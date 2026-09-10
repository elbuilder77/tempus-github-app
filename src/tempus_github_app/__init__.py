"""Tempus GitHub App - Zero-leak credential isolation and mediated execution for GitHub."""

from .credentials import GitHubAppCredentials
from .executor import GitHubAppActionAdapter, GitHubAppExecutorAdapter

__version__ = "0.1.0"
__all__ = [
    "GitHubAppCredentials",
    "GitHubAppActionAdapter",
    "GitHubAppExecutorAdapter",
]
