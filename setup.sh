#!/usr/bin/env bash
set -e

echo "========================================="
echo "  FBKit — Setup"
echo "========================================="
echo ""

if [[ "$(uname -s)" == MINGW* ]] || [[ "$(uname -s)" == MSYS* ]] || [[ "$(uname -s)" == CYGWIN* ]]; then
    echo "Detected Windows (Git Bash / MSYS2)."
    echo "  Tip: For best results, use PowerShell with .venv or WSL."
    echo ""
fi

ERRORS=0

echo "Checking Python..."
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
        echo "  OK: Python $PY_VERSION"
    else
        echo "  WARNING: Python $PY_VERSION found, 3.10+ recommended"
    fi
else
    echo "  MISSING: Python 3 not found"
    ERRORS=$((ERRORS + 1))
fi

echo "Checking pip..."
if python3 -m pip --version &>/dev/null; then
    echo "  OK: $(python3 -m pip --version | head -1)"
else
    echo "  MISSING: pip not found"
    ERRORS=$((ERRORS + 1))
fi

echo "Checking Chrome..."
if [ -d "/Applications/Google Chrome.app" ] || command -v google-chrome &>/dev/null || command -v google-chrome-stable &>/dev/null; then
    echo "  OK: Chrome found"
else
    echo "  WARNING: Chrome not detected (needed for the Facebook extension bridge)"
fi

echo ""

if [ "$ERRORS" -gt 0 ]; then
    echo "Found $ERRORS missing dependency(ies). Install them and re-run."
    exit 1
fi

echo "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  Created: .venv/"
else
    echo "  Exists: .venv/"
fi

echo "Installing Python dependencies..."
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "Verifying agent can import..."
python3 -c "from agent.main import app; print('  OK: agent.main imports successfully')" 2>&1 || {
    echo "  FAILED: agent cannot import — check error above"
    exit 1
}

echo ""
echo "========================================="
echo "  Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Load Chrome extension:"
echo "     chrome://extensions → Developer mode → Load unpacked → extension/"
echo ""
echo "  2. Open Facebook and sign in:"
echo "     https://www.facebook.com/"
echo ""
echo "  3. Start the agent in safe mode:"
echo "     LIVE_ACTIONS_ENABLED=false DRY_RUN_DEFAULT=true APPROVAL_REQUIRED=true API_AUTH_ENABLED=false WS_AUTH_ENABLED=false python -m agent.main"
echo ""
echo "  4. Verify:"
echo "     curl http://127.0.0.1:8100/health"
echo "     curl http://127.0.0.1:8100/api/status"
echo ""
