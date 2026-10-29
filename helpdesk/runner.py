"""Programmatic interface around the ADK runner, used by the CLI and the evaluation harness."""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
import warnings

from google.adk.runners import InMemoryRunner
from google.genai import types

from . import config
from .agents import build_agent
from .tools import log_unanswered_question

warnings.filterwarnings("ignore")
logging.getLogger("google_adk").setLevel(logging.ERROR)
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

APP_NAME = "academic_helpdesk"
REFUSAL_PATTERNS = re.compile(
    r"(don'?t know|do not know|cannot answer|can'?t answer|unable to (answer|find)|not able to answer|"
    r"no information|outside (my|the) scope|out of scope|could not find)", re.I)
THINK_TAGS = re.compile(r"<think>.*?</think>", re.S)


def is_refusal(text: str) -> bool:
    return bool(REFUSAL_PATTERNS.search(text or ""))


class HelpdeskRunner:
    def __init__(self, mode: str = "multi", model: str | None = None, user_id: str = "student"):
        import litellm
        litellm.suppress_debug_info = True

        self.mode = mode
        self.model = model or config.LLM_MODEL
        self.user_id = user_id
        self.agent = build_agent(mode, self.model)
        self.runner = InMemoryRunner(agent=self.agent, app_name=APP_NAME)
        self.session_id: str | None = None

    async def new_session(self) -> str:
        session = await self.runner.session_service.create_session(
            app_name=APP_NAME, user_id=self.user_id, session_id=str(uuid.uuid4()))
        self.session_id = session.id
        return session.id

    async def ask(self, question: str, fresh_session: bool = False) -> dict:
        if fresh_session or self.session_id is None:
            await self.new_session()
        start = time.time()
        agents, tool_calls, tool_results, texts = [], [], [], []
        logged_by_agent = False
        error = None
        try:
            async for event in self.runner.run_async(
                    user_id=self.user_id, session_id=self.session_id,
                    new_message=types.Content(role="user", parts=[types.Part(text=question)])):
                if event.author and event.author != "user" and (not agents or agents[-1] != event.author):
                    agents.append(event.author)
                if event.custom_metadata and event.custom_metadata.get("logged_unanswered"):
                    logged_by_agent = True
                if event.author == "router_agent":
                    continue  # the router's label is internal, never the answer
                for part in (event.content.parts if event.content else None) or []:
                    if part.function_call:
                        tool_calls.append({"agent": event.author, "name": part.function_call.name,
                                           "args": dict(part.function_call.args or {})})
                    elif part.function_response:
                        tool_results.append({"name": part.function_response.name,
                                             "response": part.function_response.response})
                    elif part.text and not part.thought:
                        texts.append((event.author, part.text))
        except Exception as exc:  # keep the evaluation going if the small model emits a malformed call
            error = f"{type(exc).__name__}: {exc}"

        answer = THINK_TAGS.sub("", texts[-1][1]).strip() if texts else ""
        if not answer:
            answer = config.REFUSAL_TEXT if error is None else f"[error] {error}"
        refused = is_refusal(answer)
        if refused and answer.startswith("I'm sorry"):
            # a plain refusal has no source; small models sometimes append an invented "[Source: ...]"
            answer = re.sub(r"\s*\[Source:[^\]]*\]", "", answer).strip()
        logged =logged_by_agent or any(c["name"] == "log_unanswered_question" for c in tool_calls)
        if refused and not logged:
            # Guarantee the human-handoff log even if the model forgot to call the tool.
            log_unanswered_question(question, reason=f"refused by {agents[-1] if agents else 'agent'} (auto-logged)")
            logged = True
        return {
            "question": question, "answer": answer, "agents": agents,
            "tool_calls": tool_calls, "tool_results": tool_results,
            "route": next((a for a in agents if a.endswith("_agent") and a != "router_agent"), None),
            "refused": refused, "logged": logged, "error": error,
            "latency_s": round(time.time() - start, 2), "mode": self.mode, "model": self.model,
        }

    def ask_sync(self, question: str, fresh_session: bool = False) -> dict:
        return asyncio.run(self.ask(question, fresh_session))
