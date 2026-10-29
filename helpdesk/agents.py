"""Agent definitions: a single-agent baseline and the multi-agent helpdesk.

Multi-agent layout:

    helpdesk_orchestrator ── router_agent    (LLM intent classifier: policy / schedule / email / out_of_scope)
                          ├─ policy_agent    (RAG over regulations / circulars)
                          ├─ schedule_agent  (timetable CSV lookups)
                          └─ email_agent     (instructor lookup + email drafting)

Two orchestration strategies are available:
  * "router"   (default) - a custom ADK agent asks the router LLM for a label and hands the
               conversation to that specialist. Robust with small models.
  * "transfer" - ADK's native LLM-driven delegation (the orchestrator calls transfer_to_agent).
               qwen3:1.7b returns empty replies for ADK's enum-typed transfer tool, so this mode
               is only usable with larger models such as qwen3:8b / llama3.1:8b.
"""
from __future__ import annotations

import re
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models import LlmRequest, LlmResponse
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from . import config
from .tools import (draft_email, find_course_mention, get_course_info, get_instructor_contact, get_slot_timings,
                    list_courses, log_unanswered_question, search_academic_documents)

REFUSE = (f'call log_unanswered_question with the question, then reply exactly: "{config.REFUSAL_TEXT}" '
          "Never guess.")

ROUTING_GUIDE = """\
- policy_agent: academic rules and regulations, attendance, exams, grading, credits, degree requirements,
  open/programme elective credit requirements, leave rules, registration, programmes, curriculum, circulars,
  academic calendar dates (semester start, exam weeks, deadlines, holidays), fee payment, hostel rules.
- schedule_agent: slot or timing of a course, timetable, courses offered/floated this semester, counting or
  listing electives of a department, who teaches a course.
- email_agent: writing or drafting an email to an instructor (leave, sick leave, make-up exam), an
  instructor's email ID."""

OUT_OF_SCOPE = ("Out of scope means anything that is not about IIT Jodhpur academics or institute notices, e.g. "
                "dining, food, transport or how to reach the campus, weather, sports, placements, general knowledge.")

POLICY_INSTRUCTION = f"""You are the Policy Agent of the IIT Jodhpur Academic Helpdesk. You answer questions about
academic rules and regulations, programmes, curriculum, credits, attendance, exams, grading, leave, the academic
calendar, registration and fee notices, and institute circulars.

Steps:
1. ALWAYS call search_academic_documents first, with the student's question as the query.
2. If the tool status is "no_relevant_documents", or the passages do not contain the answer, {REFUSE}
3. Otherwise answer exactly what was asked in 1-3 short sentences using ONLY facts stated in the passages.
   Copy numbers exactly and do not list other figures that were not asked for.
   Passages are ordered newest document first. If passages disagree, follow the most recent document
   (a circular overrides the older regulations) and say that it supersedes the older rule.
4. End the answer with the citation of the passage you used, exactly as given, e.g. [Source: <title>, p. <n>].
"""

SCHEDULE_INSTRUCTION = f"""You are the Schedule Agent of the IIT Jodhpur Academic Helpdesk. You answer questions
about this semester's timetable and the courses floated.

Tools:
- get_course_info(course): for ANY question about one course (its slot, class timings, credits, L-T-P,
  category or instructor). Pass the course code or title exactly as the student wrote it. Never guess a slot.
- list_courses(department, level, category): to COUNT or LIST courses, e.g. "how many 400 level electives
  has Humanities floated" -> list_courses(department="Humanities", level=400, category="elective").
- get_slot_timings(slot): only when the student names a slot letter, e.g. "When is slot H?".

ALWAYS call a tool before answering. Answer only with facts from the tool result (for counts, give the
"count" and list the course codes) and end with the citation from the tool result.
If the tool returns not_found, {REFUSE}
"""

EMAIL_INSTRUCTION = f"""You are the Email Agent of the IIT Jodhpur Academic Helpdesk. You write email DRAFTS from a
student to a course instructor. Emails are never sent; the student reviews the draft.

- To write an email, call draft_email(course, request_type, reason, num_days, dates, exam).
  request_type is 'sick_leave' (illness), 'leave' (other leave), 'makeup_exam' (missed exam) or 'other'.
  Fill reason, num_days, dates and exam only with what the student said; leave the rest empty/0.
- If the student only asks for an instructor's email or contact, call get_instructor_contact(course).

After the tool returns, tell the student the draft is ready for review and was NOT sent.
If the tool returns not_found, {REFUSE}
"""

ORCHESTRATOR_INSTRUCTION = f"""You are the Orchestrator of the IIT Jodhpur Academic Helpdesk. You do not answer
academic questions yourself: you call transfer_to_agent to hand the question to the right specialist.

{ROUTING_GUIDE}

{OUT_OF_SCOPE} For an out-of-scope question do not transfer: {REFUSE}
"""

ROUTER_INSTRUCTION = f"""You classify questions sent to the IIT Jodhpur Academic Helpdesk. Reply with exactly one
label and nothing else:

policy        - academic rules and regulations, attendance, exams, grading, credits, degree requirements,
                how many credits of any kind are REQUIRED for a degree, leave rules, registration,
                programmes, curriculum, circulars, academic calendar dates (semester start, exam weeks,
                deadlines, holidays), fee payment, hostel rules.
schedule      - slot or class timing of a specific course or slot letter, courses OFFERED/floated THIS
                SEMESTER, counting or listing the courses a department offers now, who teaches a course.
email         - writing or drafting an email/letter to an instructor (leave, sick leave, make-up exam), or
                asking for an instructor's email ID.
out_of_scope  - anything else. {OUT_OF_SCOPE}

Examples:
"What grade points does an A- carry?" -> policy
"Can I take leave for a medical reason?" -> policy
"What is the minimum CGPA to stay in the programme?" -> policy
"How many open elective credits are needed to graduate?" -> policy
"When do classes start next semester?" -> policy
"When are the minor exams?" -> policy
"Is 2 October a holiday?" -> policy
"When does the Deep Learning class meet?" -> schedule
"How many open electives are floated this semester?" -> schedule
"Mail my professor of CSL3010 that I was sick" -> email
"Where can I eat on campus?" -> out_of_scope
"How do I get to the airport?" -> out_of_scope
"""

SINGLE_INSTRUCTION = f"""You are the IIT Jodhpur Academic Helpdesk. You answer questions about academic rules and
regulations, programmes, curriculum, the semester timetable and course instructors, and you draft emails to
instructors. Pick the right tool:
- search_academic_documents: rules, regulations, attendance, exams, grading, credits, leave, circulars.
- get_course_info / get_slot_timings: slot, timings, credits or instructor of a course.
- list_courses(department, level, category): count or list courses floated this semester.
- get_instructor_contact / draft_email: instructor email, or an email draft for leave / make-up exams
  (request_type 'sick_leave', 'leave', 'makeup_exam' or 'other'). Drafts are never sent.

ALWAYS call a tool before answering and use ONLY facts from tool results. If passages disagree, the most
recent document wins. End every answer with the citation(s) given by the tool, e.g. [Source: <title>, p. <n>].
For email drafts show To, Subject and Body as returned and say the draft was not sent.
{OUT_OF_SCOPE} For out-of-scope questions, or when the tools return nothing relevant, {REFUSE}
"""


def build_model(model_name: str | None = None, think: bool = False) -> LiteLlm:
    name = model_name or config.LLM_MODEL
    extra = {}
    if name.startswith(("ollama", "ollama_chat")):
        extra["num_ctx"] = 8192  # Ollama's default 4k window is too small for tools + passages
        if "qwen3" in name or "deepseek-r1" in name:
            extra["think"] = think
    return LiteLlm(model=name, timeout=config.REQUEST_TIMEOUT, **extra)


def _gen_config() -> types.GenerateContentConfig:
    # The output cap (thinking tokens included) matters: small models occasionally loop forever.
    return types.GenerateContentConfig(temperature=config.TEMPERATURE, max_output_tokens=config.MAX_OUTPUT_TOKENS)


def build_single_agent(model_name: str | None = None) -> LlmAgent:
    return LlmAgent(
        name="helpdesk_single_agent",
        model=build_model(model_name, think=config.THINK == "all"),
        description="Single-agent academic helpdesk with all tools.",
        instruction=SINGLE_INSTRUCTION,
        tools=[search_academic_documents, get_course_info, get_slot_timings, list_courses,
               get_instructor_contact, draft_email, log_unanswered_question],
        generate_content_config=_gen_config(),
        after_tool_callback=remember_email_draft,
        after_model_callback=render_email_draft,
    )


def _tool_already_called(llm_request: LlmRequest) -> bool:
    """True if a tool has responded since the student's latest message."""
    for content in reversed(llm_request.contents or []):
        parts = content.parts or []
        if any(p.function_response for p in parts):
            return True
        if content.role == "user" and any(p.text for p in parts):
            return False
    return False


def force_document_search(callback_context: CallbackContext, llm_request: LlmRequest) -> LlmResponse | None:
    """Small models often answer (or refuse) without retrieving. On the first model call of a turn,
    skip the LLM and emit the search_academic_documents call ourselves; ADK then executes the tool
    normally and the LLM writes the answer from the returned passages."""
    if _tool_already_called(llm_request):
        return None
    user = callback_context.user_content
    question = next((p.text for p in (user.parts if user else []) if p.text), "")
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(
        function_call=types.FunctionCall(name="search_academic_documents", args={"query": question}))]))


def render_email_draft(callback_context: CallbackContext, llm_response: LlmResponse) -> LlmResponse | None:
    """Show the draft exactly as the tool produced it; small models tend to paraphrase or drop the body."""
    if not llm_response.content or any(p.function_call for p in llm_response.content.parts or []):
        return None
    draft = callback_context.state.get("temp:last_email_draft")
    if not draft:
        return None
    lines = ["Here is a draft email for you to review. It has NOT been sent.", "",
             f"To: {draft['to']}", f"Subject: {draft['subject']}", "", draft["body"].rstrip(), "",
             f"(Draft saved at {draft['saved_to']})"]
    if draft.get("policy_note"):
        lines += ["", f"Note: {draft['policy_note']}"]
    lines += ["", draft["citation"]]
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text="\n".join(lines))]))


def remember_email_draft(tool, args, tool_context, tool_response):
    if tool.name == "draft_email" and isinstance(tool_response, dict) and tool_response.get("status") == "drafted":
        tool_context.state["temp:last_email_draft"] = tool_response
    return None


def _strong_document_match(question: str) -> bool:
    from .rag import get_retriever
    hits = get_retriever().search(question)
    return bool(hits) and max(h["similarity"] for h in hits) >= config.OVERRIDE_SIMILARITY


TIMETABLE_WORDS = re.compile(r"\bslots?\b|float|offer|elective|\bcourses\b|teach|instructor|professor|faculty|"
                             r"lecture|\blab\b|tutorial|class(es)? (time|timing|meet)|\bmeets?\b", re.I)


def _about_timetable(question: str) -> bool:
    """The schedule agent only knows the course timetable. Questions with no course, slot or course
    offering in them ("When are the minor exams?") are academic-calendar questions for the documents."""
    return bool(re.search(r"\b(?:[A-Z]{2,3}\d{4}|[A-Z]{3} \d{4})\b", question.upper())  # CSL7570, not "AY 2026"
                or find_course_mention(question)
                or TIMETABLE_WORDS.search(question))


EMAIL_WORDS = re.compile(r"e-?mail|\bmail|\bwrite|\bdraft|\bletter|\bcompose|\bcontact|\bmessage", re.I)


def _about_email(question: str) -> bool:
    """The email agent writes drafts and looks up addresses. "To whom should I address a leave
    application?" is a rules question, not a drafting request."""
    return bool(EMAIL_WORDS.search(question))


def guard_slot_lookup(tool, args, tool_context):
    """get_slot_timings needs a slot name. When the student asked about a course rather than a
    slot, small models invent one (for "Which lab slot does CSL2010 have?" qwen3:1.7b called
    get_slot_timings("L2")). In that case answer from the course record instead."""
    if tool.name != "get_slot_timings":
        return None
    user = tool_context.user_content
    question = next((p.text for p in (user.parts if user else []) if p.text), "")
    course = find_course_mention(question)
    return get_course_info(course) if course else None


class HelpdeskOrchestrator(BaseAgent):
    """Custom ADK agent: runs the router LLM, then delegates the turn to the chosen specialist."""

    router: LlmAgent

    def __init__(self, name: str, router: LlmAgent, specialists: list[LlmAgent]):
        super().__init__(name=name, description="Routes student questions to the right specialist agent.",
                         router=router, sub_agents=[router, *specialists])

    @staticmethod
    def parse_route(text: str) -> str:
        text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).lower()
        for label in ("out_of_scope", "schedule", "email", "policy"):
            if label in text or label.replace("_", " ") in text:
                return label
        return "policy"  # unparseable label: the policy agent refuses by itself if the documents lack the answer

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        async for event in self.router.run_async(ctx):
            yield event
        route = self.parse_route(ctx.session.state.get("route", ""))
        question = next((p.text for p in (ctx.user_content.parts if ctx.user_content else []) if p.text), "")
        if route == "out_of_scope" and _strong_document_match(question):
            route = "policy"  # second opinion: the documents clearly cover this, let the policy agent try
        if route == "email" and not _about_email(question):
            route = "policy"
        if route == "schedule" and not _about_timetable(question):
            route = "policy"  # e.g. exam weeks, semester start, holidays: in the academic calendar documents
        if route == "out_of_scope":
            log_unanswered_question(question, reason="out of scope (router)")
            yield Event(invocation_id=ctx.invocation_id, author=self.name,
                        content=types.Content(role="model", parts=[types.Part(text=config.REFUSAL_TEXT)]),
                        custom_metadata={"logged_unanswered": True})
            return
        async for event in self.find_sub_agent(f"{route}_agent").run_async(ctx):
            yield event


def build_multi_agent(model_name: str | None = None, strategy: str = "router") -> BaseAgent:
    model = build_model(model_name, think=config.THINK == "all")
    reasoning_model = build_model(model_name, think=config.THINK in ("all", "policy"))

    def specialist(name, description, instruction, tools, model=model, **callbacks):
        # Specialists answer and finish; the next user turn starts again at the orchestrator.
        return LlmAgent(name=name, model=model, description=description, instruction=instruction,
                        tools=tools + [log_unanswered_question], generate_content_config=_gen_config(),
                        disallow_transfer_to_parent=True, disallow_transfer_to_peers=True, **callbacks)

    policy = specialist("policy_agent",
                        "Answers questions on academic rules, regulations, programmes, curriculum, credits, "
                        "attendance, exams, grading and leave using the document store.",
                        POLICY_INSTRUCTION, [search_academic_documents], model=reasoning_model,
                        before_model_callback=force_document_search)
    schedule = specialist("schedule_agent",
                          "Answers questions on course slots, timetable, class timings and courses floated "
                          "this semester (counts and lists).",
                          SCHEDULE_INSTRUCTION, [get_course_info, list_courses, get_slot_timings],
                          before_tool_callback=guard_slot_lookup)
    email = specialist("email_agent",
                       "Finds a course instructor's email and drafts emails for leave, sick leave or "
                       "make-up exam requests.",
                       EMAIL_INSTRUCTION, [draft_email, get_instructor_contact],
                       after_tool_callback=remember_email_draft, after_model_callback=render_email_draft)

    if strategy == "transfer":
        return LlmAgent(
            name="helpdesk_orchestrator",
            model=model,
            description="Routes student questions to the right specialist agent.",
            instruction=ORCHESTRATOR_INSTRUCTION,
            tools=[log_unanswered_question],
            sub_agents=[policy, schedule, email],
            generate_content_config=_gen_config(),
        )
    router = LlmAgent(name="router_agent", model=model, instruction=ROUTER_INSTRUCTION, output_key="route",
                      description="Classifies the question into policy / schedule / email / out_of_scope.",
                      generate_content_config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=20),
                      disallow_transfer_to_parent=True, disallow_transfer_to_peers=True)
    return HelpdeskOrchestrator("helpdesk_orchestrator", router, [policy, schedule, email])


def build_agent(mode: str = "multi", model_name: str | None = None) -> BaseAgent:
    """mode: 'multi' (router orchestrator), 'multi-transfer' (native ADK transfer) or 'single'."""
    if mode == "single":
        return build_single_agent(model_name)
    return build_multi_agent(model_name, strategy="transfer" if mode == "multi-transfer" else "router")
