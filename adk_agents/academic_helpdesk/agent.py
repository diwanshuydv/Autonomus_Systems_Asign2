"""Entry point for the ADK developer UI:  adk web adk_agents   (run from the repository root)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from helpdesk.agents import build_agent  # noqa: E402

root_agent = build_agent(os.getenv("HELPDESK_MODE", "multi"))
