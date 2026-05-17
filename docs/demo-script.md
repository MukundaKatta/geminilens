# 3-minute demo script

Tested cadence: roughly 30 seconds per beat. Record at 1080p, mic on, no
face-cam needed.

## 0:00 to 0:20  Setup

Voice: "GeminiLens is local-first observability for Vertex AI Gemini agents.
You import one library, run one Streamlit page, and you can see cost,
latency, drift, and a tool audit log for every call your agent makes."

On screen: terminal at the project root, then `git log --oneline | head -5`
to show the repo is real, then `tree -L 2 src app` to show the layout.

## 0:20 to 0:50  Library import

Voice: "Five lines wrap any Gemini client."

On screen: open `examples/quickstart.py` in an editor. Highlight the imports
and the `with observer.trace(...)` block.

Then run it:
```
PYTHONPATH=src python examples/quickstart.py
```
Show the printed drift report.

## 0:50 to 1:30  Start the dashboard with real Vertex AI

Voice: "Let me run it for real against Vertex AI."

On screen:
```
export GOOGLE_CLOUD_PROJECT=$PROJECT
PYTHONPATH=src streamlit run app/dashboard.py
```

Browser opens. Type a question in the sidebar, click Ask Gemini.

The dashboard updates: a new row appears in the trace table, cost is fractions
of a cent, latency around 1-2 seconds.

## 1:30 to 2:10  Drift demo

Voice: "Now the interesting part. I'll inject a noisy baseline so the drift
metric has something to chew on."

On screen: click "Generate 25 synthetic traces" twice, then ask Gemini three
more questions with bigger prompts. The drift cards turn from green to amber.

Voice: "Output drift is 1.4x. The agent is producing longer responses than
the baseline. If you saw this in prod you'd open the trace and look."

## 2:10 to 2:40  Egress guard

Voice: "Every tool call goes through an egress allowlist. If the agent calls
a host that isn't approved, the call raises and the URL goes into the audit
log."

On screen: open a Python REPL, do the EgressGuard example from the README
that tries to hit `evil.example.com`. Show the `EgressBlocked` exception and
the `violations()` list.

## 2:40 to 3:00  Wrap

Voice: "Apache 2.0, all the code is in the repo, the cost table is in the
repo, the drift math is in the repo. Built for the Google Cloud Rapid Agent
Hackathon, Dynatrace track."

On screen: github.com/MukundaKatta/geminilens
