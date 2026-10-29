# Structured data used by the lookup tools

These CSV files are read directly by the tools in `helpdesk/tools.py` (they are not embedded in
the vector store). **The values shipped here are SAMPLE / DUMMY data** created so that the
timetable, course-count and email questions can be exercised end to end. Faculty names and
email addresses are fictitious (`@dummy.iitj.ac.in`). Replace the rows with the real timetable
and faculty list for the current semester; keep the column names.

| File | Columns | Used by |
|---|---|---|
| `courses_offered.csv` | course_code, course_title, department (code), level (100..800), credits, ltp, category, slot, lab_slot, instructor | `get_course_info`, `list_courses`, `get_instructor_contact`, `draft_email` |
| `slot_timings.csv` | slot, day, start_time, end_time, session_type | `get_course_info`, `get_slot_timings` |
| `faculty_directory.csv` | name, department, designation, email, office | `get_instructor_contact`, `draft_email` |
| `departments.csv` | code, name, aliases (`;`-separated) | resolves "Humanities", "HSS", "CSE"... to department codes |

Notes
- `category` is free text; `list_courses(category="elective")` matches any category containing
  "elective" (Programme Elective, Open Elective, HSS Elective).
- `instructor` in `courses_offered.csv` must match `name` in `faculty_directory.csv` exactly.
- The semester label shown in citations is `HELPDESK_SEMESTER` (default "Semester I, AY 2026-27").
