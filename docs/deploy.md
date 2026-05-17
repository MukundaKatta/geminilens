# Deploy to Cloud Run

The hackathon submission needs a hosted URL. Cloud Run is the cheapest path:
one container, scales to zero, free tier covers a demo.

## Prereqs

- `gcloud` CLI authed (`gcloud auth login`)
- A GCP project with billing on
- Vertex AI API enabled: `gcloud services enable aiplatform.googleapis.com`
- Cloud Run + Artifact Registry enabled:
  `gcloud services enable run.googleapis.com artifactregistry.googleapis.com`

## One-shot deploy

```bash
export PROJECT_ID=$(gcloud config get-value project)
export REGION=us-central1
export SVC=geminilens

gcloud run deploy "$SVC" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 3 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
```

Cloud Run does its own build with Cloud Build. The Dockerfile in the repo
root is what gets baked.

## Add Vertex AI permissions

Cloud Run uses a default service account that does NOT have Vertex AI access.
Grant the role:

```bash
SA=$(gcloud run services describe "$SVC" --region "$REGION" \
       --format='value(spec.template.spec.serviceAccountName)')
SA=${SA:-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')-compute@developer.gserviceaccount.com}

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA" \
  --role=roles/aiplatform.user
```

## Optional: Dynatrace exporter

If you also want production traces to flow to Dynatrace, set:

```bash
gcloud run services update "$SVC" --region "$REGION" \
  --set-env-vars "DT_ENV_URL=https://abc.live.dynatrace.com,DT_API_TOKEN=dt0c01..."
```

Wire it in code by passing `on_trace=DynatraceExporter().export_one` to the
observer (see `examples/export_to_dynatrace.py`).

## Verify

```bash
gcloud run services describe "$SVC" --region "$REGION" \
  --format='value(status.url)'
```

Open the URL, click "Ask Gemini" in the sidebar, watch the trace appear.

## Costs

Cold start ~5 seconds. Streaming traces are written to a per-instance volume
(`/data/traces.jsonl`), so each instance has its own view. For a hackathon
demo with one user (you, holding the camera), that's fine. For real
production, mount Cloud Storage or push every trace to Dynatrace via the
`on_trace` callback.

Typical demo session: < $0.05 in Cloud Run + a few cents in Vertex AI per
Gemini Flash call.
