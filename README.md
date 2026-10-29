# Academic Helpdesk Agent (IIT Jodhpur) — multi-agent RAG with Google ADK + Ollama

A local, laptop-friendly helpdesk that answers questions about academic programmes, course
contents, rules and regulations and the semester timetable, drafts emails to course instructors
(sick leave, leave, make-up exams), refuses out-of-scope questions, and logs every question it
cannot answer for a human to pick up. Every answer cites the document or data file it came from.

* Agent framework: **Google ADK** (2.13), models reached through ADK's **LiteLLM** connector
* LLM: **qwen3:1.7b** via **Ollama** (swappable for any Ollama model, e.g. qwen3:0.6b, deepseek-r1:1.5b)
* Embeddings: **nomic-embed-text** via Ollama; vector store: **ChromaDB** (persistent, local)
* Retrieval: hybrid dense + BM25 with reciprocal-rank fusion, small-to-big chunk expansion
* Runs on a 16 GB RAM laptop (tested on an Apple-silicon Mac, 16 GB). qwen3:1.7b uses ~2.4 GB.

## Architecture

```
                        ┌───────────────────────────────────────────────┐
 student question ───▶  │ helpdesk_orchestrator  (custom ADK BaseAgent) │
                        │   1. router_agent (LLM) → policy | schedule | │
                        │      email | out_of_scope                     │
                        │   2. out_of_scope but a passage is very       │
                        │      similar → give policy_agent a try        │
                        │   3. out_of_scope → "I don't know" + log      │
                        └──────┬───────────────┬───────────────┬────────┘
                               ▼               ▼               ▼
                      policy_agent      schedule_agent     email_agent
                      (LlmAgent)        (LlmAgent)         (LlmAgent)
                          │                 │                  │
     search_academic_documents     get_course_info      get_instructor_contact
     (ChromaDB + BM25 over         list_courses         draft_email → drafts/*.txt
      sources/*)                   get_slot_timings     (never sent)
                          └───── log_unanswered_question → logs/unanswered_questions.jsonl
```

Design choices worth knowing (details and measurements in [report/REPORT.md](report/REPORT.md)):

* **Router orchestrator instead of `transfer_to_agent`.** ADK's built-in delegation exposes a
  `transfer_to_agent` tool whose argument is an enum. With qwen3:1.7b on Ollama that tool schema
  produces *empty* replies, so the default orchestrator is a custom `BaseAgent` that asks a
  router LLM for a one-word label and then runs the chosen specialist. The native ADK transfer
  version is still available (`--mode multi-transfer`) and works with 8B models.
* **Forced first retrieval.** The policy agent's `before_model_callback` issues the
  `search_academic_documents` call itself on the first step of every turn (it still goes through
  ADK's tool machinery and shows up in the trace); a 1.7B model otherwise often "answers" or
  refuses without looking anything up.
* **Thinking only where it helps.** Qwen3's reasoning mode is enabled for the policy agent (reading
  regulations and tables) and disabled for the router, schedule and email agents (tool calling).
* **Deterministic email rendering.** The LLM extracts course / request type / days / reason; the
  `draft_email` tool fills a template, looks up the instructor's address, and the draft is shown
  verbatim (`after_model_callback`) so a small model cannot paraphrase or drop the body.
* **Guaranteed hand-off log.** Any refusal is written to `logs/unanswered_questions.jsonl`, by the
  agent's `log_unanswered_question` call or, if the model forgets, by the runner.
* **Circulars win.** Among passages of similar relevance, amending circulars come first (newest
  first) and every passage is dated, so a 2024 circular supersedes the 2019 regulations it amends.
  Other documents keep their relevance order (the 2022 PG regulations must not outrank the 2019
  regulations on a B.Tech. question just because they are newer).
* **Calendar questions go to the documents.** If the router picks the schedule agent but the
  question names no course, slot or course offering ("When are the minor exams?"), the policy
  agent answers from the academic calendar instead.
* **Guards against tool-argument guessing.** If the student names a course but the schedule agent
  calls `get_slot_timings` with a made-up slot, a `before_tool_callback` returns the course record.

## Setup

```bash
# 1. Ollama models (https://ollama.com)
ollama pull qwen3:1.7b
ollama pull nomic-embed-text
# optional, only for the 8B comparison configs (heavy on a 16 GB laptop)
# ollama pull qwen3:8b && ollama pull llama3.1:8b

# 2. Python 3.11 or 3.12 environment
python3.12 -m venv .venv            # or: uv venv -p 3.12 .venv
source .venv/bin/activate
pip install -r requirements.txt     # or: uv pip install -r requirements.txt

# 3. Build the vector store from sources/
python -m helpdesk.ingest
```

## Usage

```bash
python chat.py --trace                       # interactive chat, shows agents + tool calls
python chat.py -q "What is the slot for the course Autonomous Systems?"
python chat.py --mode single                 # single-agent baseline (all tools in one agent)
python chat.py --model ollama_chat/deepseek-r1:1.5b  # any LiteLLM model id
./ask_examples.sh                            # the example questions from the assignment brief

adk web adk_agents                           # ADK developer UI (choose "academic_helpdesk")
```

Example session:

```
You: Write an email to the course instructor of CSL7570 that I need leave for 2 days
  agents: router_agent -> email_agent
  tool:   email_agent.draft_email({"course": "CSL7570", "request_type": "leave", "num_days": 2, ...})
Helpdesk: Here is a draft email for you to review. It has NOT been sent.
To: arjun.mehta@dummy.iitj.ac.in
Subject: Request for Leave of Absence - CSL7570
...
```

## Adding documents

Drop files into `sources/` and re-run `python -m helpdesk.ingest` (it rebuilds the collection).

* Formats: PDF (text or scanned), DOCX, TXT, MD, HTML, CSV.
* Scanned PDFs (circulars, office orders) are OCR'd locally with RapidOCR; missing spaces are
  restored with `wordninja`. For a perfect transcript, place `<file>.pdf.ocr.txt` next to the
  PDF (pages separated by `=== PAGE n ===` lines) and it is used instead of OCR.
* Ruled tables in PDFs are extracted with pdfplumber and written row by row
  (`Table 11.2 row - Course Type: Open (O) | Course Category: Electives (OE) | B.Tech. Regular: 10.`).
  Calendar-style grids with merged cells are rebuilt from cell positions
  (`Minor Examination | SEMESTER I (2026-27) - 15-20 September 2026 | SEMESTER II (2026-27) - 16-21 February 2027`).
* Sub-folders are indexed too (`sources/emails/`, `sources/official/`, `sources/web/`). Paths listed
  in `sources/.ingestignore` (glob patterns) are skipped, e.g. `archive/*` for superseded regulations.
* `sources/catalog.csv` (`filename,title,doc_type,date`, filename relative to `sources/`) gives each
  document the title used in citations and its date. A dataset `sources/index.csv`
  (`file,title,category,source,date`) is used as a fallback. Without either the title is derived
  from the file name. Passages from documents with `doc_type` `Circular` are put first when about
  as relevant as others, because circulars amend the regulations.

The timetable, course list and faculty directory are CSV files in `data/` read by the lookup
tools — see [data/README.md](data/README.md). **They currently hold sample/dummy data**; replace
them with the real semester timetable and faculty list.

## Evaluation

`eval/questions.json` holds 30 questions (13 policy, 7 schedule, 4 email, 6 out-of-scope) with
expected key facts and expected source documents; `eval/QUESTIONS.md` is the readable list.
Answers the keyword grader passed were also reviewed by hand; false positives are recorded in
`eval/manual_audit.json` and reported as "audited accuracy".

```bash
python -m eval.run_eval --tag my_run --runs 3          # one configuration
./eval/run_all.sh                                      # every configuration in the report
python -m eval.summarize                               # → eval/results/summary.md
```

Headline result (qwen3:1.7b, multi-agent, all 42 documents, 3 runs): 93% in-scope accuracy (92%
audited), 100% correct refusals, 100% genuine citations, 100% routing, ~9 s per answer. On 12
questions only the new sources can answer (`eval/questions_new_sources.json`) it reaches 88%
audited. The single-agent baseline gets 18%. Full results: [report/REPORT.md](report/REPORT.md).

The 8B configurations of the report (`HEAVY=1 ./eval/run_all.sh`) need about 6 GB more memory;
everything else runs with qwen3:1.7b.

Metrics: answer accuracy (key facts present), correct citation (expected source cited), genuine
citations (every `[Source: ...]` came from a tool result), retrieval hit, correct refusal of
out-of-scope questions, false refusals, refusals logged, routing accuracy, latency, and answer
stability across repeated runs. Raw transcripts are in `eval/results/<tag>.jsonl`.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `HELPDESK_LLM` | `ollama_chat/qwen3:1.7b` | chat model (LiteLLM id) |
| `HELPDESK_THINK` | `policy` | Qwen3 thinking: `none`, `policy` (policy agent only), `all` |
| `HELPDESK_TEMPERATURE` | `0.2` | sampling temperature of the specialists |
| `HELPDESK_EMBED` | `nomic-embed-text` | Ollama embedding model |
| `HELPDESK_TOP_K` | `3` | passages returned per search (each expanded with its next chunk) |
| `HELPDESK_MIN_SIMILARITY` | `0.68` | below this best cosine similarity the documents "don't know" |
| `HELPDESK_OVERRIDE_SIMILARITY` | `0.72` | router said out-of-scope but a passage is this similar → policy agent |
| `HELPDESK_SEMESTER` | `Semester I, AY 2026-27` | label used in timetable citations |
| `HELPDESK_STUDENT_NAME`, `HELPDESK_STUDENT_ROLL` | placeholders | signature of email drafts |
| `OLLAMA_API_BASE` | `http://localhost:11434` | Ollama server |

## Repository layout

```
helpdesk/            core package
  config.py          settings
  ingest.py          loading (PDF/OCR/tables/DOCX/HTML/CSV), chunking, embedding → ChromaDB
  rag.py             hybrid retriever (dense + BM25, RRF, small-to-big expansion)
  tools.py           the 7 agent tools
  agents.py          router orchestrator, policy/schedule/email agents, single-agent baseline
  runner.py          ADK runner wrapper (trace, refusal detection, auto-logging)
adk_agents/academic_helpdesk/agent.py   root_agent for `adk web`
chat.py              CLI
ask_examples.sh      the assignment's example questions
sources/             documents for RAG: regulations and circulars, emails/ (institute notices),
                     official/ (calendars, regulations), web/ (website extracts), catalog.csv,
                     .ingestignore, archive/ (superseded, not indexed)
data/                timetable / courses / faculty CSVs (sample data)
eval/                questions.json / QUESTIONS.md, run_eval.py, summarize.py, run_all.sh,
                     manual_audit.json, results/ (raw transcripts + summary.md)
logs/unanswered_questions.jsonl         questions referred to a human
drafts/              generated email drafts (never sent)
report/REPORT.md     findings
report/example_session.txt              transcript of ./ask_examples.sh
```
