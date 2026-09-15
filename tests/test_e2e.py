from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from tempus_ddb import TempusDDB

from tempus_github_app.credentials import GitHubAppCredentials
from tempus_github_app.executor import GitHubAppExecutorAdapter
from tests.conftest import MockAppTransport, setup_gate_and_agents


def test_end_to_end_issue_creation_and_replay_protection(
    tmp_path: Path, app_key: tuple[Path, Any]
) -> None:
    pem_path, _ = app_key
    env = setup_gate_and_agents(tmp_path, tenant_id="tenant-acme")
    gate: TempusDDB = env["gate"]

    transport = MockAppTransport()
    credentials = GitHubAppCredentials(
        client_id="Iv1.test_e2e",
        private_key_path=str(pem_path),
        installation_id=42,
        repository="acme/widget",
        transport=transport,
    )

    executor = GitHubAppExecutorAdapter(
        executor_db=env["exec_db"],
        executor_keyfile=env["exec_keyfile"],
        trusted_gate_id=env["gate_id"],
        trusted_tenant_id=env["tenant_id"],
        credentials=credentials,
        transport=transport,
    )

    # 1. Agent creates and signs Intent
    intent = {
        "schema_version": "tempus.action-intent.v1",
        "tenant_id": env["tenant_id"],
        "agent_id": env["agent_id"],
        "idempotency_key": "e2e-issue-001",
        "action_type": "github.create_issue",
        "resource": "acme/widget",
        "requested_at": time.time_ns() // 1000,
        "input": {"title": "Automated Bug Report", "body": "Found by QA agent"},
    }

    # 2. Gate issues single-use permit
    permit_str = gate.request_action(json.dumps(intent), env["agent_keyfile"], 60)
    permit_data = json.loads(permit_str)
    assert permit_data["authorization"]["decision"] == "ALLOWED"

    # 3. Mediated executor consumes permit and acts
    outcome_str = executor.execute(permit_str)
    outcome_data = json.loads(outcome_str)
    assert outcome_data["status"] == "SUCCEEDED"
    assert outcome_data["output"]["number"] == 1
    assert outcome_data["output"]["resource"] == "acme/widget"

    # Invariant: installation credentials and RSA key NEVER leak into outcome
    assert transport.token not in outcome_str
    assert "private_key" not in outcome_str

    # 4. Replay protection: identical permit re-execution fails closed
    with pytest.raises(Exception) as exc_info:
        executor.execute(permit_str)
    assert "already consumed" in str(exc_info.value).lower() or "action id" in str(exc_info.value).lower()

    # 5. Commit outcome to Gate to complete full cryptographic trace
    auth_id = permit_data["authorization"]["authorization_id"]
    receipt_str = gate.commit_outcome_signed(auth_id, outcome_str)
    receipt_data = json.loads(receipt_str)
    assert receipt_data["receipt"]["status"] == "SUCCEEDED"

    # 6. Verify trace offline with Tempus Gate
    action_id = permit_data["authorization"]["action_id"]
    verification = json.loads(gate.verify_trace(action_id))
    assert verification["status"] == "VERIFIED"


def test_end_to_end_pull_request_creation(
    tmp_path: Path, app_key: tuple[Path, Any]
) -> None:
    pem_path, _ = app_key
    env = setup_gate_and_agents(tmp_path, tenant_id="tenant-devops")
    gate: TempusDDB = env["gate"]

    transport = MockAppTransport()
    credentials = GitHubAppCredentials(
        client_id="Iv1.test_pr",
        private_key_path=str(pem_path),
        installation_id=42,
        repository="acme/widget",
        transport=transport,
    )

    executor = GitHubAppExecutorAdapter(
        executor_db=env["exec_db"],
        executor_keyfile=env["exec_keyfile"],
        trusted_gate_id=env["gate_id"],
        trusted_tenant_id=env["tenant_id"],
        credentials=credentials,
        transport=transport,
    )

    intent = {
        "schema_version": "tempus.action-intent.v1",
        "tenant_id": env["tenant_id"],
        "agent_id": env["agent_id"],
        "idempotency_key": "e2e-pr-001",
        "action_type": "github.create_pull_request",
        "resource": "acme/widget",
        "requested_at": time.time_ns() // 1000,
        "input": {
            "title": "fix: resolve memory leak",
            "head": "patch-1",
            "base": "main",
            "body": "Automated patch from Cursor agent",
            "draft": False,
        },
    }

    permit_str = gate.request_action(json.dumps(intent), env["agent_keyfile"], 60)
    outcome_str = executor.execute(permit_str)
    outcome_data = json.loads(outcome_str)
    assert outcome_data["status"] == "SUCCEEDED"
    assert outcome_data["output"]["number"] == 2


def test_recover_incomplete_executions(
    tmp_path: Path, app_key: tuple[Path, Any]
) -> None:
    pem_path, _ = app_key
    env = setup_gate_and_agents(tmp_path, tenant_id="tenant-recovery")

    transport = MockAppTransport()
    credentials = GitHubAppCredentials(
        client_id="Iv1.recovery",
        private_key_path=str(pem_path),
        installation_id=42,
        repository="acme/widget",
        transport=transport,
    )

    executor = GitHubAppExecutorAdapter(
        executor_db=env["exec_db"],
        executor_keyfile=env["exec_keyfile"],
        trusted_gate_id=env["gate_id"],
        trusted_tenant_id=env["tenant_id"],
        credentials=credentials,
        transport=transport,
    )

    # Recovering with 0 incomplete records should succeed cleanly
    recovery_result = executor.recover_incomplete(0)
    assert "0" in recovery_result or "recovered" in recovery_result.lower() or "[]" in recovery_result
