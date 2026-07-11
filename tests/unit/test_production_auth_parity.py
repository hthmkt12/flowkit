"""Production/test parity tests for live authorization.

These tests spawn a clean child Python process (no ``pytest`` in
``sys.modules``) and assert that live-authorization decisions are
identical to the in-process test behavior.  The live path must fail
closed purely from runtime config predicates, never from the presence
of the pytest framework.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]  # flowkit/
FLOWKIT_DIR = REPO_ROOT
AGENT_DIR = FLOWKIT_DIR / "agent"

AUTH_MODULES = [
    AGENT_DIR / "db" / "crud.py",
    AGENT_DIR / "api" / "tasks.py",
    AGENT_DIR / "worker" / "processor.py",
]

# Functions whose body must never branch on framework presence.
AUTH_FUNCTION_NAMES = {
    "_require_live_arm_auth_enabled",
    "live_auth_ready",
    "arm_live_actions",
    "approve_task",
    "_check_rate_limit",
    "_dispatch",
}


def _run_clean_child(script: str, env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    """Run a snippet in a clean interpreter with no pytest module loaded."""
    env = dict(os.environ)
    # Force auth disabled for the parity-failure probes.
    env.update(env_overrides)
    # Ensure no pytest collection state leaks into the child.
    for key in ("PYTEST_CURRENT_TEST", "PYTEST_CONFIGURE"):
        env.pop(key, None)
    # Make ``agent`` importable when cwd is flowkit/.
    env["PYTHONPATH"] = str(FLOWKIT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(FLOWKIT_DIR),
        timeout=60,
    )


def test_live_auth_ready_is_false_in_clean_python_process_when_auth_disabled():
    """A non-pytest process with auth disabled reports live_auth_ready()=False."""
    script = textwrap.dedent(
        """
        import sys
        # Prove no pytest framework is loaded in this child.
        assert "pytest" not in sys.modules, "parity child must not load pytest"
        from agent.db import crud
        print(crud.live_auth_ready())
        """
    )
    result = _run_clean_child(
        script,
        {"API_AUTH_ENABLED": "false", "WS_AUTH_ENABLED": "false"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


def test_live_arm_rejected_in_clean_python_process_when_auth_disabled(tmp_path):
    """A non-pytest process cannot create a live arm when auth is disabled."""
    db_path = tmp_path / "parity.db"
    # Auth check runs BEFORE any DB access in arm_live_actions(), so we
    # can prove fail-closed behavior without initializing the schema.
    # This avoids aiosqlite WAL deadlocks observed on some Windows temp
    # directories in subprocess children.
    script = textwrap.dedent(
        f"""
        import sys, asyncio, os
        assert "pytest" not in sys.modules, "parity child must not load pytest"
        os.environ["DB_PATH"] = r"{db_path}"
        os.environ["DATA_ENCRYPTION_KEY"] = "parity-test-key"
        from agent.db import crud

        async def main():
            try:
                await crud.arm_live_actions("acct-1", ["POST_TEXT"], 300, "parity")
            except ValueError as exc:
                print("ValueError: " + str(exc))
                return
            print("ARM_CREATED")

        asyncio.run(main())
        """
    )
    result = _run_clean_child(
        script,
        {"API_AUTH_ENABLED": "false", "WS_AUTH_ENABLED": "true"},
    )
    assert result.returncode == 0, result.stderr
    assert "ValueError: API_AUTH_ENABLED" in result.stdout
    assert "ARM_CREATED" not in result.stdout


def test_live_security_modules_do_not_branch_on_pytest_presence():
    """AST-scan authorization functions for pytest/sys.modules branching."""
    forbidden_substrings = ("pytest", "sys.modules")
    for module_path in AUTH_MODULES:
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name not in AUTH_FUNCTION_NAMES:
                    continue
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        if sub.value in forbidden_substrings:
                            pytest.fail(
                                f"{module_path.name}:{node.name} references '{sub.value}'"
                            )
                    if isinstance(sub, ast.Name) and sub.id == "sys":
                        # Allow ``import sys`` only at module level, not in auth funcs.
                        if isinstance(sub.ctx, ast.Load):
                            pytest.fail(
                                f"{module_path.name}:{node.name} uses sys inside auth function"
                            )


def test_no_pytest_or_sys_modules_strings_in_auth_modules():
    """No raw string references to pytest/sys.modules remain in auth modules."""
    for module_path in AUTH_MODULES:
        source = module_path.read_text(encoding="utf-8")
        for token in ("pytest", "sys.modules"):
            assert token not in source, f"{module_path.name} still contains '{token}'"
