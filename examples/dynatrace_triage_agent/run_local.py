"""Optional programmatic run for embedding the agent (for example behind Streamlit).

Primary run path is the ADK CLI:  adk run dynatrace_triage_agent
This file shows the runner API. Confirm it against https://google.github.io/adk-docs/ .

Run from the parent directory:
    python -m dynatrace_triage_agent.run_local "what blew up in the last hour?"
"""

import asyncio
import sys

from dotenv import load_dotenv

# Load .env before importing the agent: agent.py reads DT_* / TRIAGE_MODEL at import time.
load_dotenv()

from google.genai import types  # noqa: E402

from .agent import root_agent  # noqa: E402


async def ask(question: str) -> str:
    # Confirm the current runner API; older ADK used MCPToolset.from_server and a
    # different runner construction.
    from google.adk.runners import InMemoryRunner

    runner = InMemoryRunner(agent=root_agent, app_name="dynatrace-triage")
    session = await runner.session_service.create_session(
        app_name="dynatrace-triage", user_id="local"
    )
    content = types.Content(role="user", parts=[types.Part(text=question)])

    chunks: list[str] = []
    async for event in runner.run_async(
        user_id="local", session_id=session.id, new_message=content
    ):
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if part.text:
                    chunks.append(part.text)
    return "".join(chunks)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What are the top open problems right now?"
    print(asyncio.run(ask(q)))
