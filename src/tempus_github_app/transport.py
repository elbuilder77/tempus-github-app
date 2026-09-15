"""Transport boundary and error handling for GitHub API requests."""

import json
import re
from typing import Any, Protocol
from urllib import error, parse, request

RESOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def validate_github_api_url(api_url: str) -> str:
    """Accept only an explicit HTTPS GitHub or GitHub Enterprise API endpoint."""
    candidate = api_url.strip().rstrip("/")
    parsed = parse.urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise GitHubExecutorError("GitHub API URL must be an absolute HTTPS endpoint")
    return candidate


class GitHubExecutorError(RuntimeError):
    """Base error for configuration and permit failures."""


class GitHubAPIError(GitHubExecutorError):
    """A definitive HTTP response returned by GitHub."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class GitHubTransport(Protocol):
    """Transport boundary used by the real client and deterministic tests."""

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one GitHub API request."""


class RejectRedirects(request.HTTPRedirectHandler):
    """Prevent credential forwarding to third-party endpoints."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise GitHubExecutorError("GitHub API redirects are not allowed")


class UrllibGitHubTransport:
    """Minimal GitHub REST transport rejecting redirects and enforcing HTTPS."""

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        validate_github_api_url(url)
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        github_request = request.Request(
            url,
            data=encoded,
            headers=headers,
            method=method,
        )
        try:
            opener = request.build_opener(RejectRedirects())
            with opener.open(github_request, timeout=30) as response:
                body = response.read().decode("utf-8")
                parsed = json.loads(body) if body else {}
                if not isinstance(parsed, dict):
                    raise GitHubExecutorError("GitHub returned a non-object JSON response")
                return parsed
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
                message = str(parsed.get("message", body))
            except json.JSONDecodeError:
                message = body or str(exc)
            raise GitHubAPIError(exc.code, message) from exc
