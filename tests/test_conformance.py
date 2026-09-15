from __future__ import annotations

from pathlib import Path
from typing import Any

from tempus_ddb.testing import AdapterConformanceHarness

from tempus_github_app.credentials import GitHubAppCredentials
from tempus_github_app.executor import GitHubAppActionAdapter


class ConformanceTransport:
    """Mock transport handling token issuance and GitHub API issue creation."""

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if "access_tokens" in url:
            return {
                "token": "ghs_conformance_dummy_token",
                "expires_at": "2099-01-01T00:00:00Z",
            }
        return {
            "id": 1234,
            "number": 99,
            "html_url": "https://github.com/acme/widget-repo/issues/99",
            "state": "open",
        }


def test_github_app_adapter_conformance(app_key: tuple[Path, Any]) -> None:
    """Run the official Tempus DDB ActionAdapter conformance test suite."""
    pem_path, _ = app_key

    def create_adapter() -> GitHubAppActionAdapter:
        transport = ConformanceTransport()
        credentials = GitHubAppCredentials(
            client_id="Iv1.conformance",
            private_key_path=str(pem_path),
            installation_id=42,
            repository="acme/widget-repo",
            transport=transport,
        )
        return GitHubAppActionAdapter(
            credentials=credentials,
            transport=transport,
        )

    harness = AdapterConformanceHarness(
        adapter_factory=create_adapter,
        valid_action_type="github.create_issue",
        valid_resource="acme/widget-repo",
        valid_input={"title": "Conformance Issue", "body": "Testing conformance"},
        tenant_id="tenant-conformance",
    )
    harness.run_all_checks()
