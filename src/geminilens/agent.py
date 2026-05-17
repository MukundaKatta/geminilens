"""A small reference agent that uses Gemini 2.5 + a couple of tools, fully
instrumented via GeminiObserver. This is what the dashboard tails."""

from __future__ import annotations

import os
import time
from typing import Any

from geminilens.guard import EgressGuard
from geminilens.observer import GeminiObserver, Trace


def _try_import_gemini():
    try:
        from google import genai  # type: ignore
        return genai
    except ImportError:
        return None


class ResearchAgent:
    """Toy research agent: takes a question, may call a tool that fetches
    facts from an allowlisted source, then answers with Gemini."""

    def __init__(
        self,
        observer: GeminiObserver,
        model: str = "gemini-2.5-flash",
        guard: EgressGuard | None = None,
        project: str | None = None,
        location: str = "us-central1",
    ):
        self.observer = observer
        self.model = model
        self.guard = guard or EgressGuard(allow=["en.wikipedia.org"])
        self._genai = _try_import_gemini()
        if self._genai is None:
            self._client = None
        else:
            kwargs: dict[str, Any] = {}
            project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
            if project:
                kwargs["vertexai"] = True
                kwargs["project"] = project
                kwargs["location"] = location
            self._client = self._genai.Client(**kwargs)

    def _fetch_wiki_summary(self, topic: str) -> str:
        client = self.guard.client(timeout=10.0)
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ', '_')}"
        resp = client.get(url, headers={"accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        return data.get("extract", "")[:1200]

    def answer(self, question: str, use_tool: bool = True) -> str:
        with self.observer.trace(model=self.model, prompt=question, agent="research") as tr:
            context = ""
            if use_tool:
                topic = question.split("?")[0].split()[-1]
                try:
                    context = self.observer.run_tool(
                        tr, "wiki_summary", self._fetch_wiki_summary, topic
                    )
                except Exception as e:
                    context = f"(tool failed: {e})"

            if self._client is None:
                # Offline / no-GCP fallback so the demo still produces a trace.
                fake_resp = self._fallback_response(question, context)
                tr.response = fake_resp
                tr.input_tokens = len(question.split()) + len(context.split())
                tr.output_tokens = len(fake_resp.split())
                return fake_resp

            return self._call_gemini(tr, question, context)

    def _call_gemini(self, tr: Trace, question: str, context: str) -> str:
        prompt = (
            "You are a careful researcher. Answer the user using the supplied context "
            "if it is relevant; otherwise say you don't know.\n\n"
            f"CONTEXT:\n{context}\n\nQUESTION: {question}"
        )
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        self.observer.record_response(tr, response)
        return tr.response or (response.text or "")

    @staticmethod
    def _fallback_response(question: str, context: str) -> str:
        if context:
            head = context.split(".")[0]
            return f"(offline-fallback) Based on context: {head}."
        return "(offline-fallback) I don't have GCP credentials configured."


def simulate(observer: GeminiObserver, n: int = 25) -> None:
    """Generate synthetic traces so the dashboard has data without burning
    GCP credits. Useful for the live demo recording."""
    import random

    topics = ["Python", "Rust", "Kubernetes", "Gemini", "Vector_database", "Anthropic"]
    for i in range(n):
        with observer.trace(model="gemini-2.5-flash", prompt=f"sim-{i}", scenario="demo") as tr:
            time.sleep(random.uniform(0.01, 0.05))
            tr.input_tokens = random.randint(200, 1500)
            tr.output_tokens = random.randint(50, 800)
            tr.cached_tokens = random.randint(0, tr.input_tokens // 3)
            tr.response = f"Synthetic answer about {random.choice(topics)}"
