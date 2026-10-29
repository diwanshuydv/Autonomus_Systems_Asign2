"""Central configuration. Every value can be overridden with an environment variable."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCES_DIR = Path(os.getenv("HELPDESK_SOURCES", ROOT / "sources"))
DATA_DIR = Path(os.getenv("HELPDESK_DATA", ROOT / "data"))
VECTOR_DIR = Path(os.getenv("HELPDESK_VECTORS", ROOT / "vectorstore"))
LOG_DIR = ROOT / "logs"
DRAFTS_DIR = ROOT / "drafts"

# Chat model, in LiteLLM notation. "ollama_chat/<tag>" talks to a local Ollama server.
LLM_MODEL = os.getenv("HELPDESK_LLM", "ollama_chat/qwen3:1.7b")
# Qwen3 is a hybrid reasoning model. Thinking makes qwen3:1.7b much better at reading the
# retrieved passages but slower and less reliable at emitting tool calls, so by default it is
# enabled only for the policy agent (whose tool call is issued by code). Values: none | policy | all
THINK = os.getenv("HELPDESK_THINK", "policy").lower()
TEMPERATURE = float(os.getenv("HELPDESK_TEMPERATURE", "0.2"))
REQUEST_TIMEOUT = int(os.getenv("HELPDESK_REQUEST_TIMEOUT", "180"))  # seconds per LLM call
MAX_OUTPUT_TOKENS = int(os.getenv("HELPDESK_MAX_OUTPUT_TOKENS", "1200"))

EMBED_MODEL = os.getenv("HELPDESK_EMBED", "nomic-embed-text")
OLLAMA_HOST = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
COLLECTION = "academic_docs"

CHUNK_SIZE = int(os.getenv("HELPDESK_CHUNK_SIZE", "1200"))     # characters
CHUNK_OVERLAP = int(os.getenv("HELPDESK_CHUNK_OVERLAP", "200"))
TOP_K = int(os.getenv("HELPDESK_TOP_K", "3"))
# If even the best passage is less similar than this (cosine), the question is treated as not
# covered by the documents. Calibrated on nomic-embed-text: in-scope ~0.75+, off-topic ~0.55-0.65.
MIN_SIMILARITY = float(os.getenv("HELPDESK_MIN_SIMILARITY", "0.68"))
# If the router says "out of scope" but a passage is at least this similar, the policy agent gets a try.
OVERRIDE_SIMILARITY = float(os.getenv("HELPDESK_OVERRIDE_SIMILARITY", "0.72"))

# Structured data used by the lookup tools.
COURSES_CSV = DATA_DIR / "courses_offered.csv"
SLOTS_CSV = DATA_DIR / "slot_timings.csv"
FACULTY_CSV = DATA_DIR / "faculty_directory.csv"
DEPARTMENTS_CSV = DATA_DIR / "departments.csv"
CURRENT_SEMESTER = os.getenv("HELPDESK_SEMESTER", "Semester I, AY 2026-27")

UNANSWERED_LOG = LOG_DIR / "unanswered_questions.jsonl"

# Placeholders the student fills in before sending an email draft.
STUDENT_NAME = os.getenv("HELPDESK_STUDENT_NAME", "[Your Name]")
STUDENT_ROLL = os.getenv("HELPDESK_STUDENT_ROLL", "[Your Roll Number]")

REFUSAL_TEXT = (
    "I'm sorry, I don't know the answer to that. I can only help with IIT Jodhpur "
    "academic programmes, courses, rules and regulations, timetables and instructor "
    "emails. I have logged your question so that a human from the academic office can respond."
)
