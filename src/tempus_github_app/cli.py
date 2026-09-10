"""Command line interface for Tempus GitHub App Executor."""

import argparse
import json
import sys
from pathlib import Path

from tempus_ddb.executor_runtime import UnknownExecutionError

from .credentials import GitHubAppCredentials
from .executor import GitHubAppExecutorAdapter


def _read_permit(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tempus-github-app-executor",
        description="Execute GitHub writes bound to a signed Tempus permit using GitHub App credentials",
    )
    parser.add_argument(
        "--permit", required=True, help="Path to signed permit JSON file, or '-' for stdin"
    )
    parser.add_argument("--executor-db", required=True, help="Path to executor SQLite database")
    parser.add_argument("--executor-keyfile", required=True, help="Path to executor Ed25519 keys JSON")
    parser.add_argument("--gate-id", required=True, help="Trusted Gate public key (hex)")
    parser.add_argument("--tenant-id", required=True, help="Tenant ID")

    # GitHub App credentials
    parser.add_argument("--app-client-id", required=True, help="GitHub App Client ID (e.g. Iv1.xxx)")
    parser.add_argument("--app-private-key", required=True, help="Path to GitHub App RSA private key (.pem)")
    parser.add_argument("--installation-id", type=int, required=True, help="GitHub App installation ID")
    parser.add_argument("--repository", required=True, help="Target repository in owner/repo format")
    parser.add_argument("--api-url", default="https://api.github.com", help="GitHub API base URL")
    parser.add_argument(
        "--executor-pool-size",
        type=int,
        default=8,
        help="Maximum pooled SQLite connections (default: 8)",
    )

    args = parser.parse_args()

    try:
        credentials = GitHubAppCredentials(
            client_id=args.app_client_id,
            private_key_path=args.app_private_key,
            installation_id=args.installation_id,
            repository=args.repository,
            api_url=args.api_url,
        )

        adapter = GitHubAppExecutorAdapter(
            executor_db=args.executor_db,
            executor_keyfile=args.executor_keyfile,
            trusted_gate_id=args.gate_id,
            trusted_tenant_id=args.tenant_id,
            credentials=credentials,
            api_url=args.api_url,
            executor_pool_size=args.executor_pool_size,
        )

        permit_content = _read_permit(args.permit)
        outcome = adapter.execute(permit_content)
        print(outcome)
    except UnknownExecutionError as exc:
        print(exc.observation, file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
