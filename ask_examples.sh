#!/bin/sh
# Runs the example questions from the assignment brief through the multi-agent helpdesk.
cd "$(dirname "$0")"
PY=${PY:-.venv/bin/python}
while IFS= read -r q; do
  echo "Q: $q"
  $PY chat.py -q "$q" "$@" 2>/dev/null
  echo "------"
done <<'QUESTIONS'
What is the attendance requirement to sit in the Major exam?
What is the slot for the course Autonomous Systems?
How many 400 level electives have been floated by the Humanities department in this semester?
How many Open Elective credits do I need to earn in order to get a B.Tech. Degree?
Write an email to the course instructor of CSL7570 that I need leave for 2 days
What are the available dining options on the campus?
What is the best way to reach the campus from Jodhpur city center?
QUESTIONS
