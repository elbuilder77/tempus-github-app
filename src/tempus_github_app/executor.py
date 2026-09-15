"""Credential-isolated GitHub App executor for Tempus permits."""

from __future__ import annotations

import inspect
from typing import Any, ClassVar

from tempus_ddb.executor_runtime import (
    ActionAdapter,
    AmbiguousTransportError,
    ExecutionResult,
    ExecutorRuntime,
)

from .credentials import GitHubAppCredentials
from .transport import (
    RESOURCE_PATTERN,
    GitHubAPIError,
    GitHubExecutorError,
    GitHubTransport,
    UrllibGitHubTransport,
    validate_github_api_url,
)


class GitHubAppActionAdapter(ActionAdapter):
    """ActionAdapter implementation for GitHub REST API writes using GitHub App installation tokens."""

    unsupported_error_code = "TEMPUS_GITHUB_BINDING_REJECTED"

    SUPPORTED_ACTIONS: ClassVar[set[str]] = {
        "github.create_issue",
        "github.create_pull_request",
    }

    def __init__(
        self,
        credentials: GitHubAppCredentials,
        api_url: str = "https://api.github.com",
        transport: GitHubTransport | None = None,
    ):
        self._credentials = credentials
        self._api_url = validate_github_api_url(api_url)
        self._transport = transport or UrllibGitHubTransport()

    @property
    def supported_actions(self) -> set[str]:
        return self.SUPPORTED_ACTIONS

    def execute_action(self, intent: dict[str, Any]) -> ExecutionResult:
        method, url, payload, action_type, resource = self._bind_request(intent)

        try:
            token = self._credentials.token_for(resource, action_type)
        except Exception:  # noqa: BLE001
            # Never leak credential details or stack trace
            return ExecutionResult(
                status="FAILED",
                payload={"error_code": "TEMPUS_GITHUB_CREDENTIAL_REJECTED"},
            )

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "tempus-github-app-executor/0.1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            response = self._transport.request(method, url, headers, payload)
            result = self._sanitize_result(response, action_type, resource)
            return ExecutionResult(status="SUCCEEDED", payload=result)
        except GitHubAPIError as exc:
            if exc.status_code >= 500:
                raise AmbiguousTransportError(
                    f"GITHUB_SERVER_RESPONSE_{exc.status_code}"
                ) from exc
            return ExecutionResult(
                status="FAILED",
                payload={
                    "error_code": f"GITHUB_HTTP_{exc.status_code}",
                    "message": str(exc),
                },
            )
        except Exception as exc:
            # Ambiguous network outcomes must fail closed as UNKNOWN
            raise AmbiguousTransportError(
                f"GITHUB_TRANSPORT_AMBIGUOUS: {type(exc).__name__}"
            ) from exc

    def _bind_request(
        self, intent: dict[str, Any]
    ) -> tuple[str, str, dict[str, Any], str, str]:
        action_type = self._required_string(intent, "action_type")
        resource = self._required_string(intent, "resource")
        if not RESOURCE_PATTERN.fullmatch(resource):
            raise GitHubExecutorError("resource must be an exact 'owner/repository' value")

        action_input = intent.get("input")
        if not isinstance(action_input, dict):
            raise GitHubExecutorError("intent.input must be an object")

        if action_type == "github.create_issue":
            payload = self._issue_payload(action_input)
            endpoint = f"/repos/{resource}/issues"
        elif action_type == "github.create_pull_request":
            payload = self._pull_request_payload(action_input)
            endpoint = f"/repos/{resource}/pulls"
        else:
            raise GitHubExecutorError(f"unsupported GitHub action_type: {action_type}")

        return "POST", self._api_url + endpoint, payload, action_type, resource

    @staticmethod
    def _required_string(value: dict[str, Any], field: str) -> str:
        result = value.get(field)
        if not isinstance(result, str) or not result:
            raise GitHubExecutorError(f"{field} must be a non-empty string")
        return result

    def _issue_payload(self, value: dict[str, Any]) -> dict[str, Any]:
        allowed = {"title", "body", "labels"}
        self._reject_unknown_fields(value, allowed)
        payload: dict[str, Any] = {"title": self._required_string(value, "title")}
        if "body" in value:
            if not isinstance(value["body"], str):
                raise GitHubExecutorError("input.body must be a string")
            payload["body"] = value["body"]
        if "labels" in value:
            labels = value["labels"]
            if not isinstance(labels, list) or not all(
                isinstance(label, str) for label in labels
            ):
                raise GitHubExecutorError("input.labels must be an array of strings")
            payload["labels"] = labels
        return payload

    def _pull_request_payload(self, value: dict[str, Any]) -> dict[str, Any]:
        allowed = {"title", "head", "base", "body", "draft"}
        self._reject_unknown_fields(value, allowed)
        payload: dict[str, Any] = {
            "title": self._required_string(value, "title"),
            "head": self._required_string(value, "head"),
            "base": self._required_string(value, "base"),
        }
        if "body" in value:
            if not isinstance(value["body"], str):
                raise GitHubExecutorError("input.body must be a string")
            payload["body"] = value["body"]
        if "draft" in value:
            if not isinstance(value["draft"], bool):
                raise GitHubExecutorError("input.draft must be a boolean")
            payload["draft"] = value["draft"]
        return payload

    @staticmethod
    def _reject_unknown_fields(value: dict[str, Any], allowed: set) -> None:
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise GitHubExecutorError(f"unsupported input fields: {', '.join(unknown)}")

    @staticmethod
    def _sanitize_result(
        response: dict[str, Any], action_type: str, resource: str
    ) -> dict[str, Any]:
        result = {"action_type": action_type, "resource": resource}
        for field in ("id", "number", "html_url", "url", "state"):
            if field in response:
                result[field] = response[field]
        return result


class GitHubAppExecutorAdapter:
    """Execute a narrow set of GitHub writes from a verified Tempus permit using GitHub App credentials."""

    def __init__(
        self,
        executor_db: str,
        executor_keyfile: str,
        trusted_gate_id: str,
        trusted_tenant_id: str,
        credentials: GitHubAppCredentials,
        api_url: str = "https://api.github.com",
        transport: GitHubTransport | None = None,
        executor_pool_size: int = 8,
        gate_db: str | None = None,
    ):
        self._adapter = GitHubAppActionAdapter(
            credentials=credentials, api_url=api_url, transport=transport
        )
        runtime_kwargs: dict[str, Any] = {
            "executor_db": executor_db,
            "executor_keyfile": executor_keyfile,
            "trusted_gate_id": trusted_gate_id,
            "trusted_tenant_id": trusted_tenant_id,
            "executor_pool_size": executor_pool_size,
        }
        if gate_db is not None and "gate_db" in inspect.signature(ExecutorRuntime.__init__).parameters:
            runtime_kwargs["gate_db"] = gate_db
        self._runtime = ExecutorRuntime(**runtime_kwargs)

    def execute(self, permit_json: str) -> str:
        """Consume a permit, perform exactly its GitHub action, and sign the outcome."""
        return self._runtime.execute_permit(permit_json, self._adapter)

    execute_permit = execute

    def recover_incomplete(self, older_than_seconds: int = 0) -> str:
        """Mark stale STARTED executions UNKNOWN without replaying GitHub writes."""
        return self._runtime.raw_executor.recover_incomplete(older_than_seconds)

    def get_execution_state(self, authorization_id: str) -> str:
        """Return the executor's signed local state for an authorization."""
        return self._runtime.raw_executor.get_execution_state(authorization_id)
