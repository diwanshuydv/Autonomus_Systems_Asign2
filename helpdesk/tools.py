"""Tools exposed to the agents. Each returns a plain dict that ADK serialises back to the LLM.

Every tool result carries a ``citation`` string so the answering agent can cite where the
information came from.
"""
from __future__ import annotations

import csv
import difflib
import json
import re
from datetime import datetime
from functools import lru_cache

from . import config

TIMETABLE_CITATION = f"[Source: Course Timetable, {config.CURRENT_SEMESTER} (courses_offered.csv)]"
SLOTS_CITATION = "[Source: Slot Timings (slot_timings.csv)]"
FACULTY_CITATION = "[Source: Faculty Directory (faculty_directory.csv)]"


# ---------------------------------------------------------------- helpers

@lru_cache(maxsize=None)
def _rows(path) -> tuple[dict, ...]:
    with open(path, newline="", encoding="utf-8") as f:
        return tuple({k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f))


def _norm_code(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _find_courses(course: str) -> list[dict]:
    """Resolve a course code ('CSL7570', 'csl 7570') or title ('autonomous systems')."""
    courses = _rows(config.COURSES_CSV)
    code = _norm_code(course)
    exact = [c for c in courses if _norm_code(c["course_code"]) == code]
    if exact:
        return exact
    m = re.search(r"[A-Z]{2,3}\s*\d{4}", course.upper())
    if m:
        hits = [c for c in courses if _norm_code(c["course_code"]) == _norm_code(m.group(0))]
        if hits:
            return hits
    title = re.sub(r"\b(the|course|subject|class)\b", " ", course.lower())
    title = re.sub(r"\s+", " ", title).strip()
    by_title = {c["course_title"].lower(): c for c in courses}
    if title in by_title:
        return [by_title[title]]
    contains = [c for t, c in by_title.items() if title and (title in t or t in title)]
    if contains:
        return contains
    return [by_title[t] for t in difflib.get_close_matches(title, list(by_title), n=3, cutoff=0.6)]


def _slot_schedule(slot: str) -> list[str]:
    return [f"{r['day']} {r['start_time']}-{r['end_time']} ({r['session_type']})"
            for r in _rows(config.SLOTS_CSV) if r["slot"].upper() == slot.upper()]


def _faculty(name: str) -> dict:
    for f in _rows(config.FACULTY_CSV):
        if f["name"].lower() == name.lower():
            return f
    return {}


def _resolve_department(dept: str) -> str | None:
    d = dept.strip().lower()
    if not d:
        return None
    for row in _rows(config.DEPARTMENTS_CSV):
        names = {row["code"].lower(), row["name"].lower(), *[a.strip() for a in row["aliases"].lower().split(";")]}
        if d in names or d.replace(" department", "") in names:
            return row["code"]
    for row in _rows(config.DEPARTMENTS_CSV):  # loose fallback: "humanities dept" -> HS
        if row["name"].lower().startswith(d.split()[0]):
            return row["code"]
    return None


def find_course_mention(text: str) -> str | None:
    """Return the code of a course named in free text (by code or full title), if any."""
    m = re.search(r"\b[A-Z]{2,3}\s?\d{4}\b", text.upper())
    if m and _find_courses(m.group(0)):
        return _find_courses(m.group(0))[0]["course_code"]
    lowered = text.lower()
    for c in sorted(_rows(config.COURSES_CSV), key=lambda c: -len(c["course_title"])):
        if c["course_title"].lower() in lowered:
            return c["course_code"]
    return None


def _not_found(course: str) -> dict:
    return {"status": "not_found",
            "message": f"No course matching '{course}' is offered in {config.CURRENT_SEMESTER}.",
            "citation": TIMETABLE_CITATION}


# ---------------------------------------------------------------- tools

def search_academic_documents(query: str) -> dict:
    """Search IIT Jodhpur academic documents (rules and regulations, circulars, office orders,
    curriculum, registration notices) and return the most relevant passages with citations.

    Args:
        query: The student's question or the key terms to search for.
    """
    from .rag import get_retriever

    hits = get_retriever().search(query)
    if not hits or max(h["similarity"] for h in hits) < config.MIN_SIMILARITY:
        return {"status": "no_relevant_documents",
                "message": "The academic documents do not contain information about this. "
                           "Tell the student you do not know and log the question."}
    # Among passages that are about equally relevant, put amending circulars first (newest first):
    # they override the older regulations, and small models tend to use the first passage. Other
    # documents keep their relevance order, so e.g. the 2022 PG regulations do not jump ahead of the
    # 2019 regulations on a B.Tech. question just because they are newer.
    best = max(h["similarity"] for h in hits)
    hits.sort(key=lambda h: (h["similarity"] < best - 0.05,
                             0 if h["doc_type"] == "Circular" else 1,
                             -int((h["date"] or "0").replace("-", "")) if h["doc_type"] == "Circular" else 0))
    passages = [{
        "citation": f"[Source: {h['title']}, p. {h['page']}]",
        "document_date": h["date"] or "unknown",
        "text": h["text"],
    } for h in hits]
    return {"status": "found",
            "passages": passages,
            "note": "Answer only from these passages and end with the citation of the passage used. "
                    "If passages disagree, the most recent document (e.g. a circular) overrides older rules."}


def get_course_info(course: str) -> dict:
    """Look up a course in this semester's timetable by course code or title. Returns its code,
    title, department, level, credits, L-T-P, category, lecture slot with day/time, lab slot
    and instructor.

    Args:
        course: Course code (e.g. 'CSL7570') or course title (e.g. 'Autonomous Systems').
    """
    matches = _find_courses(course)
    if not matches:
        return _not_found(course)
    results = []
    for c in matches[:3]:
        info = dict(c)
        info["slot_timings"] = _slot_schedule(c["slot"]) if c["slot"] else []
        info["lab_slot_timings"] = _slot_schedule(c["lab_slot"]) if c["lab_slot"] else []
        results.append(info)
    return {"status": "found", "semester": config.CURRENT_SEMESTER, "courses": results,
            "citation": TIMETABLE_CITATION}


def get_slot_timings(slot: str) -> dict:
    """Return the days and times of a timetable slot (e.g. 'C', 'H', 'L2').

    Args:
        slot: Slot name as written in the timetable.
    """
    schedule = _slot_schedule(slot.strip().replace("Slot", "").replace("slot", "").strip())
    if not schedule:
        return {"status": "not_found", "message": f"Slot '{slot}' does not exist.", "citation": SLOTS_CITATION}
    return {"status": "found", "slot": slot.upper(), "timings": schedule, "citation": SLOTS_CITATION}


def list_courses(department: str = "", level: int = 0, category: str = "") -> dict:
    """List and count the courses floated this semester, optionally filtered. Use it for
    questions like 'How many 400 level electives are offered by the Humanities department?'.

    Args:
        department: Department name or code, e.g. 'Humanities', 'HS', 'Computer Science'. Empty for all.
        level: Course level such as 100, 200, 300, 400, 700. 0 for all levels.
        category: 'elective', 'core', 'open elective', 'programme elective', 'hss elective'. Empty for all.
    """
    rows = list(_rows(config.COURSES_CSV))
    applied = {}
    if department:
        code = _resolve_department(department)
        if code is None:
            return {"status": "not_found", "message": f"Unknown department '{department}'.",
                    "citation": TIMETABLE_CITATION}
        rows = [r for r in rows if r["department"] == code]
        applied["department"] = code
    if level:
        lvl = int(str(level)[0]) * 100 if int(level) >= 100 else int(level) * 100
        rows = [r for r in rows if int(r["level"]) == lvl]
        applied["level"] = lvl
    if category:
        cat = category.lower().replace("courses", "").replace("course", "").strip().rstrip("s")
        rows = [r for r in rows if cat in r["category"].lower()]
        applied["category"] = cat
    return {"status": "found", "semester": config.CURRENT_SEMESTER, "filters": applied, "count": len(rows),
            "courses": [f"{r['course_code']} {r['course_title']} ({r['category']}, {r['credits']} credits, "
                        f"slot {r['slot'] or r['lab_slot']})" for r in rows],
            "citation": TIMETABLE_CITATION}


def get_instructor_contact(course: str) -> dict:
    """Find the instructor of a course and their email address and office.

    Args:
        course: Course code (e.g. 'CSL7570') or course title.
    """
    matches = _find_courses(course)
    if not matches:
        return _not_found(course)
    c = matches[0]
    fac = _faculty(c["instructor"])
    return {"status": "found", "course_code": c["course_code"], "course_title": c["course_title"],
            "instructor": c["instructor"], "email": fac.get("email", "not listed"),
            "office": fac.get("office", ""), "citation": f"{TIMETABLE_CITATION} {FACULTY_CITATION}"}


EMAIL_TEMPLATES = {
    "leave": ("Request for Leave of Absence - {code}",
              "I am writing to inform you that I will not be able to attend the {title} ({code}) classes "
              "{period} due to {reason}. I kindly request you to grant me leave for this period. "
              "I will make sure to cover the material I miss and complete any pending work."),
    "sick_leave": ("Request for Medical Leave - {code}",
                   "I am writing to inform you that I am unwell and will not be able to attend the {title} "
                   "({code}) classes {period}. {reason_sentence}I kindly request you to grant me medical leave "
                   "for this period. I will submit the medical certificate and catch up on the missed material."),
    "makeup_exam": ("Request for Make-up Examination - {code}",
                    "I was unable to appear for the {exam} of {title} ({code}) {period} due to {reason}. "
                    "I kindly request your permission to appear for a make-up examination at a time convenient "
                    "to you. I can provide supporting documents (e.g. a medical certificate) if required."),
    "other": ("Regarding {title} ({code})",
              "I am writing to you regarding {title} ({code}). {reason_sentence}"),
}


def draft_email(course: str, request_type: str, reason: str = "", num_days: int = 0,
                dates: str = "", exam: str = "") -> dict:
    """Write an email draft from the student to the instructor of a course. The draft is saved for
    the student to review; it is NOT sent. The instructor's name and email are looked up automatically.

    Args:
        course: Course code (e.g. 'CSL7570') or course title.
        request_type: One of 'leave', 'sick_leave', 'makeup_exam', 'other'.
        reason: Reason given by the student, e.g. 'fever', 'a family emergency'. Empty if not given.
        num_days: Number of days of leave requested, 0 if not given.
        dates: Dates mentioned by the student, e.g. '3-4 November'. Empty if not given.
        exam: For make-up requests, the missed exam, e.g. 'Minor 1', 'Major'. Empty if not given.
    """
    contact = get_instructor_contact(course)
    if contact["status"] != "found":
        return contact
    # small models often fill unused optional arguments with " " or "none"
    reason, dates, exam = (("" if str(v).strip().lower() in {"", "none", "null", "n/a", "na", "0"} else str(v).strip())
                           for v in (reason, dates, exam))
    rtype = request_type.lower().replace("-", "_").replace(" ", "_")
    if rtype not in EMAIL_TEMPLATES:
        rtype = "sick_leave" if "sick" in rtype or "medical" in rtype else \
            "makeup_exam" if "make" in rtype or "exam" in rtype else "leave" if "leave" in rtype else "other"
    num_days = int(num_days or 0)
    if dates and num_days:
        period = f"for {num_days} day{'s' if num_days > 1 else ''} ({dates})"
    elif dates:
        period = f"on {dates}"
    elif num_days:
        period = f"for the next {num_days} day{'s' if num_days > 1 else ''}"
    else:
        period = "[mention the dates]" if rtype != "makeup_exam" else "held on [exam date]"
    fields = {"code": contact["course_code"], "title": contact["course_title"], "period": period,
              "reason": reason or ("illness" if rtype in ("sick_leave", "makeup_exam") else "[state your reason]"),
              "reason_sentence": f"The reason is {reason}. " if reason else "",
              "exam": exam or "examination"}
    subject_t, para_t = EMAIL_TEMPLATES[rtype]
    subject = subject_t.format(**fields)
    body = (f"Dear {contact['instructor']},\n\n{para_t.format(**fields)}\n\n"
            f"Thank you for your consideration.\n\nYours sincerely,\n{config.STUDENT_NAME}\n"
            f"Roll No.: {config.STUDENT_ROLL}\n")
    config.DRAFTS_DIR.mkdir(exist_ok=True)
    path = config.DRAFTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{contact['course_code']}_{rtype}.txt"
    path.write_text(f"To: {contact['email']}\nSubject: {subject}\n\n{body}", encoding="utf-8")
    result = {"status": "drafted", "to": contact["email"], "subject": subject, "body": body,
              "saved_to": str(path.relative_to(config.ROOT)), "sent": False,
              "citation": contact["citation"]}
    if rtype in ("leave", "sick_leave"):
        result["policy_note"] = ("As per the Academic Regulations 2019 (Sec. 15), a leave application should be "
                                 "addressed to the Convener DUGC with a medical certificate if applicable; "
                                 "short leave is limited to 10 days on medical grounds and 5 days otherwise. "
                                 "[Source: Academic Regulations (UG & PG) 2019, p. 21]")
    return result


def log_unanswered_question(question: str, reason: str = "") -> dict:
    """Record a question the helpdesk could not answer so a human from the academic office can
    respond. Call this whenever you tell the student you do not know.

    Args:
        question: The student's question, verbatim.
        reason: Why it could not be answered, e.g. 'out of scope' or 'not found in documents'.
    """
    config.LOG_DIR.mkdir(exist_ok=True)
    entry = {"timestamp": datetime.now().isoformat(timespec="seconds"), "question": question,
             "reason": reason or "unspecified", "status": "pending_human_review"}
    with config.UNANSWERED_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"status": "logged", "message": "Question forwarded to the academic office for a human answer."}
