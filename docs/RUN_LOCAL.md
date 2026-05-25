# Run Loopback locally — from-scratch runbook

Run the whole app (ADK/Gemini agent + UI) in one container on your machine and click through
it. The container talks directly to GitLab's official MCP server over HTTPS — no MCP sidecar.
~10 minutes cold. You need Docker and Google Cloud auth for Gemini, plus a one-time GitLab
OAuth step (that step uses the repo's Python venv; the container itself needs no host Python).

> Shortcut: if a `loopback-local` container is already running, just open
> http://localhost:8080. To do it yourself from scratch, follow the steps below
> (stop any running one first: `docker rm -f loopback-local`).

---

## 1. What you need (and how to check)

```bash
docker --version        # need Docker; any recent version
docker info             # must print info, NOT "Cannot connect" — the daemon must be running
gcloud --version        # need the Google Cloud CLI
```
- **Docker not installed / daemon off:** install Docker Desktop (https://www.docker.com/products/docker-desktop), open the app, wait for the whale icon to settle. Re-run `docker info`.
- **gcloud not installed:** https://cloud.google.com/sdk/docs/install (or `brew install --cask google-cloud-sdk`).

You also need:
- A **GitLab account** with access to the project you'll write to, and a **Duo trial** (the
  official MCP server is part of the GitLab Duo Agent Platform). No PAT needed — auth is OAuth.
- A **GitLab project ID** to write issues into. Use the clean demo project **`82508739`** (egg-labs-group/loopback-demo), or any project you own (its numeric ID is on the project's overview page).
- A **Google Cloud project** with the Vertex AI API enabled (your personal one is fine).

## 2. Google Cloud auth (so Gemini works)

```bash
gcloud auth login                       # browser login to your Google account
gcloud auth application-default login   # creates the credentials the container mounts (ADC)
# enable Gemini on your project if it isn't already (safe to run if it is):
gcloud services enable aiplatform.googleapis.com --project=mimetic-firefly-248609
```
This writes `~/.config/gcloud/application_default_credentials.json`, which the container
reads (mounted read-only) to call Gemini on your project. Nothing is uploaded anywhere.

> Simpler alternative (no gcloud): get a Gemini API key from https://aistudio.google.com/apikey,
> and in step 4 replace the three `GOOGLE_*` flags with a single `-e GEMINI_API_KEY=...`.

## 3. Authorize GitLab (one-time OAuth) + set values

```bash
# One-time browser authorization → writes .oauth_token.json (gitignored). Click "Authorize".
.venv/bin/python scripts/oauth_spike.py

export GITLAB_PROJECT_ID='82508739'             # clean demo project, or your own project ID
export GCP_PROJECT='mimetic-firefly-248609'     # your Google Cloud project
```
The OAuth token now lives in `.oauth_token.json`; `GITLAB_PROJECT_ID` / `GCP_PROJECT` are also
in your gitignored `.env`. (Re-run the spike only if the token is ever revoked.)

## 4. Build and run

```bash
cd /Users/muhammadegaa/code/rapid-agent
docker rm -f loopback-local 2>/dev/null    # clear any previous run
docker build -t loopback:local .           # ~3-5 min the first time
docker run --rm --name loopback-local -p 8080:8080 \
  -e GITLAB_OAUTH_TOKEN_JSON="$(cat .oauth_token.json)" \
  -e GITLAB_PROJECT_ID="$GITLAB_PROJECT_ID" \
  -e GOOGLE_GENAI_USE_VERTEXAI=true \
  -e GOOGLE_CLOUD_PROJECT="$GCP_PROJECT" \
  -e GOOGLE_CLOUD_LOCATION=global \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  loopback:local
```
Wait for the log to show **`Uvicorn running on http://0.0.0.0:8080`** (no MCP sidecar to wait for).

In another terminal, sanity-check, then open the app:
```bash
curl http://localhost:8080/api/health      # -> {"ok":true,"project":"82508739"}
open http://localhost:8080
```

## 5. Five-minute click-through (what "working" looks like)

1. **Landing.** You see "Stop letting customer pain rot in the support inbox." and a dropzone.
2. **Upload.** Click the dropzone (or drag) and choose
   `/Users/muhammadegaa/code/rapid-agent/data/sample_feedback.csv` (142 messages).
   - ✅ Working: the status pill switches to **"Analyzing"** and a terminal-style **step log**
     starts streaming on the right.
3. **The ~50s wait (expected).** Clustering + drafting 6 issues with Gemini takes ~50s. The
   step log streams the agent's reasoning the whole time: `ingest: loaded 142 signals` →
   `cluster_and_rank: 6 themes…` → `search_existing: …` → `draft_issues: drafted 6 issues`.
   - ✅ Working: log lines keep appearing. It is **not** frozen — that's the agent thinking.
4. **The approval gate (the moment).** An **amber banner** pulses in: *"The agent has paused
   for your approval."* Six issue cards appear — each with a title, priority badge, the actual
   customer quotes as evidence, repro steps, and suggested labels.
   - ✅ Working: **nothing has been created in GitLab yet.** The agent stopped and is waiting
     for you. This is the whole point.
5. **Reject one.** Click the green **"✓ Approved"** toggle on one card (e.g. *Search
   Performance*). It dims and strikes through; the big button changes to **"Approve & create 5."**
6. **Approve.** Click **"Approve & create 5."** Status → **"Creating issues"** (~15-20s).
7. **Result.** A green panel: **"5 issues created in GitLab,"** with rows `#N`, label chips,
   and **"open ↗"** links. The rejected card is listed under **"Rejected — not created."**
   - ✅ Working: click an **"open ↗"** link → a **real GitLab issue** opens, with the labels
     applied and the customer quotes in the description. The rejected one exists **nowhere**.
8. **(Optional) Second run — "it remembers."** Click **"New run,"** upload the same CSV again.
   This time the step log shows `search_existing: … → 1 related issue(s)` and the created
   issues get related-issue links (via `link_work_items`) to the ones from your first run.

**Your judgment checklist** — it's working correctly if:
- [ ] The step log streams the agent's reasoning (you can see it think).
- [ ] It **pauses** at the amber gate and creates nothing until you decide.
- [ ] Approved drafts become **real GitLab issues with labels and working links.**
- [ ] The rejected draft is **not** created.
- [ ] No crash, blank screen, or error at any step.

## 6. Stop and clean up

```bash
docker rm -f loopback-local        # stop + remove the container (the --rm also auto-removes on exit)
docker rmi loopback:local          # optional: remove the 726MB image
```
- Each run files ~5 real issues into your GitLab project. To reset the demo project before
  recording, delete them in GitLab (Issues → select → delete) or create a fresh project.
- Your gcloud ADC stays on your machine (harmless). Revoke with
  `gcloud auth application-default revoke` if you want.
