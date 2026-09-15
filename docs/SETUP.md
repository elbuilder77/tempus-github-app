# Setup and Registration Guide: Tempus GitHub App

This guide explains how to register, install, and operate the Tempus GitHub App for credential-isolated, mediated execution.

---

## 1. Register the GitHub App

You can register the App manually or via the App Manifest (`manifest/app.yml`).

1. Go to **GitHub Settings → Developer settings → GitHub Apps → New GitHub App**.
2. **App Name**: Choose a unique name (e.g., `tempus-security-gate-acme`).
3. **Homepage URL**: `https://github.com/elbuilder77/tempus-ddb` (or your organization's URL).
4. **Permissions**:
   - **Repository permissions**:
     - **Issues**: `Read and write`
     - **Pull requests**: `Read and write`
     - **Metadata**: `Read-only` (implicit)
5. **Webhooks** (Optional):
   - If using the webhook service, provide your server URL and generate a secret string.
   - If using executor-only CLI mode, webhooks can be disabled.
6. Click **Create GitHub App**.

---

## 2. Generate RSA Private Key & Record IDs

1. In the newly created App's settings, scroll down to **Private keys** and click **Generate a private key**.
2. Download the `.pem` file and save it securely (e.g., `secrets/tempus-app.pem`).
3. Note the **Client ID** (e.g., `Iv1.xxxxxxxxxxxx`) and **App ID**.

> [!CAUTION]
> Never commit the `.pem` private key to source control. Ensure file permissions are restricted (`chmod 600` on Linux/macOS).

---

## 3. Install the App on Repositories

1. In the App settings sidebar, click **Install App**.
2. Select your user account or organization, and choose **Only select repositories**.
3. Select the target repositories (e.g., `owner/repository`).
4. Complete the installation and note the **Installation ID** from the URL (e.g., `https://github.com/settings/installations/12345678`).

---

## 4. Execution Boundary with Tempus DDB

The GitHub App RSA key remains strictly inside the mediated executor process. The requesting agent **never** receives GitHub tokens or the App private key.

1. **Agent signs Intent**: Agent declares action (e.g. `github.create_issue`) signed with Ed25519.
2. **Gate authorizes Permit**: Tempus Gate checks tenant policy and issues an expiring, single-use signed Permit (`ALLOWED`).
3. **Mediated Executor executes**:
   ```bash
   tempus-github-app-executor \
     --permit permit.json \
     --executor-db executor.db \
     --executor-keyfile executor.keys.json \
     --gate-id GATE_PUBLIC_KEY \
     --tenant-id TENANT_ID \
     --app-client-id Iv1.xxxxxxxx \
     --app-private-key secrets/tempus-app.pem \
     --installation-id 12345678 \
     --repository owner/repository
   ```
   Or using `.env`:
   ```bash
   tempus-github-app-executor --permit permit.json
   ```
4. **Receipt produced**: Both executor and Gate sign the outcome, producing a mathematical audit receipt.
5. **Offline trace verification**:
   ```bash
   tempus verify-trace --action-id <ACTION_ID>
   ```

---

## 5. Webhook Server Setup (Optional)

To receive webhooks (e.g., issue opened, PR created):

```bash
tempus-github-app-server --secret GITHUB_WEBHOOK_SECRET --port 8000
```

Configure your GitHub App's Webhook URL to point to `https://your-domain.com/webhook` and ensure HMAC verification is enabled.
