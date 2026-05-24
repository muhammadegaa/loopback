# Deploying Loopback to Cloud Run

One container serves everything (Node MCP server + Python ADK agent/API + static UI),
so there is **one public URL**. Gemini runs on the deploy project via the Cloud Run
service account (Vertex / ADC) — no API key. The only secret is the GitLab PAT, kept in
Secret Manager. Nothing secret is in the repo or the image.

> Status: held until the $100 hackathon credits are approved and a credited project
> exists. The container is built and verified locally; the steps below are the deploy.

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
```bash
printf '%s' 'glpat-YOUR-PAT' | gcloud secrets create loopback-gitlab-pat --data-file=-
PROJNUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
SA="$PROJNUM-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding loopback-gitlab-pat \
  --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$SA" --role=roles/aiplatform.user   # Gemini on this project
```

## 3. Deploy (build + run, one command)
```bash
gcloud run deploy loopback --source . --region=us-central1 --allow-unauthenticated \
  --memory=2Gi --cpu=2 --cpu-boost --no-cpu-throttling \
  --min-instances=1 --max-instances=1 --timeout=600 \
  --set-env-vars=GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=global,GITLAB_PROJECT_ID=82489785,GITLAB_API_URL=https://gitlab.com/api/v4 \
  --set-secrets=GITLAB_TOKEN=loopback-gitlab-pat:latest
```
The printed **Service URL** is the public URL.

### Why these flags
- `--no-cpu-throttling` + `--min-instances=1 --max-instances=1`: a run executes in a
  background thread and the UI polls it; a single always-on instance keeps that thread
  alive and keeps all polls hitting the same in-memory run state. (To scale out later,
  move run state to a shared store — Firestore/Redis.)
- `--memory=2Gi`: Node MCP server + Python ADK + Gemini client.

## Local verification (no cloud cost)
```bash
docker build -t loopback .
docker run -p 8080:8080 \
  -e GITLAB_TOKEN=glpat-... -e GITLAB_PROJECT_ID=82489785 \
  -e GOOGLE_GENAI_USE_VERTEXAI=true -e GOOGLE_CLOUD_PROJECT=mimetic-firefly-248609 \
  -e GOOGLE_CLOUD_LOCATION=global \
  -v ~/.config/gcloud:/root/.config/gcloud:ro \
  loopback
# open http://localhost:8080
```
