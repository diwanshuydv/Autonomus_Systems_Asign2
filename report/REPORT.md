# Academic Helpdesk Agent: Design and Evaluation Report

**Course:** Autonomous Systems. **Assignment:** Multi-agent Academic Helpdesk (IIT Jodhpur).
**Stack:** Google ADK 2.13 + LiteLLM, Ollama (qwen3:1.7b by default; qwen3:8b and llama3.1:8b were compared once, in configs D-F), nomic-embed-text, ChromaDB.
**Hardware:** Apple-silicon laptop with 16 GB RAM. Everything runs locally.

---

## 1. Problem

The helpdesk must:

1. answer questions about academic programmes, course contents, rules and regulations, and the semester timetable;
2. draft (not send) emails to course instructors, for example for sick leave or a make-up exam;
3. cite the document each answer comes from;
4. say "I don't know" to anything outside its scope, without guessing;
5. log every question it could not answer so a human can respond.

## 2. System design

### 2.1 Agents

```
student ─▶ helpdesk_orchestrator (custom ADK BaseAgent)
             ├─ router_agent    LLM, outputs one label: policy | schedule | email | out_of_scope
             ├─ policy_agent    RAG over regulations and circulars
             ├─ schedule_agent  timetable / course-list lookups
             └─ email_agent     instructor lookup and email drafting
```

* **Orchestrator.** A custom `BaseAgent`. It runs `router_agent` (temperature 0, 20-token cap), reads
  the label from session state (`output_key="route"`) and hands the turn to that specialist.
  * An `out_of_scope` label gets the fixed refusal text and is logged.
  * Second opinion: if the router says `out_of_scope` but some document passage has cosine
    similarity ≥ 0.72 to the question, the policy agent gets the question instead. The policy
    agent can still refuse. This catches router mistakes on real academic questions (for
    example, a grading question).
  * Intent checks (v3): a `schedule` label is only accepted if the question names a course, a slot
    or a course offering; otherwise it is a calendar question ("When are the minor exams?") and goes
    to the policy agent, which can search the academic calendars. An `email` label is only accepted
    if the question asks to write, draft or mail something, or for contact details; "To whom should
    I address a leave application?" is a rules question.
* **Policy agent.** Tools: `search_academic_documents` and `log_unanswered_question`.
  * A `before_model_callback` issues the search call itself on the first step of every turn.
    The call goes through ADK's normal tool execution and appears in the trace.
  * Qwen3 "thinking" is enabled for this agent only.
* **Schedule agent.** Tools: `get_course_info`, `list_courses` (filter by department, level and
  category, and count), `get_slot_timings`.
  * In v2, a `before_tool_callback` guard stops invented slot names (section 5.4).
* **Email agent.** Tools: `draft_email` and `get_instructor_contact`.
  * The LLM only extracts the parameters: course, request type, number of days, dates, reason and exam.
  * The tool looks up the instructor, fills a template and saves the draft under `drafts/`. It never sends anything.
  * An `after_model_callback` shows the draft verbatim, so the model cannot paraphrase it or drop the body.
  * Leave drafts include the relevant leave rule, with its citation.
* **Single-agent baseline.** One `LlmAgent` with all 7 tools. This is the "base version" the assignment asks for first.
* **Native ADK delegation (`multi-transfer`).** The same three specialists, with an `LlmAgent`
  orchestrator that delegates through ADK's `transfer_to_agent`. It is kept for comparison.

### 2.2 Tools

| Tool | Source | Returns |
|---|---|---|
| `search_academic_documents(query)` | ChromaDB + BM25 | top-3 passages with `[Source: <title>, p. N]`, document date, or `no_relevant_documents` |
| `get_course_info(course)` | `data/courses_offered.csv` + `slot_timings.csv` | code, title, credits, L-T-P, category, slot and its timings, lab slot, instructor |
| `list_courses(department, level, category)` | `courses_offered.csv` + `departments.csv` | count and list (for example, 400-level HS electives) |
| `get_slot_timings(slot)` | `slot_timings.csv` | days and times |
| `get_instructor_contact(course)` | `courses_offered.csv` + `faculty_directory.csv` | instructor, email, office |
| `draft_email(course, request_type, reason, num_days, dates, exam)` | the tools above + template | To, Subject, Body, saved path, policy note |
| `log_unanswered_question(question, reason)` | — | appends to `logs/unanswered_questions.jsonl` |

Every tool result includes a `citation` string. The agents are told to end answers with it.

### 2.3 RAG pipeline

**Loading.**
* Text is extracted with pypdf.
* Scanned pages (fewer than 40 extractable characters) are OCR'd with RapidOCR. Missing
  inter-word spaces are restored with `wordninja`.
* Ruled tables are extracted with pdfplumber. Each row is written as a self-contained sentence,
  inserted right after the table caption:
  `Table 11.2 row - Course Type: Open (O) | Course Category: Electives (OE) | B.Tech. Regular: 10 | ...`.
  Without this, the table flattens to `Open (O) Electives (OE) 10 0 0`, and no model in our tests
  could read the open-elective requirement from that.
* Calendar-style grids (v3). The academic calendars are Word tables with merged cells, in which
  every wrapped line is a separate cell, so neither flattened text nor row-wise rendering keeps a
  date with its event and its semester. They are rebuilt from cell positions: each date cell is
  assigned to the column header above it and to the event label that shares the most height with
  it, giving `Minor Examination | SEMESTER I (2026-27) - 15-20 September 2026 | SEMESTER II (2026-27) - 16-21 February 2027 | ...`.
  Headers are carried over to continuation pages only when the column boundaries line up; tables
  whose first row holds dates are left as plain text.
* DOCX, HTML, TXT/MD and CSV files are also supported. Sub-folders of `sources/` are indexed, and
  `sources/.ingestignore` excludes paths (for example `archive/*`).
* `sources/catalog.csv` supplies each document's title, type and date; the dataset's own
  `sources/index.csv` is the fallback (its dates such as "06 Jul 2026 (reminders until 17 Jul 2026)"
  are reduced to the latest date).

**Chunking.** Sentence-aware packing into chunks of 1200 characters with 200 characters of overlap.

**Indexing.**
* nomic-embed-text, using the `search_document:` / `search_query:` prefixes.
* ChromaDB with cosine distance.
* A BM25 index over the same chunks, with a light plural stemmer.

**Retrieval.**
* Dense top-12 and BM25 top-12 are fused with reciprocal-rank fusion. The top 3 are kept.
* Each hit is joined with the next chunk of the same page (small-to-big expansion), so that
  tables and lists split by the chunker come back whole.
* If the best cosine similarity is below 0.68, the tool returns `no_relevant_documents`. Measured
  similarities: in-scope questions about 0.74–0.82; off-topic questions 0.55–0.70.
* Passages within 0.05 of the best similarity are reordered so that amending **circulars** come
  first (newest first). Every passage carries its date. This is how the July 2024 attendance and
  examination circulars override the 2019 regulations they amend. In v2 all documents were
  ordered newest first; with the larger corpus this put the 2022 PG regulations ahead of the 2019
  regulations on B.Tech. questions, so v3 restricts the reordering to circulars.

**Refusal and logging.**
* Every agent has the refusal text and `log_unanswered_question`.
* The runner also detects refusals by regex and logs them if the model forgot to call the tool.
* As a result, 100% of refusals were logged in every configuration.

### 2.4 Data

The corpus is 42 documents, 458 chunks:

| Item | Content |
|---|---|
| `sources/1_Academic_Regulations_Final_03_09_2019.pdf` | UG & PG regulations, 43 pages, text PDF with tables (page 12 needed OCR) |
| `sources/7.1_Circular_...08-July-2024.pdf` | scanned circular (OCR) amending the attendance policy |
| `sources/emails/01-25` | 25 institute notices from 2025-26: registration, fee payment, exam timetables and guidelines, add/drop, course withdrawal, minor/specialization, summer term, IH electives, hostel rules, office orders. Student names and roll numbers are anonymised. |
| `sources/official/30-42` | 13 PDFs downloaded from iitj.ac.in: 7 academic calendars (AY 2026-27, executive students, summer terms, AY 2025-26, BS/B.Sc., PG certificate/diploma), PG regulations (2022 onwards), M.S. by Research regulations, IITJ-AIIMS joint programme regulations, the 2020 amendment notification, the July 2024 examination-policy circular (scanned) and the 2026 holiday list (scanned) |
| `sources/web/27` | the parts of the Academic Regulations web page that are not in the PDFs (branch change rules, discontinued from AY 2026-27) and the B.Tech. academic-session FAQ |
| `sources/00_iitj_official_email_directory.csv` | 167 official office and faculty email IDs |
| `data/courses_offered.csv`, `slot_timings.csv`, `faculty_directory.csv` | **sample data**: 30 courses, 32 slot rows, 16 fictitious faculty at `@dummy.iitj.ac.in`. The real slot sheets were attachments to the registration emails and are not in the dataset. |

Source checks before ingestion:
* The linked "Academic Regulations (Final, 03-09-2019)" PDF is byte-identical to the one already in
  `sources/`. The regulations page links three copies of it and three copies of the 2020
  notification; one of each was kept.
* The regulations web page repeats the two regulation PDFs almost word for word: 98% of its lines
  share 5-word shingles with them. Only the remaining 2% was kept, in `web/27`.
* The B.Tech. 2013, old M.Sc. and Ph.D. 2014 regulations come from the "Old Regulations" page.
  They are superseded and would put conflicting rules into the index, so they are archived
  (`sources/archive/`) and not indexed.
* Chunk-level near-duplicate scan after ingestion: no exact duplicates. The 2019 and 2022
  regulations share 77 near-identical chunks, because the PG regulations restate the 2019 PG rules.
  Both are kept: they apply to different cohorts.

## 3. Problems found while building, and fixes

These came from tracing real runs with qwen3:1.7b. They shaped the final design.

| # | Observation | Fix |
|---|---|---|
| 1 | With ADK's native delegation, qwen3:1.7b returned **empty responses** (`finish_reason=STOP`, no parts) for all 7 example questions from the brief. Calling Ollama directly showed the cause: ADK declares `transfer_to_agent(agent_name)` with an `enum`. With the enum, 0 of 6 calls produced a tool call; without it, the model usually called the tool. | Custom router orchestrator: the LLM outputs a label and code does the dispatch. Native transfer kept as `--mode multi-transfer`. |
| 2 | With Qwen3 thinking on everywhere, sub-agents described tool calls instead of making them ("I will call the get_slot tool…"). With thinking off, the policy agent read passages poorly (it missed the open-elective table row and quoted the superseded attendance rule). | Thinking off for router/schedule/email, on for policy (`HELPDESK_THINK=policy`). |
| 3 | The policy agent often refused, or answered with an invented citation (`[Source: Academic Helpdesk Policy, p. 1]`), **without calling the search tool**. | `before_model_callback` forces the first `search_academic_documents` call. |
| 4 | Runs occasionally hung for minutes: the 1.7B model fell into a repetition loop with no output limit. | `max_output_tokens=1200` (thinking included), 180 s per LLM request, 600 s per evaluation question. |
| 5 | The email agent filled unused arguments with `" "` and paraphrased the draft ("the email body is provided above…"). It also invented a policy note ("the leave is within the allowed limits"). | Argument sanitising in `draft_email`; verbatim draft rendering; a fixed, cited policy note. |
| 6 | The router labelled "How many grade points does a B- grade carry?" as out of scope, and "How many Open Elective credits do I need…" as schedule. | Few-shot examples in the router prompt, plus the retrieval-similarity second opinion. |
| 7 | Flattened PDF tables (credit requirements, grade points) and OCR output without spaces. | pdfplumber row rendering; wordninja re-spacing. |
| 8 | The circular contains both the "Existing policy" and the "Revised policy". The model kept quoting the old one. | Newest-first passage order plus a supersession instruction. This only partly worked at 1.7B (section 5.2). |
| 9 | (v3, larger corpus) Calendar dates were answered from the wrong column: "Semester II classes start 10 May 2027" is the Summer Term column; the right date is 4 January 2027. | Grid tables rebuilt from cell positions (section 2.3). The row renderer had produced 60 chunks of repeated carried-down cells for one 10-page calendar; now there are 23 readable ones. |
| 10 | (v3) The sentence chunker splits at colons, so `SEMESTER I (2026-27): 19-26 November` was cut between header and date. | Grid cells are written as `header - value`. |
| 11 | (v3) Newest-first ordering put the 2022 PG regulations above the 2019 regulations on B.Tech. questions. | Only circulars are moved forward (section 2.3). |
| 12 | (v3) Calendar questions ("When are the minor exams?") were routed to the schedule agent, which only knows the course timetable, and refused. "Address an application for leave" was routed to the email agent. Fee and hostel questions were classed out of scope although notices on them are now in the corpus. | Intent checks on `schedule` and `email` labels (section 2.1). The out-of-scope definition no longer lists fees and hostel rules; dining, transport, sports, placements and general knowledge remain out of scope. |
| 13 | (v3) A refusal sometimes ended with an invented citation such as `[Source: Academic Documents Policy, p. 12]`. | The runner removes citations from plain refusals. |

## 4. Evaluation method

**Question set** (`eval/questions.json`): 30 questions.
* 13 policy, 7 schedule/timetable, 4 email, 6 out-of-scope (dining, travel to campus, hostel
  fee, IPL, placements, library hours).
* All five example questions from the brief are included, plus both example out-of-scope questions.
* Each question lists its key facts as keyword groups (every group must match, with alternatives
  inside a group) and its acceptable source documents.
* After the sources were added, P08 (duration of the Major examination) was changed from
  "120 minutes" (2019 regulations) to "3 hours": the July 2024 examination-policy circular
  supersedes that rule. A-F and A2 were graded against the old expectation, because their corpus
  did not contain the circular.

**New-source question set** (`eval/questions_new_sources.json`): 12 questions that only the added
documents can answer:
* 4 on the academic calendar: semester start, minor-exam week, timetable swap day, holiday;
* 5 on notices: late-registration fine, summer credit limit, summer fee, IH elective cap, feedback rule;
* 2 on amended rules: minor-exam duration, branch change;
* 1 out-of-scope trap (bus timings): the transport office order is in the corpus, but its
  timetable attachment is not.

It is kept separate so that the 30-question results stay comparable across configurations.

**Metrics.** Each question is asked in a fresh session.

| Metric | Definition |
|---|---|
| Accuracy (auto) | In-scope answer contains every key fact (citation text removed first) and is not a refusal. An answer that gives the fact and then appends "I don't know" counts as a refusal. |
| Accuracy (audited) | Auto accuracy after a manual review of every answer the keyword grader passed. Eight false positives were overridden (`eval/manual_audit.json`): the answer contained the number but said something wrong or contradictory. |
| Correct citation | Among answered in-scope questions, the share whose `[Source: …]` names an expected document. |
| Citations genuine | Every `[Source: …]` in the answer appears verbatim in this turn's tool results, i.e. no invented citations. |
| Retrieval / tool hit | A tool returned the expected source (retrieval quality, independent of the LLM). |
| Correct refusal | Out-of-scope question answered with "I don't know". |
| False refusal | In-scope question refused. |
| Refusals logged | Share of refusals written to the unanswered-questions log. |
| Routing accuracy | The question reached the intended specialist. |
| Stability | Over repeated runs: whether correctness changed, and pairwise answer similarity (difflib). |

**Configurations.** Temperature 0.2. A, A2, A3, N and B were run 3 times each; the others once,
because the 8B models are slow on this machine. A–F and A2 used the 2-document corpus; A3 and N
use the 42-document corpus.

| Tag | Model | Orchestration | Thinking |
|---|---|---|---|
| A | qwen3:1.7b | router multi-agent (v1) | policy agent |
| A2 | qwen3:1.7b | router multi-agent (**v2**: fixes from section 5.4) | policy agent |
| B | qwen3:1.7b | single agent, all tools | off |
| C | qwen3:1.7b | router multi-agent (v1) | off |
| D | qwen3:8b | router multi-agent (v1) | policy agent |
| E | llama3.1:8b | router multi-agent (v1) | n/a |
| F | qwen3:8b | ADK native `transfer_to_agent` (v1) | policy agent |
| A3 | qwen3:1.7b | router multi-agent (**v3**: 42 documents, fixes 9–13 of section 3) | policy agent |
| N | qwen3:1.7b | as A3, on the 12 new-source questions | policy agent |

## 5. Results

### 5.1 Overall

| Config | Runs | Accuracy auto | Accuracy audited | Correct citation | Citations genuine | Retrieval hit | Correct refusal (OOS) | False refusal | Logged | Routing | Latency (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** qwen3:1.7b multi | 3 | 76% | 72% | 88% | 100% | 88% | **100%** | 11% | 100% | 96% | 11.4 |
| **A2** qwen3:1.7b multi v2 | 3 | **86%** | **83%** | 89% | 100% | 92% | **100%** | 11% | 100% | 96% | 12.4 |
| **B** qwen3:1.7b single | 3 | 18% | 18% | 68% | 39% | 46% | 100% | 61% | 100% | – | 5.2 |
| **C** qwen3:1.7b multi, no think | 1 | 79% | 71% | 86% | 100% | 88% | 100% | 8% | 100% | 96% | 8.2 |
| **D** qwen3:8b multi | 1 | 92% | **92%** | 91% | 100% | 100% | 100% | 4% | 100% | **100%** | 52.2 |
| **E** llama3.1:8b multi | 1 | 92% | 88% | 78% | 100% | 92% | 100% | 4% | 100% | 92% | 247.7 |
| **F** qwen3:8b ADK transfer | 1 | 71% | 71% | 89% | 100% | 83% | 100% | 25% | 100% | 83% | 98.2 |
| **A3** qwen3:1.7b multi v3, 42 docs | 3 | **93%** | **92%** | 86% | 100% | 96% | **100%** | 4% | 100% | **100%** | 9.4 |
| **N** qwen3:1.7b, new-source questions | 3 | 94% | 88% | 94% | 97% | 100% | 100% | 3% | 100% | 100% | 15.3 |

Accuracy (auto) by category:

| Config | Policy (13) | Schedule (7) | Email (4) | Out-of-scope (6) |
|---|---|---|---|---|
| A | 77% | 62% | 100% | 100% |
| A2 | 90% | 71% | 100% | 100% |
| B | 0% | 33% | 50% | 100% |
| C | 85% | 57% | 100% | 100% |
| D | 85% | 100% | 100% | 100% |
| E | 92% | 100% | 75% | 100% |
| F | 69% | 100% | 25% | 100% |
| A3 | 97% | 81% | 100% | 100% |

The per-question table and the raw transcripts are in `eval/results/summary.md` and `eval/results/<tag>.jsonl`.

### 5.2 Findings

1. **Out-of-scope questions were always refused, and every refusal was logged.** This holds
   across all 7 configurations and 6 × 13 out-of-scope trials. In the multi-agent system the
   router catches them at about 0.3 s each, before any retrieval. The similarity floor on the
   search tool (0.68) is a second barrier. The hostel-fee question (similarity 0.70) gets past
   that floor; the router stops it.

2. **Multi-agent beats single-agent by a wide margin at 1.7B: 76% vs 18%.** The single agent made
   no tool call in 30 of 72 in-scope turns and answered or refused from its own knowledge. In
   some answers it gave the correct fact and then appended "I'm sorry, I don't know…". Only 39%
   of its citations were genuine. Splitting the task gives each small model a short prompt with
   2–4 tools and one job. Code-level guarantees (forced retrieval, deterministic email rendering)
   then cover what the model cannot do reliably.

3. **Groundedness is high when answers come through the tools.** In every multi-agent
   configuration, 100% of the citations printed in answers came from tool results: no citation
   was invented. 86–91% of answered questions cited the expected document. Most misses were page
   or document mix-ups (for example, citing the PG leave section, p. 34, for a B.Tech. leave
   question). Llama 3.1 is lower (78%) because it often dropped the `[Source: …]` tag altogether.

4. **Model size matters most for reading regulations and tables.** At 1.7B, policy accuracy is
   77–85% and schedule accuracy 57–62%. Both 8B models reach 85–92% and 100%. The 1.7B failures
   are reasoning failures, not retrieval failures:
   * P12: "programme elective credits": the table row was retrieved, but in 2 of 3 runs the model
     answered "not explicitly specified".
   * P13: in 1 of 3 runs it picked the PG rule ("Convener DRC") over the UG rule ("Convener DUGC").
   * P01: twice it quoted the superseded 2019 attendance rule from the circular's "Existing
     policy" paragraph.

   qwen3:8b got all of these right.

5. **Native ADK delegation is less reliable than an explicit router, even at 8B.** With qwen3:8b,
   the `transfer_to_agent` orchestrator (F) kept 3 of the 4 email requests and a leave-rule
   question for itself and refused them. Routing was 83%, against 100% for the router version
   (D). Email accuracy was 25% against 100%. At 1.7B the native version does not work at all
   (section 3, item 1).

6. **Thinking mode trades speed for reading quality.** Over one run, C (no thinking) scored about
   the same as A (71% vs 72% audited) and was 30% faster. The errors differed: without thinking,
   the model missed the open-elective table (P02) and stated the superseded attendance rule; with
   thinking, it read the table correctly in 3 of 3 runs.

7. **Latency.** qwen3:1.7b answers in 11 s on average: 0.3 s for refusals, 5–9 s for schedule and
   email, 10–25 s for policy questions with thinking. The 8B models took 52 s (qwen3) and 248 s
   (llama3.1) per question. During these runs the laptop had about 8 GB of swap in use from other
   applications, and the embedding model and the chat model were both resident. So the 8B models
   do run within 16 GB, but they are only practical with little else running.

### 5.3 Questions whose answers changed across runs (config A, 3 runs)

| Q | Correct runs | What changed |
|---|---|---|
| P12 Programme Elective credits | 1/3 | 2 runs: "not explicitly specified"; 1 run: "18 credits" (correct). |
| P13 Leave application addressed to | 2/3 | 2 runs: Convener DUGC (correct); 1 run: Convener DRC (PG rule). |
| S05 L-T-P of Deep Learning | 1/3 auto, 0/3 audited | Routed to the policy agent in all runs. Answers were "typically 3-0-0", a refusal, and a generic L-T-P explanation. |
| P01 Attendance for Major exam | 3/3 auto, 1/3 audited | All mention 75%. One run correctly says the 2024 circular de-links exams from attendance; one restates the superseded rule; one contradicts itself. |
| P02, P04, P05, P03, P11 | stable outcome | Wording differed: answer similarity 0.17–0.49 between runs, because thinking produces different explanations. The facts and the outcome stayed the same. |

Schedule and email answers, and refusals, were word-for-word stable. Those answers are built
mostly from tool output, and the email body is rendered deterministically.

In A2 the outcome changed for P02 (2/3) and, after audit, P01 (1/3: two runs restated the
superseded rule). Wording again varied for most policy answers (similarity 0.16–0.56).

For B (single agent), S03 changed between runs (1/3). Twice the correct instructor was followed
by an appended refusal.

In A3 only P02 (2/3), S05 (2/3) and, after audit, P01 (2/3) changed outcome. In N, N06 (summer
credit limit) was correct in 1 of 3 runs by keyword and 0 of 3 after audit, and N01 in 2 of 3
after audit.

### 5.4 Error analysis and the v2 fixes

Every failure of config A was traced to a root cause:

| Q | Failure (A) | Root cause | Fix in v2 |
|---|---|---|---|
| P11 | 0/3: "more than two weeks absent" answered with the 4-week semester-withdrawal rule | **Ingestion.** At 2× render scale, RapidOCR's detector skipped the whole bullet "If a student remains absent from a class without sanctioned leave for more than two weeks…". The fact was not in the index, so all models failed or guessed. | OCR at scales 1.5×, 2×, 3× and keep the most complete reading (`OCR_SCALES`). The bullet is now indexed. |
| S06 | 0/3: "Which lab slot does CSL2010 have?" answered "L2" (it is L1) | **Tool-argument hallucination.** The model called `get_slot_timings("L2")` without looking up the course. The tool answered faithfully for a slot nobody asked about. | `before_tool_callback` guard: if the question names a course, `get_slot_timings` returns that course's record instead. |
| S07 | 0/3: "Which open electives are offered?" refused | Schedule agent refused without calling `list_courses(category="open elective")`. | Not fixed (would need forced tool choice); the 8B models answer it. |
| S05 | misrouted to policy | The router reads "L-T-P structure" as a regulation question. | Not fixed. |
| P03 | 0/3: "minimum CGPA for Independent Study" refused | **Retrieval.** The answer chunk ranked 4th; top-3 held the capability-linked-opportunity rule (also CGPA 6.0, different context). | Not fixed. A cross-encoder re-ranker or top-k = 4 would help. |
| P12, P13, P01 | intermittent | 1.7B reasoning (see 5.2.4). | Larger model. |

**Effect of the v2 fixes (A → A2, 3 runs each, same model and prompts).**

| | A (v1) | A2 (v2) |
|---|---|---|
| Accuracy auto / audited | 76% / 72% | **86% / 83%** |
| P11 (two-week absence) | 0/3 | **3/3** |
| S06 (lab slot of CSL2010) | 0/3 | **3/3** (the model still guessed "L2"; the guard returned the real course record and it answered L1) |
| Retrieval hit | 88% | 92% |
| Policy / schedule accuracy | 77% / 62% | 90% / 71% |

Two fixes, each a few lines, both outside the LLM, added 10 points of accuracy. P12 and P13 also
went to 3/3. That gain should be read as run-to-run variance rather than as an effect of the
fixes. P02 dropped to 2/3 for the same reason. Remaining 1.7B failures:
* P03, S05, S07: 0/3 each (retrieval rank, routing, no tool call);
* P01: correct in only 1/3 runs after audit (superseded rule);
* P13: two runs falsely claimed the 2024 circular "confirms" the DUGC rule, a fabricated attribution the citation check does not catch.

### 5.5 Effect of adding the source dataset (A2 → A3, and N)

| | A2 (2 docs, v2) | A3 (42 docs, v3) |
|---|---|---|
| Accuracy auto / audited | 86% / 83% | **93% / 92%** |
| Policy / schedule accuracy | 90% / 71% | 97% / 81% |
| Routing | 96% | 100% |
| Retrieval hit | 92% | 96% |
| Correct refusal (OOS), refusals logged | 100%, 100% | 100%, 100% |
| Mean latency | 12.4 s | 9.4 s |
| Questions below 3/3 | P02 2/3, P03 0/3, S05 0/3, S07 0/3, P01 1/3 (audited) | P02 2/3, S05 2/3, S07 0/3, P01 2/3 (audited) |

* **A 15× larger corpus did not hurt the original questions.** Two adjustments were needed to get
  there: circular-only reordering, so the 2022 PG regulations do not outrank the 2019 regulations
  on B.Tech. questions, and the router intent checks. Before the email check, P13 was routed to
  the email agent in 3 of 3 runs. That P13 result was re-run after the fix and is the figure shown.
* **P03 went from 0/3 to 3/3.** The independent-study rule now ranks in the top 3; the ranking
  changed with the new BM25 statistics of the larger corpus. **S05 went from 0/3 to 2/3**: the
  schedule label is now described as "slot or class timing of a specific course", and the router
  no longer sends "L-T-P structure" to the policy agent.
* **The out-of-scope behaviour held.** Dining, campus travel, the hostel fee amount, IPL,
  placements, library hours and bus timings were refused in every run, although the corpus now
  contains hostel notices, a fee notice and a transport office order.
* **New-source questions (N): 88% audited.** All calendar, rules and branch-change questions were
  correct, citing the 2026-27 calendar, the 2024 examination circular, the holiday list and the
  web extract. The weak spot is N06, the summer-term credit limit. The registration notice says 8
  credits, but in two runs the 1.7B model answered with the regulations' per-semester limit of 25
  credits, and in one it refused. This is the same "two rules with the same keywords" failure as P03.
* **Calendar extraction mattered more than the model.** Before the grid rendering, the model was
  given the right page and still answered "10 May 2027" for the Semester II start, because the
  flattened text listed three dates with no column names. After it, N01 was correct in 3/3 runs
  (2/3 after audit).

## 6. Conclusions

* A multi-agent design with an explicit router, specialist agents with few tools each, and code
  that enforces the critical steps lets a **1.7B model** run a useful helpdesk on a laptop.
  * Out-of-scope questions were refused in every trial.
  * No citation was invented in any multi-agent configuration.
  * Unanswered questions were always logged.
  * After the v2 fixes, 83% (audited) of in-scope answers were correct, at about 12 s per answer.
  * With the full 42-document corpus and the v3 fixes, 92% (audited) were correct, with 100%
    routing, at about 9 s per answer. On 12 questions that only the new documents answer it
    reached 88%.
* The same structure with qwen3:8b reaches 92% accuracy and 100% routing, at about 5× the latency.
* ADK's LLM-driven `transfer_to_agent` is the weak point for small local models. A label-emitting
  router plus a custom `BaseAgent` dispatcher is more robust, and it is cheap: one short LLM call
  per turn.
* Many of the "LLM errors" were actually data or tool errors: a dropped OCR line, a flattened
  table, a calendar grid with no column names, a guessed tool argument. Tracing each failure to its
  root cause gave fixes that help every model.

## 7. Limitations and next steps

* Timetable, course list and faculty data are still sample data. The real slot sheets were
  attachments to the registration emails and were not part of the dataset. The schedule and email
  results therefore test the agents and tools, not real timetable content.
* The 8B comparison (D–F) was run on the 2-document corpus and was not repeated on the full
  corpus: the target machine is a 16 GB laptop, and later runs use small models only.
* Automatic grading is keyword-based. It was complemented with a manual audit of passing answers.
  An LLM-as-judge or human grading of all answers would be more thorough.
* The 8B configurations ran once each, so their figures carry about ±4 points of single-run noise
  per question.
* Open problems:
  * a schedule agent that refuses without calling a tool (forced tool choice is not honoured by Ollama);
  * a router that misreads course-specific wording;
  * retrieval misses when two rules share keywords.

  A cross-encoder re-ranker, a small classifier for routing, and conversation-aware query
  rewriting for follow-up questions are the next steps.

## 8. Reproducing

```bash
ollama pull qwen3:1.7b && ollama pull nomic-embed-text
pip install -r requirements.txt
python -m helpdesk.ingest
python -m eval.run_eval --tag A3_qwen3-1.7b_multi_v3_sources --runs 3
python -m eval.run_eval --tag N_qwen3-1.7b_multi_new_sources --runs 3 --questions eval/questions_new_sources.json
./eval/run_all.sh                         # A-C; the 8B configs D-F only with HEAVY=1
python -m eval.summarize
```

Note: configs A–F were produced by the v1 code and the 2-document corpus, A2 by the v2 code and
the same corpus. Re-running them now uses the v3 code and all 42 documents.
