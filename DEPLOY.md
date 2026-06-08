# Deploying Loopback to Cloud Run

One Python container serves everything (ADK agent/API + static UI) and talks **directly
to GitLab's official MCP server** (`gitlab.com/api/v4/mcp`) over HTTPS - no MCP sidecar,
no Node at runtime. So there is **one public URL**. Gemini runs on the deploy project via
the Cloud Run service account (Vertex / ADC) - no API key. The only secret is the GitLab
**OAuth token blob**, kept in Secret Manager. Nothing secret is in the repo or the image.

> Status: held until the $100 hackathon credits are approved and a credited project
> exists. The agent + official-server integration are verified locally end to end
> (`scripts/demo_run.py`); the steps below are the deploy.

## 0. One-time: authorize GitLab (local, browser)
The official server uses OAuth. Authorize once to mint the refresh token the container
will use (a human clicks "Authorize" - fully compatible with this HITL product):
```bash
.venv/bin/python scripts/oauth_spike.py        # opens a browser; writes .oauth_token.json
```
`.oauth_token.json` now holds access_token, refresh_token, client_id, token_endpoint.

## 1. Project + APIs (once)
```bash
PROJECT=loopback-hackathon          # fresh project, NOT the personal dev one
gcloud projects create "$PROJECT"
gcloud billing projects link "$PROJECT" --billing-account=<CREDITED_BILLING_ID>
gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com aiplatform.googleapis.com secretmanager.googleapis.com
```

## 2. Secret + IAM (once)
The token blob lives in Secret Manager. The app reads the latest version and writes a new
version each time it refreshes (every ~2h), so the rotated refresh token survives restarts
across the June 22–July 6 judging window.
```bash
gcloud secrets create loopback-oauth --data-file=.oauth_token.json
PROJNUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
SA="$PROJNUM-compute@developer.gserviceaccount.com"
# read the token...
gcloud secrets add-iam-policy-binding loopback-oauth \
  --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor
# ...and write back rotated tokens
gcloud secrets add-iam-policy-binding loopback-oauth \
  --member="serviceAccount:$SA" --role=roles/secretmanager.secretVersionAdder
# Gemini on this project
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$SA" --role=roles/aiplatform.user
```

## 3. Deploy (build + run, one command)
```bash
PROJNUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
gcloud run deploy loopback --source . --region=us-central1 --allow-unauthenticated \
  --memory=2Gi --cpu=2 --cpu-boost --no-cpu-throttling \
  --min-instances=1 --max-instances=1 --timeout=600 \
  --set-env-vars=GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=global,GITLAB_PROJECT_ID=82508739,GEMINI_MODEL=gemini-3-flash-preview,GITLAB_OAUTH_SECRET_RESOURCE=projects/$PROJNUM/secrets/loopback-oauth
```
The printed **Service URL** is the public URL. The agent reads/refreshes the OAuth token
from `GITLAB_OAUTH_SECRET_RESOURCE` - no `--set-secrets` needed for it.

> Simpler but less durable alternative: skip `secretVersionAdder` and pass the token as a
> static env instead - `--set-secrets=GITLAB_OAUTH_TOKEN_JSON=loopback-oauth:latest`. The
> app still refreshes in-memory, but a restart after a refresh would need the secret
> re-seeded. The `GITLAB_OAUTH_SECRET_RESOURCE` path above avoids that.

### Why these flags
- `--no-cpu-throttling` + `--min-instances=1 --max-instances=1`: a run executes in a
  background thread and the UI polls it; a single always-on instance keeps that thread
  alive and keeps all polls hitting the same in-memory run state. (To scale out later,
  move run state to a shared store - Firestore/Redis.)
- `--memory=2Gi`: Python ADK + the Gemini client. (No Node at runtime anymore.)

## Local verification (no cloud cost)
Needs the Docker daemon running. Pass the OAuth blob as JSON (no Secret Manager locally):
```bash
docker build -t loopback .
docker run -p 8080:8080 \
  -e GITLAB_OAUTH_TOKEN_JSON="$(cat .oauth_token.json)" \
  -e GITLAB_PROJECT_ID=82508739 \
  -e GOOGLE_GENAI_USE_VERTEXAI=true -e GOOGLE_CLOUD_PROJECT=mimetic-firefly-248609 \
  -e GOOGLE_CLOUD_LOCATION=global \
  -v ~/.config/gcloud:/root/.config/gcloud:ro \
  loopback
# open http://localhost:8080  (curl http://localhost:8080/api/health -> {"ok":true,...})
```
