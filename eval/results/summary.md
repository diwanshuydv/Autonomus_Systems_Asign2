# Evaluation summary

| Configuration | Model | Mode | Think | Runs | Accuracy (in-scope, auto) | Accuracy (audited) | Correct citation | Citations genuine | Retrieval/tool hit | Correct refusal (OOS) | False refusal | Refusals logged | Routing acc. | Latency (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2_qwen3-1.7b_multi_v2 | qwen3:1.7b | multi | policy | 3 | 86% | 83% | 89% | 100% | 92% | 100% | 11% | 100% | 96% | 12.37 |
| A3_qwen3-1.7b_multi_v3_sources | qwen3:1.7b | multi | policy | 3 | 93% | 92% | 86% | 100% | 96% | 100% | 4% | 100% | 100% | 9.37 |
| A_qwen3-1.7b_multi | qwen3:1.7b | multi | policy | 3 | 76% | 72% | 88% | 100% | 88% | 100% | 11% | 100% | 96% | 11.39 |
| B_qwen3-1.7b_single | qwen3:1.7b | single | policy | 3 | 18% | 18% | 68% | 39% | 46% | 100% | 61% | 100% | - | 5.21 |
| C_qwen3-1.7b_multi_nothink | qwen3:1.7b | multi | none | 1 | 79% | 71% | 86% | 100% | 88% | 100% | 8% | 100% | 96% | 8.15 |
| D_qwen3-8b_multi | qwen3:8b | multi | policy | 1 | 92% | 92% | 91% | 100% | 100% | 100% | 4% | 100% | 100% | 52.17 |
| E_llama3.1-8b_multi | llama3.1:8b | multi | policy | 1 | 92% | 88% | 78% | 100% | 92% | 100% | 4% | 100% | 92% | 247.73 |
| F_qwen3-8b_multi-transfer | qwen3:8b | multi-transfer | policy | 1 | 71% | 71% | 89% | 100% | 83% | 100% | 25% | 100% | 83% | 98.24 |
| N_qwen3-1.7b_multi_new_sources | qwen3:1.7b | multi | policy | 3 | 94% | 88% | 94% | 97% | 100% | 100% | 3% | 100% | 100% | 15.34 |

## Accuracy by category

| Configuration | calendar | email | notices | out_of_scope | policy | rules | schedule |
|---|---|---|---|---|---|---|---|
| A2_qwen3-1.7b_multi_v2 | - | 100% | - | 100% | 90% | - | 71% |
| A3_qwen3-1.7b_multi_v3_sources | - | 100% | - | 100% | 97% | - | 81% |
| A_qwen3-1.7b_multi | - | 100% | - | 100% | 77% | - | 62% |
| B_qwen3-1.7b_single | - | 50% | - | 100% | 0% | - | 33% |
| C_qwen3-1.7b_multi_nothink | - | 100% | - | 100% | 85% | - | 57% |
| D_qwen3-8b_multi | - | 100% | - | 100% | 85% | - | 100% |
| E_llama3.1-8b_multi | - | 75% | - | 100% | 92% | - | 100% |
| F_qwen3-8b_multi-transfer | - | 25% | - | 100% | 69% | - | 100% |
| N_qwen3-1.7b_multi_new_sources | 100% | - | 87% | 100% | - | 100% | - |

## Per-question correct runs

| Question | A2_qwen3-1.7b_multi_v2 | A3_qwen3-1.7b_multi_v3_sources | A_qwen3-1.7b_multi | B_qwen3-1.7b_single | C_qwen3-1.7b_multi_nothink | D_qwen3-8b_multi | E_llama3.1-8b_multi | F_qwen3-8b_multi-transfer | N_qwen3-1.7b_multi_new_sources |
|---|---|---|---|---|---|---|---|---|---|
| E01 | 3/3 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | 0/1 | - |
| E02 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| E03 | 3/3 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | 0/1 | - |
| E04 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 0/1 | 0/1 | - |
| N01 | - | - | - | - | - | - | - | - | 3/3 |
| N02 | - | - | - | - | - | - | - | - | 3/3 |
| N03 | - | - | - | - | - | - | - | - | 3/3 |
| N04 | - | - | - | - | - | - | - | - | 3/3 |
| N05 | - | - | - | - | - | - | - | - | 3/3 |
| N06 | - | - | - | - | - | - | - | - | 1/3 |
| N07 | - | - | - | - | - | - | - | - | 3/3 |
| N08 | - | - | - | - | - | - | - | - | 3/3 |
| N09 | - | - | - | - | - | - | - | - | 3/3 |
| N10 | - | - | - | - | - | - | - | - | 3/3 |
| N11 | - | - | - | - | - | - | - | - | 3/3 |
| N12 | - | - | - | - | - | - | - | - | 3/3 |
| O01 | 3/3 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| O02 | 3/3 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| O03 | 3/3 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| O04 | 3/3 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| O05 | 3/3 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| O06 | 3/3 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| P01 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| P02 | 2/3 | 2/3 | 3/3 | 0/3 | 0/1 | 1/1 | 1/1 | 0/1 | - |
| P03 | 0/3 | 3/3 | 0/3 | 0/3 | 0/1 | 0/1 | 1/1 | 0/1 | - |
| P04 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| P05 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| P06 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| P07 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| P08 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| P09 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| P10 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| P11 | 3/3 | 3/3 | 0/3 | 0/3 | 1/1 | 0/1 | 1/1 | 0/1 | - |
| P12 | 3/3 | 3/3 | 1/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| P13 | 3/3 | 3/3 | 2/3 | 0/3 | 1/1 | 1/1 | 0/1 | 0/1 | - |
| S01 | 3/3 | 3/3 | 3/3 | 0/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| S02 | 3/3 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| S03 | 3/3 | 3/3 | 3/3 | 1/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| S04 | 3/3 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | 1/1 | - |
| S05 | 0/3 | 2/3 | 1/3 | 0/3 | 0/1 | 1/1 | 1/1 | 1/1 | - |
| S06 | 3/3 | 3/3 | 0/3 | 0/3 | 0/1 | 1/1 | 1/1 | 1/1 | - |
| S07 | 0/3 | 0/3 | 0/3 | 0/3 | 0/1 | 1/1 | 1/1 | 1/1 | - |

## Questions whose answers changed across runs

### A2_qwen3-1.7b_multi_v2
- **P01** What is the attendance requirement to sit in the Major exam? - correct in 3/3 runs, min. pairwise answer similarity 0.401
- **P02** How many Open Elective credits do I need to earn in order to get a B.Tech. Degree? - correct in 2/3 runs, min. pairwise answer similarity 0.193
- **P03** What is the minimum CGPA required to opt for an Independent Study course? - correct in 0/3 runs, min. pairwise answer similarity 0.156
- **P04** For how many days can a student be granted short leave on medical grounds during a semester? - correct in 3/3 runs, min. pairwise answer similarity 0.557
- **P05** What happens if a student is absent for four or more weeks in a semester? - correct in 3/3 runs, min. pairwise answer similarity 0.545
- **P11** What happens if a student remains absent from a class without sanctioned leave for more than two weeks? - correct in 3/3 runs, min. pairwise answer similarity 0.421
- **P12** How many Programme Elective credits are required for a regular B.Tech. degree? - correct in 3/3 runs, min. pairwise answer similarity 0.341
- **P13** To whom should a B.Tech. student address an application for leave of absence? - correct in 3/3 runs, min. pairwise answer similarity 0.196
- **S05** What is the L-T-P structure of the Deep Learning course? - correct in 0/3 runs, min. pairwise answer similarity 0.126

### A3_qwen3-1.7b_multi_v3_sources
- **P02** How many Open Elective credits do I need to earn in order to get a B.Tech. Degree? - correct in 2/3 runs, min. pairwise answer similarity 0.242
- **P03** What is the minimum CGPA required to opt for an Independent Study course? - correct in 3/3 runs, min. pairwise answer similarity 0.504
- **P07** How many grade points does a B- grade carry? - correct in 3/3 runs, min. pairwise answer similarity 0.521
- **P10** When is an 'I' grade awarded to a student? - correct in 3/3 runs, min. pairwise answer similarity 0.157
- **P11** What happens if a student remains absent from a class without sanctioned leave for more than two weeks? - correct in 3/3 runs, min. pairwise answer similarity 0.255
- **P12** How many Programme Elective credits are required for a regular B.Tech. degree? - correct in 3/3 runs, min. pairwise answer similarity 0.424
- **S01** What is the slot for the course Autonomous Systems? - correct in 3/3 runs, min. pairwise answer similarity 0.185
- **S05** What is the L-T-P structure of the Deep Learning course? - correct in 2/3 runs, min. pairwise answer similarity 0.455

### A_qwen3-1.7b_multi
- **P01** What is the attendance requirement to sit in the Major exam? - correct in 3/3 runs, min. pairwise answer similarity 0.286
- **P02** How many Open Elective credits do I need to earn in order to get a B.Tech. Degree? - correct in 3/3 runs, min. pairwise answer similarity 0.389
- **P03** What is the minimum CGPA required to opt for an Independent Study course? - correct in 0/3 runs, min. pairwise answer similarity 0.486
- **P04** For how many days can a student be granted short leave on medical grounds during a semester? - correct in 3/3 runs, min. pairwise answer similarity 0.463
- **P05** What happens if a student is absent for four or more weeks in a semester? - correct in 3/3 runs, min. pairwise answer similarity 0.34
- **P11** What happens if a student remains absent from a class without sanctioned leave for more than two weeks? - correct in 0/3 runs, min. pairwise answer similarity 0.174
- **P12** How many Programme Elective credits are required for a regular B.Tech. degree? - correct in 1/3 runs, min. pairwise answer similarity 0.168
- **P13** To whom should a B.Tech. student address an application for leave of absence? - correct in 2/3 runs, min. pairwise answer similarity 0.457
- **S05** What is the L-T-P structure of the Deep Learning course? - correct in 1/3 runs, min. pairwise answer similarity 0.069

### B_qwen3-1.7b_single
- **P11** What happens if a student remains absent from a class without sanctioned leave for more than two weeks? - correct in 0/3 runs, min. pairwise answer similarity 0.304
- **S03** Who teaches CSL7620 Machine Learning this semester? - correct in 1/3 runs, min. pairwise answer similarity 0.696

### N_qwen3-1.7b_multi_new_sources
- **N01** When do classes commence for Semester II of AY 2026-27? - correct in 3/3 runs, min. pairwise answer similarity 0.512
- **N03** Which day's time table will be followed on 24 September 2026? - correct in 3/3 runs, min. pairwise answer similarity 0.418
- **N05** What is the fine for late course registration? - correct in 3/3 runs, min. pairwise answer similarity 0.516
- **N06** How many credits can a UG student register for in the summer term? - correct in 1/3 runs, min. pairwise answer similarity 0.189

