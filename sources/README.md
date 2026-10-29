# IIT Jodhpur document dataset (28 documents)

Real IIT Jodhpur documents about rules and regulations, time tables, course registration, examinations, fees, recent office orders, hostel rules, and faculty/office email IDs. Collected 28 Oct 2026.

## Contents
- `emails/01–25`: official circulars sent to the institute email account (Registration Cell, Examination Cell, Office of Academics UG, Office of Students, Hostel Affairs, Director's Office, Dean of Administration, EE Department). One notice thread per file, with title/category/source/date metadata at the top.
- `00_iitj_official_email_directory.csv`: 167 official @iitj.ac.in IDs (faculty, deans, offices, cells, programme coordinators, mailing lists), compiled from the email headers.
- `web/27`: point-wise extraction of the Academic Regulations from academics.iitj.ac.in.
- `web/28`: links to 12 official PDFs (academic calendars, UG/PG/M.Sc./Ph.D. regulations) that you need to download manually.
- `index.csv`: file, title, category, source, date, size.

## Privacy and anonymization
- Student names, roll numbers and student emails were removed or replaced with dummy values (e.g. "Student A (B23XX0001)", student.a@example.com). Messages between students were dropped.
- One staff member's personal mobile number was replaced with a dummy value.
- Official faculty, office and functionary email IDs and office phone numbers were kept, since they are institutional contact details.

## Limitations
- PDF attachments in the emails (office-order PDFs, the bus schedule, slot-system sheets, forms) are not included. Each file lists them under "Attachments (not included)".
- Repeated "polite reminder" messages are condensed. Notice text is otherwise kept as sent.

## Additions on 28 Oct 2026 (helpdesk ingestion)
- `official/30-42`: the PDFs linked in `web/28`, plus the amendment circulars linked on the Academic Regulations page, downloaded from iitj.ac.in: academic calendars (AY 2026-27, executive AY 2026-27, Summer Term 2026, AY 2025-26, BS/B.Sc. 2nd year 2025-26, PG Certificate/Diploma/MBA Tech 2025-26, Summer Term 2025), PG Regulations (2022 onwards), M.S. by Research Regulations, IITJ-AIIMS joint Medical Technologies regulations, the 26 Oct 2020 amendment notification, Circular 52 (Examination Policy, 08 July 2024) and the 2026 holiday list. Titles and dates are in `catalog.csv`.
- `web/27_branch_change_and_academic_session_web.md` replaces the missing `web/27` extraction. The Academic Regulations web page repeats the 2019 regulations PDF and the 2022 PG regulations PDF almost word for word (about 98% of its text), so only the parts not in those PDFs are kept: the Branch Change section (applicable to UG students admitted in 2025-26; discontinued from AY 2026-27) and the B.Tech. Academic Session FAQ.
- Not ingested (listed in `.ingestignore`):
  - `web/28`, which is only a list of links.
  - `archive/superseded_regulations/`: B.Tech. 2013, old M.Sc. and Ph.D. 2014 regulations from the "Old Regulations" page. These are replaced by the 2019 UG/PG and 2022 PG regulations.
  - This README.
- Duplicates skipped: `web/28` item 8 is byte-identical to `1_Academic_Regulations_Final_03_09_2019.pdf`. The Academic Regulations page links three copies of that PDF and three copies of the 2020 amendment notification; one of each was kept.
- `00_iitj_official_email_directory.csv` has no duplicate addresses. Some roles have two IDs (e.g. ADAA: `adaa@` and `ad_academics@`); both are kept.
