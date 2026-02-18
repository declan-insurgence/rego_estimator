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
  --env-vars AZURE_BLOB_CONNECTION_STRING="$BLOB_CONN" FEE_SNAPSHOT_BLOB_CONTAINER=fee-snapshots FEE_SNAPSHOT_BLOB_NAME=vic/latest.json
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
