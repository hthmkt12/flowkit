from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Exchange a ZooPost Cloud registration token and print env-only FBKit setup commands.")
    parser.add_argument("--cloud-url", default=os.environ.get("ZOOPOST_CLOUD_API_URL", "http://127.0.0.1:8200"))
    parser.add_argument("--installation-id", required=True)
    parser.add_argument("--registration-token", required=True)
    parser.add_argument("--bearer-token", default=os.environ.get("ZOOPOST_CLOUD_BEARER_TOKEN"))
    args = parser.parse_args()

    if os.environ.get("LIVE_ACTIONS_ENABLED", "false").lower() == "true":
        print("Refusing setup while LIVE_ACTIONS_ENABLED=true.", file=sys.stderr)
        return 2

    credential = exchange_token(args.cloud_url, args.installation_id, args.registration_token, args.bearer_token)
    print_env_commands(args.cloud_url, args.installation_id, credential)
    return 0


def exchange_token(cloud_url: str, installation_id: str, registration_token: str, bearer_token: str | None) -> str:
    body = json.dumps({"registration_token": registration_token}).encode()
    url = f"{cloud_url.rstrip('/')}/agent-gateway/setup/installations/{installation_id}/exchange"
    headers = {"Content-Type": "application/json", "User-Agent": "zoopost-agent-env-setup/1"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise SystemExit(f"Token exchange failed: HTTP {exc.code} {detail}") from exc
    credential = data.get("credential")
    if not isinstance(credential, str) or not credential:
        raise SystemExit("Token exchange response did not include a credential.")
    return credential


def print_env_commands(cloud_url: str, installation_id: str, credential: str):
    commands = [
        f'$env:ZOOPOST_CLOUD_API_URL="{cloud_url}"',
        f'$env:ZOOPOST_AGENT_INSTALLATION_ID="{installation_id}"',
        f'$env:ZOOPOST_AGENT_CREDENTIAL="{credential}"',
        '$env:LIVE_ACTIONS_ENABLED="false"',
        '$env:DRY_RUN_DEFAULT="true"',
        '$env:APPROVAL_REQUIRED="true"',
        '$env:API_AUTH_ENABLED="false"',
        '$env:WS_AUTH_ENABLED="false"',
        '.\\.venv\\Scripts\\python.exe -m agent.main',
    ]
    print("\n".join(commands))


if __name__ == "__main__":
    raise SystemExit(main())
