# Azure Container Apps deployment

## Prerequisites
- Azure CLI logged in
- Resource groups for dev/staging/prod
- ACR + Storage account available per environment

## Variables
```bash
SUB=<subscription-id>
LOC=australiaeast
APP=vic-rego-estimator
RG_DEV=rg-vic-rego-dev
RG_STG=rg-vic-rego-stg
RG_PRD=rg-vic-rego-prd
ACR=vicregoacr
IMG=$ACR.azurecr.io/$APP:$(git rev-parse --short HEAD)
STORAGE=vicregodata
```

## Build & push image
```bash
az account set --subscription $SUB
az acr login -n $ACR
docker build -f deploy/Dockerfile -t $IMG .
docker push $IMG
```

## Create Blob container
```bash
az storage container create --name fee-snapshots --account-name $STORAGE --auth-mode login
```

## Deploy to ACA (repeat per env)
```bash
ENV_NAME=aca-dev
RG=$RG_DEV
az containerapp env create -g $RG -n $ENV_NAME -l $LOC

BLOB_CONN=$(az storage account show-connection-string -g $RG --name $STORAGE --query connectionString -o tsv)

az containerapp create \
  -g $RG \
  -n $APP \
  --environment $ENV_NAME \
  --image $IMG \
  --target-port 8080 \
  --ingress external \
  --registry-server $ACR.azurecr.io \
  --env-vars AZURE_BLOB_CONNECTION_STRING="$BLOB_CONN" FEE_SNAPSHOT_BLOB_CONTAINER=fee-snapshots FEE_SNAPSHOT_BLOB_NAME=vic/latest.json AUTH_ENABLED=true OIDC_ISSUER="https://<tenant>/" OIDC_AUDIENCE="<api-audience>" OIDC_CLIENT_ID="<client-id>" OIDC_JWKS_URL="https://<tenant>/.well-known/jwks.json" OIDC_REQUIRED_SCOPE="mcp:invoke"
```

## Promote same image to staging/prod
Run the same `az containerapp update` with RG/ENV per stage.

## Connect to ChatGPT Apps
1. In ChatGPT, open **Create > Connectors / MCP**.
2. Add server URL: `https://<containerapp-fqdn>/mcp`.
3. Verify tool discovery shows:
   - normalize_vehicle_request
   - get_fee_snapshot
   - estimate_registration_cost
   - explain_assumptions
4. Confirm widget template path is `ui://widget/index.html` and endpoint serves `/widget/index.html`.

## Production app review checklist
Before promoting to production, verify the following ChatGPT app quality controls:

- **Privacy disclosure**
  - Logged identifiers are documented in `request_audit_log`: `request_id`, source IP (`client_ip`), auth subject (`authenticated_sub`), method/path, status, and latency.
  - Retain logs for **30 days** in Azure Log Analytics and restrict access with least-privilege RBAC roles (`Log Analytics Reader` for support, write access only for platform SRE).
- **Abuse controls**
  - Set `MCP_RATE_LIMIT_REQUESTS` and `MCP_RATE_LIMIT_WINDOW_SECONDS` per environment (`60/60` baseline; increase only with load testing evidence).
  - Verify `/mcp` returns HTTP 429 and `Retry-After` when limits are exceeded.
- **Authentication failure UX**
  - `WWW-Authenticate` challenge includes actionable details (`authorization_uri`, `resource`, `client_id`, `error`, `error_description`, and optional `scope`).
  - ChatGPT connector setup copy should map failures to user actions:
    - `invalid_request`: reconnect and re-authorize the connector.
    - `invalid_token`: sign in again and retry.
    - `insufficient_scope`: request the required scope and reconnect.
- **Error UX states**
  - Exercise unsupported method (400), unknown tool (404), rate limit (429), and internal error (500).
  - Confirm each error response includes concise `recovery_steps` (retry, reconnect auth, contact support with request ID).
- **Correlation and auditability**
  - Verify `X-Request-ID` is accepted/echoed when provided and generated when missing.
  - Include request IDs in incident runbooks so support can trace requests quickly.

### Incident runbook snippet (support)
1. Ask user for timestamp and `X-Request-ID` from connector logs.
2. Query Log Analytics by `request_id` to retrieve method/path, auth subject, status, and latency.
3. If `status=401/403`, guide user through connector re-auth.
4. If `status=429`, advise retry after `Retry-After` interval and evaluate rate limit sizing.
5. If `status=500`, escalate to on-call with request ID and correlated log entry.
