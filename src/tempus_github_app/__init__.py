"""Tempus GitHub App - Zero-leak credential isolation and mediated execution for GitHub."""

from typing import Any

from .credentials import GitHubAppCredentials
from .executor import GitHubAppActionAdapter, GitHubAppExecutorAdapter
from .transport import GitHubRateLimitError, PermitContext
from .webhook import GitHubWebhookHandler, verify_webhook_signature

__version__ = "0.1.0"
__all__ = [
    "GitHubAppActionAdapter",
    "GitHubAppCredentials",
    "GitHubAppExecutorAdapter",
    "GitHubRateLimitError",
    "GitHubWebhookHandler",
    "PermitContext",
    "create_webhook_app",
    "verify_webhook_signature",
]


def create_webhook_app(*args: Any, **kwargs: Any) -> Any:
    """Lazily load and create the FastAPI webhook application."""
    from .server import create_webhook_app as _create_webhook_app

    return _create_webhook_app(*args, **kwargs)
