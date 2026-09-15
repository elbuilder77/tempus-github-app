from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tempus_ddb import TempusDDB

from tests.conftest import MockAppTransport, setup_gate_and_agents


def run_executor_cli(
    args: list[str],
    env: dict[str, str] | None = None,
    stdin_data: str | None = None,
    cwd: Path | None = None,
) -> tuple[int, str, str]:
    cmd = [sys.executable, "-m", "tempus_github_app.cli"] + args
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    repo_src = str(Path(__file__).parent.parent / "src")
    tempus_python = str(Path(__file__).parent.parent.parent / "tempus-ddb" / "python")
    existing_pythonpath = run_env.get("PYTHONPATH", "")
    run_env["PYTHONPATH"] = os.pathsep.join(
        p for p in [repo_src, tempus_python, existing_pythonpath] if p
    )

    result = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
        env=run_env,
        cwd=cwd,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def test_cli_version():
    code, out, _ = run_executor_cli(["--version"])
    assert code == 0
    assert "tempus-github-app-executor" in out


def test_cli_help():
    code, out, _ = run_executor_cli(["--help"])
    assert code == 0
    assert "--permit" in out
    assert "--executor-db" in out
    assert "--gate-id" in out
    assert "--app-client-id" in out
    assert "--installation-id" in out
    assert "--gate-db" in out


def test_cli_missing_required_arguments_fails():
    code, _out, err = run_executor_cli([])
    assert code == 1
    assert "Missing required arguments" in err
    assert "--permit" in err


def test_cli_main_in_process_with_mock_transport(
    tmp_path: Path, app_key: tuple[Path, Any], monkeypatch
):
    from tempus_github_app.cli import main
    from tempus_github_app.credentials import GitHubAppCredentials
    from tempus_github_app.executor import GitHubAppExecutorAdapter

    pem_path, _ = app_key
    env_setup = setup_gate_and_agents(tmp_path, tenant_id="tenant-cli-inproc")
    gate: TempusDDB = env_setup["gate"]

    transport = MockAppTransport()

    # Monkeypatch transport in credentials
    original_init = GitHubAppCredentials.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(GitHubAppCredentials, "__init__", patched_init)

    # Monkeypatch transport in adapter
    orig_adapter_init = GitHubAppExecutorAdapter.__init__

    def patched_adapter_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        orig_adapter_init(self, *args, **kwargs)

    monkeypatch.setattr(GitHubAppExecutorAdapter, "__init__", patched_adapter_init)

    intent = {
        "schema_version": "tempus.action-intent.v1",
        "tenant_id": "tenant-cli-inproc",
        "agent_id": env_setup["agent_id"],
        "idempotency_key": "cli-inproc-001",
        "action_type": "github.create_issue",
        "resource": "acme/widget",
        "requested_at": time.time_ns() // 1000,
        "input": {"title": "CLI In-process Issue"},
    }
    permit_str = gate.request_action(
        json.dumps(intent), env_setup["agent_keyfile"], 60
    )
    permit_file = tmp_path / "permit.json"
    permit_file.write_text(permit_str, encoding="utf-8")

    cli_args = [
        "--permit",
        str(permit_file),
        "--executor-db",
        env_setup["exec_db"],
        "--executor-keyfile",
        env_setup["exec_keyfile"],
        "--gate-id",
        env_setup["gate_id"],
        "--tenant-id",
        "tenant-cli-inproc",
        "--app-client-id",
        "Iv1.cli_test",
        "--app-private-key",
        str(pem_path),
        "--installation-id",
        "42",
        "--repository",
        "acme/widget",
        "--gate-db",
        env_setup["gate_db"],
    ]

    main(cli_args)
    assert len(transport.calls) == 2  # 1 token + 1 issue write


def test_cli_main_in_process_with_env_vars(
    tmp_path: Path, app_key: tuple[Path, Any], monkeypatch
):
    from tempus_github_app.cli import main
    from tempus_github_app.credentials import GitHubAppCredentials
    from tempus_github_app.executor import GitHubAppExecutorAdapter

    pem_path, _ = app_key
    env_setup = setup_gate_and_agents(tmp_path, tenant_id="tenant-cli-env")
    gate: TempusDDB = env_setup["gate"]

    transport = MockAppTransport()

    # Monkeypatch transports
    orig_cred_init = GitHubAppCredentials.__init__

    def patched_cred(self, *args, **kwargs):
        kwargs["transport"] = transport
        orig_cred_init(self, *args, **kwargs)

    monkeypatch.setattr(GitHubAppCredentials, "__init__", patched_cred)

    orig_adap_init = GitHubAppExecutorAdapter.__init__

    def patched_adap(self, *args, **kwargs):
        kwargs["transport"] = transport
        orig_adap_init(self, *args, **kwargs)

    monkeypatch.setattr(GitHubAppExecutorAdapter, "__init__", patched_adap)

    intent = {
        "schema_version": "tempus.action-intent.v1",
        "tenant_id": "tenant-cli-env",
        "agent_id": env_setup["agent_id"],
        "idempotency_key": "cli-env-001",
        "action_type": "github.create_issue",
        "resource": "acme/widget",
        "requested_at": time.time_ns() // 1000,
        "input": {"title": "CLI Env-var Issue"},
    }
    permit_str = gate.request_action(
        json.dumps(intent), env_setup["agent_keyfile"], 60
    )
    permit_file = tmp_path / "permit_env.json"
    permit_file.write_text(permit_str, encoding="utf-8")

    # Set all environment variables
    monkeypatch.setenv("TEMPUS_PERMIT", str(permit_file))
    monkeypatch.setenv("TEMPUS_EXECUTOR_DB", env_setup["exec_db"])
    monkeypatch.setenv("TEMPUS_EXECUTOR_KEYFILE", env_setup["exec_keyfile"])
    monkeypatch.setenv("TEMPUS_GATE_ID", env_setup["gate_id"])
    monkeypatch.setenv("TEMPUS_TENANT_ID", "tenant-cli-env")
    monkeypatch.setenv("TEMPUS_GATE_DB", env_setup["gate_db"])
    monkeypatch.setenv("GITHUB_APP_CLIENT_ID", "Iv1.cli_env_test")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY_PATH", str(pem_path))
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "42")
    monkeypatch.setenv("GITHUB_APP_REPOSITORY", "acme/widget")

    # Call main with no explicit arguments
    main([])
    assert len(transport.calls) == 2
