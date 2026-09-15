from __future__ import annotations

import time

from tempus_github_app.credentials import GitHubAppCredentials
from tempus_github_app.executor import GitHubAppActionAdapter
from tests.conftest import MockAppTransport


def test_auth_failure_does_not_write_or_leak_credentials(app_key):
    now = [time.time()]
    transport = MockAppTransport(now)
    transport.failure = RuntimeError("private-secret-value")
    credentials = GitHubAppCredentials(
        "Iv1.test",
        str(app_key[0]),
        42,
        "acme/widget",
        transport=transport,
        clock=lambda: now[0],
    )
    adapter = GitHubAppActionAdapter(credentials=credentials, transport=transport)
    result = adapter.execute_action(
        {
            "action_type": "github.create_issue",
            "resource": "acme/widget",
            "input": {"title": "test"},
        }
    )
    assert result.status == "FAILED"
    assert result.payload == {"error_code": "TEMPUS_GITHUB_CREDENTIAL_REJECTED"}
    assert len(transport.calls) == 1
    assert transport.calls[0][1].endswith("/access_tokens")


def test_action_adapter_executes_issue_creation(app_key):
    now = [time.time()]
    auth_transport = MockAppTransport(now)
    credentials = GitHubAppCredentials(
        "Iv1.test",
        str(app_key[0]),
        42,
        "acme/widget",
        transport=auth_transport,
        clock=lambda: now[0],
    )

    class CombinedTransport:
        def __init__(self):
            self.calls = []

        def request(self, method, url, headers, payload):
            self.calls.append((method, url, headers, payload))
            if "access_tokens" in url:
                return auth_transport.request(method, url, headers, payload)
            assert headers["Authorization"] == f"Bearer {auth_transport.token}"
            return {"id": 101, "number": 1, "html_url": "https://github.com/acme/widget/issues/1"}

    combined = CombinedTransport()
    adapter = GitHubAppActionAdapter(credentials=credentials, transport=combined)
    result = adapter.execute_action(
        {
            "action_type": "github.create_issue",
            "resource": "acme/widget",
            "input": {"title": "Bug report", "body": "Details here"},
        }
    )
    assert result.status == "SUCCEEDED"
    assert result.payload["number"] == 1
    assert result.payload["resource"] == "acme/widget"
