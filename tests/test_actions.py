from unittest.mock import MagicMock, Mock

import pytest

from tempus_github_app.executor import GitHubAppActionAdapter
from tempus_github_app.transport import GitHubExecutorError, UrllibGitHubTransport

CASES = [
    ("add_comment", {"issue_number": 7, "body": "Hello"},
     "issues/7/comments", {"body": "Hello"}, {"id": 3}),
    ("add_labels", {"issue_number": 7, "labels": ["bug"]},
     "issues/7/labels", {"labels": ["bug"]}, [{"id": 3, "name": "bug"}]),
    ("request_review", {"pull_number": 7, "reviewers": ["alice"]},
     "pulls/7/requested_reviewers", {"reviewers": ["alice"]}, {"number": 7}),
    ("request_review", {"pull_number": 7, "team_reviewers": ["core"], "reviewers": []},
     "pulls/7/requested_reviewers", {"team_reviewers": ["core"], "reviewers": []},
     {"number": 7}),
]


@pytest.mark.parametrize("action,inputs,endpoint,payload,response", CASES)
def test_new_actions(action, inputs, endpoint, payload, response):
    credentials = Mock()
    credentials.token_for.return_value = "secret-token"
    transport = Mock()
    transport.request.return_value = response
    adapter = GitHubAppActionAdapter(credentials, transport=transport)
    result = adapter.execute_action({
        "action_type": "github." + action, "resource": "acme/widget", "input": inputs,
    })
    assert result.status == "SUCCEEDED"
    credentials.token_for.assert_called_once_with("acme/widget", "github." + action)
    args = transport.request.call_args.args
    assert args[0:2] == ("POST", "https://api.github.com/repos/acme/widget/" + endpoint)
    assert args[3] == payload
    assert "secret-token" not in str(result.payload)


@pytest.mark.parametrize("action,inputs,endpoint,payload,response", CASES)
@pytest.mark.parametrize("invalid", [None, True, False, 0, -1, 1.2, "7"])
def test_numbers_rejected_before_credentials(action, inputs, endpoint, payload, response, invalid):
    inputs = dict(inputs)
    inputs["pull_number" if action == "request_review" else "issue_number"] = invalid
    assert_rejected(action, inputs)


def assert_rejected(action, inputs):
    credentials, transport = Mock(), Mock()
    adapter = GitHubAppActionAdapter(credentials, transport=transport)
    with pytest.raises(GitHubExecutorError):
        adapter.execute_action({
            "action_type": "github." + action, "resource": "acme/widget", "input": inputs,
        })
    credentials.token_for.assert_not_called()
    transport.request.assert_not_called()


@pytest.mark.parametrize("action,inputs,endpoint,payload,response", CASES)
def test_unknown_fields(action, inputs, endpoint, payload, response):
    assert_rejected(action, {**inputs, "unexpected": True})


@pytest.mark.parametrize("body", [None, 123, "", "   ", "x" * 65_537],
                         ids=["null", "number", "empty", "whitespace", "too-long"])
def test_invalid_comment(body):
    assert_rejected("add_comment", {"issue_number": 1, "body": body})


def test_comment_boundary():
    adapter = GitHubAppActionAdapter(Mock())
    assert adapter._comment_payload({"body": "x" * 65_536}) == {"body": "x" * 65_536}


@pytest.mark.parametrize("items", [None, "alice", {}, [None], [1], [""], [" "]])
@pytest.mark.parametrize("action,field", [
    ("add_labels", "labels"), ("request_review", "reviewers"),
    ("request_review", "team_reviewers"),
])
def test_invalid_lists(action, field, items):
    number = "issue_number" if action == "add_labels" else "pull_number"
    assert_rejected(action, {number: 1, field: items})


@pytest.mark.parametrize("action,inputs", [
    ("add_comment", {"issue_number": 1}),
    ("add_labels", {"issue_number": 1}),
    ("add_labels", {"issue_number": 1, "labels": []}),
    ("request_review", {"pull_number": 1}),
    ("request_review", {"pull_number": 1, "reviewers": [], "team_reviewers": []}),
])
def test_missing_required_fields(action, inputs):
    assert_rejected(action, inputs)


def test_label_response_sanitization():
    result = GitHubAppActionAdapter._sanitize_result([
        {"id": 1, "name": "bug", "color": "ffffff", "description": "secret", "token": "secret"}
    ], "github.add_labels", "acme/widget")
    assert result["labels"] == [{"id": 1, "name": "bug", "color": "ffffff"}]
    assert "secret" not in str(result)


@pytest.mark.parametrize("action", ["github.add_comment", "github.request_review"])
def test_object_response_sanitization(action):
    result = GitHubAppActionAdapter._sanitize_result(
        {"id": 1, "body": "secret", "user": {"token": "secret"}}, action, "acme/widget"
    )
    assert result == {"action_type": action, "resource": "acme/widget", "id": 1}


def test_real_transport_accepts_labels_list(monkeypatch):
    response = Mock()
    response.read.return_value = b'[{"id":1,"name":"bug"}]'
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value = response
    monkeypatch.setattr("tempus_github_app.transport.request.build_opener", lambda *args: opener)
    assert UrllibGitHubTransport().request(
        "POST", "https://api.github.com/repos/acme/widget/issues/1/labels", {}, {"labels": ["bug"]}
    ) == [{"id": 1, "name": "bug"}]
