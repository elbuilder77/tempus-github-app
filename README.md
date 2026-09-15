<div align="center">

# Tempus GitHub App

### Credential-Isolated Mediated Executor and GitHub App Integration for Tempus DDB

**Short-lived installation tokens · Zero-leak credential boundary · Atomic single-use permit consumption · Cryptographic receipts**

<p align="center">
  <a href="https://github.com/elbuilder77/tempus-github-app/actions/workflows/ci.yml"><img src="https://github.com/elbuilder77/tempus-github-app/actions/workflows/ci.yml/badge.svg" alt="CI Build" /></a>
  <a href="https://github.com/elbuilder77/tempus-ddb"><img src="https://img.shields.io/badge/ecosystem-tempus--ddb-blue.svg" alt="Tempus DDB Ecosystem" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT" /></a>
  <a href="https://elbuilder77.github.io/tempus-ddb/"><img src="https://img.shields.io/badge/docs-interactive%20trace-orange.svg" alt="Interactive Trace Docs" /></a>
</p>

</div>

---

## 🔒 Overview

**Tempus GitHub App** decouples GitHub privileged operations from autonomous AI agents. Rather than provisioning personal access tokens (PATs) directly to agents or runners:

1. **Requesting Agents** sign an **Intent** declaring the requested repository action without holding GitHub credentials.
2. **Tempus Gate** evaluates cryptographic tenant policy and grants an expiring, single-use signed **Permit**.
3. **Tempus GitHub App Executor** validates the permit, atomically consumes it, and mints short-lived (1-hour), installation- and repository-scoped GitHub App tokens using an RSA private key.
4. **Execution Outcomes** are signed and recorded into the Tempus immutable decision ledger.

Neither the GitHub App private key nor ephemeral installation tokens ever leak to the requesting agent or execution receipts.

---

## ⚡ Installation

```bash
pip install -e .
# or with optional webhook server:
pip install -e ".[server]"
```

Requires Python 3.10+ and `tempus-ddb>=0.5.0`.

---

## 🚀 Quick Usage

### 1. Configure the Executor
Ensure you have registered a GitHub App and installed it on your repository (see [docs/SETUP.md](docs/SETUP.md)).

You can configure credentials either via CLI arguments or environment variables (`.env` supported):

```bash
cp .env.example .env
# Edit .env with your App Client ID, private key path, installation ID, repository, and Gate ID
```

### 2. Execute a Signed Permit via CLI
Given a signed permit `permit.json` issued by the Tempus Gate for `github.create_issue`:

```bash
# Using CLI arguments:
tempus-github-app-executor \
  --permit permit.json \
  --executor-db executor.db \
  --executor-keyfile executor.keys.json \
  --gate-id <GATE_PUBLIC_KEY> \
  --tenant-id <TENANT_ID> \
  --app-client-id <APP_CLIENT_ID> \
  --app-private-key /path/to/private-key.pem \
  --installation-id 12345678 \
  --repository owner/repo

# Or with environment variables configured in .env:
tempus-github-app-executor --permit permit.json
```

Accepts `stdin` via `--permit -` for piping directly from `tempus request-action`.

### 3. Optional: Webhook Receiver Server

Run the FastAPI-based webhook receiver to securely verify GitHub webhook deliveries:

```bash
tempus-github-app-server --secret <WEBHOOK_SECRET> --port 8000
```

* `POST /webhook`: Validates `X-Hub-Signature-256` HMAC-SHA256 signature and dispatches events.
* `GET /healthz`: Health check endpoint for container orchestrators.

### 4. Python SDK Integration

```python
from tempus_github_app import GitHubAppCredentials, GitHubAppExecutorAdapter

credentials = GitHubAppCredentials(
    client_id="Iv1.xxxx",
    private_key_path="secrets/app.pem",
    installation_id=12345678,
    repository="owner/repo",
)

executor = GitHubAppExecutorAdapter(
    executor_db="executor.db",
    executor_keyfile="executor.keys.json",
    trusted_gate_id=gate_public_key,
    trusted_tenant_id="tenant-1",
    credentials=credentials,
)

outcome_json = executor.execute(permit_json)
```

---

## 🛡️ Security Guarantees & Invariants

* **Zero Credential Leakage**: The agent never receives GitHub tokens. The executor process handles authentication internally.
* **Scope Minimization**: Tokens are generated on-demand with minimal repository and permission scope (`issues: write` or `pull_requests: write`).
* **Redirect Shielding**: Enforces strict redirect blocking (`RejectRedirects`) on API calls to prevent credential forwarding to third-party endpoints.
* **Replay Protection**: The underlying Tempus permit is consumed atomically; replay attempts fail immediately without contacting GitHub.
* **Adapter Conformance**: Validated against the official `tempus_ddb.testing.AdapterConformanceHarness` conformance suite.

---

## 🧪 Testing

```bash
pytest tests/ -v
```

---

## 📄 License

MIT License. Part of the [Tempus DDB](https://github.com/elbuilder77/tempus-ddb) ecosystem.
