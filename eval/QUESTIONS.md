# Evaluation question set

## Main set (`questions.json`): 30 questions

13 policy, 7 schedule, 4 email, 6 out-of-scope. All example questions from the assignment brief are included (P01, P02, S01, S02, E01, O01, O02). Used for every configuration in the report.

P08 expects 3 hours. The July 2024 examination-policy circular superseded the 120 minutes in the 2019 regulations; configs A-F and A2 predate the circular and were graded against 120 minutes.

| ID | Category | Question | Expected answer | Expected source |
|---|---|---|---|---|
| P01 | policy | What is the attendance requirement to sit in the Major exam? | Per the July 2024 circular, exam performance is no longer linked to attendance; attendance should still not fall below 75% in a course (below 75% without valid reason can lead to de-registration). | Attendance Policy, Circular |
| P02 | policy | How many Open Elective credits do I need to earn in order to get a B.Tech. Degree? | 10 credits of Open Electives (B.Tech. Regular), Table 11.2. | Academic Regulations |
| P03 | policy | What is the minimum CGPA required to opt for an Independent Study course? | CGPA of at least 6.0, with recommendation of the supervising professor. | Academic Regulations |
| P04 | policy | For how many days can a student be granted short leave on medical grounds during a semester? | Up to 10 days on medical grounds (5 days for any other valid reason). | Academic Regulations |
| P05 | policy | What happens if a student is absent for four or more weeks in a semester? | Automatic withdrawal from the semester / cancellation of registration from all courses. | Academic Regulations, Attendance Policy, Circular |
| P06 | policy | What is the maximum duration allowed for completing a B.Tech. programme? | 14 registered semesters. | Academic Regulations |
| P07 | policy | How many grade points does a B- grade carry? | 7 grade points (Good). | Academic Regulations |
| P08 | policy | What is the duration of the Major examination of a regular course? | 3 hours, per the July 2024 circular on the Examination Policy (it supersedes the 2019 regulations, which said 120 minutes). | Examination Policy, Circular |
| P09 | policy | How many credits must a GEN category B.Tech. student earn by the end of the second semester to continue in the programme? | 18 credits (14 for SC/ST/PD). | Academic Regulations |
| P10 | policy | When is an 'I' grade awarded to a student? | 'I' (Incomplete) is awarded on the student's request with instructor approval when an evaluation component is missed due to medical grounds or other special circumstances. | Academic Regulations |
| P11 | policy | What happens if a student remains absent from a class without sanctioned leave for more than two weeks? | The course instructor may recommend de-registration of the student from the course (2024 circular). | Attendance Policy, Circular |
| P12 | policy | How many Programme Elective credits are required for a regular B.Tech. degree? | 18 credits. | Academic Regulations |
| P13 | policy | To whom should a B.Tech. student address an application for leave of absence? | The Convener, DUGC (with a medical certificate if applicable). | Academic Regulations |
| S01 | schedule | What is the slot for the course Autonomous Systems? | Slot C (Mon 10:00, Tue 11:00, Thu 10:00). | Course Timetable, courses_offered |
| S02 | schedule | How many 400 level electives have been floated by the Humanities department in this semester? | 4 (HSL4010, HSL4020, HSL4030, HSL4040). | Course Timetable, courses_offered |
| S03 | schedule | Who teaches CSL7620 Machine Learning this semester? | Dr. Kavya Rao. | Course Timetable, courses_offered |
| S04 | schedule | On which days and at what time are the classes of slot H held? | Monday and Thursday, 15:00-16:25. | Slot Timings, slot_timings |
| S05 | schedule | What is the L-T-P structure of the Deep Learning course? | 3-0-2 (3 credits). | Course Timetable, courses_offered |
| S06 | schedule | Which lab slot does CSL2010 have? | L1 (Monday 14:00-16:55). | Course Timetable, courses_offered |
| S07 | schedule | Which open electives are being offered this semester? | MAL4010 Optimization Methods and BBL4010 Bioinformatics. | Course Timetable, courses_offered |
| E01 | email | Write an email to the course instructor of CSL7570 that I need leave for 2 days | Draft to arjun.mehta@dummy.iitj.ac.in requesting 2 days of leave for CSL7570. | Faculty Directory, faculty_directory, Course Timetable |
| E02 | email | What is the email ID of the instructor of Natural Language Understanding? | nikhil.joshi@dummy.iitj.ac.in (Dr. Nikhil Joshi). | Faculty Directory, faculty_directory, Course Timetable |
| E03 | email | I missed the Minor 1 exam of CSL3010 because of fever. Draft an email to the instructor asking for a makeup exam. | Draft to rahul.bansal@dummy.iitj.ac.in requesting a make-up for Minor 1. | Faculty Directory, faculty_directory, Course Timetable |
| E04 | email | Draft a sick leave email to the instructor of Control Systems for 3 days, I have viral fever. | Draft to pooja.saxena@dummy.iitj.ac.in requesting 3 days of medical leave. | Faculty Directory, faculty_directory, Course Timetable |
| O01 | out_of_scope | What are the available dining options on the campus? | Refuse ("I don't know") and log the question. | - |
| O02 | out_of_scope | What is the best way to reach the campus from Jodhpur city center? | Refuse ("I don't know") and log the question. | - |
| O03 | out_of_scope | What is the hostel fee for B.Tech. students this year? | Refuse ("I don't know") and log the question. | - |
| O04 | out_of_scope | Who won the IPL in 2024? | Refuse ("I don't know") and log the question. | - |
| O05 | out_of_scope | Which companies visited IIT Jodhpur for placements last year? | Refuse ("I don't know") and log the question. | - |
| O06 | out_of_scope | Is the central library open on Sundays? | Refuse ("I don't know") and log the question. | - |

## New-source set (`questions_new_sources.json`): 12 questions

Questions that only the documents added later (academic calendars, notices, circulars, website extract) can answer, plus one out-of-scope trap: the bus timetable is an attachment that is not in the corpus.

| ID | Category | Question | Expected answer | Expected source |
|---|---|---|---|---|
| N01 | calendar | When do classes commence for Semester II of AY 2026-27? | 4 January 2027 (Monday), Academic Calendar AY 2026-27. | Academic Calendar AY 2026-27 |
| N02 | calendar | When are the Minor examinations of Semester I, AY 2026-27? | 15 to 20 September 2026. | Academic Calendar AY 2026-27, Minor Examination |
| N03 | calendar | Which day's time table will be followed on 24 September 2026? | Friday's time table (24 September 2026 is a Thursday). | Academic Calendar AY 2026-27, Friday's Time Table |
| N04 | calendar | Is 20 October 2026 an institute holiday? | Yes, Dussehra (Vijay Dashmi). | Holidays, Academic Calendar |
| N05 | notices | What is the fine for late course registration? | Rs. 1500, paid before the last date of add/drop. | Main Registration |
| N06 | notices | How many credits can a UG student register for in the summer term? | Up to a maximum of eight credits (more needs special approval). | Summer Term |
| N07 | notices | What is the fee per course for a General category student in the Summer Term 2026? | Rs 15000 per course (Rs 2000 for SC/ST/PH). | Summer Term |
| N08 | notices | What is the upper cap on the number of students in an Institute Humanities elective? | 80 students, allocated by CGPA. | Main Registration, Pre-Registration |
| N09 | notices | What happens if a student does not submit the course feedback? | The grade of that course will not be visible to the student. | Feedback |
| N10 | rules | What is the duration of the Minor examination? | 2 hours, per the July 2024 Examination Policy circular (the 2019 regulations said 60 minutes). | Examination Policy, Circular |
| N11 | rules | Can a B.Tech. student admitted in AY 2026-27 change their branch? | No. Branch change is discontinued in UG programmes from AY 2026-27 (the branch change rules apply to students admitted in 2025-26). | Branch Change |
| N12 | out_of_scope | At what time does the institute bus leave for the city? | Refuse ("I don't know") and log the question. | - |

Grading keywords for each question are in the JSON files. Manual overrides of the keyword grader are in `manual_audit.json`.
