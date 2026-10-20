# CodeQuest API — requirements

Each requirement has an ID, the implementation phase, the requirement and its acceptance criterion. Functional tests under `tests/functional/` prove each criterion through the HTTP API and carry `@pytest.mark.req("<ID>")`. Rows whose criterion starts with `MANUAL:` are checked by inspection. `tools/traceability.py` builds `docs/evidence/traceability.md` from this table.

## Functional requirements

| ID | Phase | Requirement | Acceptance |
|---|---|---|---|
| RF-01 | 3 | Student sign-up with username and password; professor accounts only by command line | Sign-up returns 201 and the student can log in; duplicate username returns 409; invalid username or password returns 422; there is no endpoint that creates a professor. |
| RF-02 | 3 | Login with token; access by role, ownership and class membership | Login returns a bearer token; protected endpoints without a valid token return 401; students get 403 on professor endpoints; a professor gets 404 on another professor's resources; a student gets 404 on content of a class they do not belong to. |
| RF-03 | 4 | Professor creates classes, missions and challenges of the four types | A professor creates a class (6-character join code returned), a mission in it, and one challenge of each type; all are listed back with the sent values. |
| RF-04 | 4 | Template rules validated on create, update and publish; no empty mission is published | A challenge breaking any template rule returns 422 with a Portuguese message and is not stored; publishing re-validates; publishing a mission without a published challenge returns 409. |
| RF-05 | 5 | Student sees published base missions and the missions of their classes, in any order | A new student sees the base missions; after joining a class they also see its published missions; draft missions and missions of other classes never appear and return 404; any challenge of a visible mission can be opened without solving the previous ones. |
| RF-06 | 5 | Deterministic grading per type; unlimited attempts | For each type, the correct answer returns `is_correct: true` and a wrong one `false`; a malformed answer returns 422 and is not counted; wrong answers can be repeated without limit. |
| RF-07 | 5 | XP only on the first solve, by attempts; level and title computed from XP | A solve on the first try gives 10 XP, after one or two wrong answers 5 XP, after three or more 2 XP; solving again, wrong answers and hints give 0; level is `xp // 50 + 1` and the title matches the level band. |
| RF-08 | 5 | Tiered badges by milestones, shown with XP and level | After the first solve the response lists the `first_solve` badge once; the profile lists all badges with tier and emoji, earned ones marked, hidden ones not yet earned shown as "Insígnia secreta" without condition, together with XP, level and title. |
| RF-09 | 6 | Global and class rankings, weekly and monthly; student sees self ± 2 | A student's ranking, in each scope and period, contains at most 5 entries including themself with `is_me: true`; ties share the position; a class ranking counts only XP from that class's challenges; the professor's class ranking lists every student of the class. |
| RF-10 | 5 | Streak without XP | The profile shows streak 0 before any solve and 1 after a solve today; the streak never changes XP. |
| RF-11 | 5 | Daily challenge per student among unsolved challenges | The daily challenge is a visible challenge the student had not solved; asking again the same day returns the same challenge, also after solving it; a student with nothing left to solve gets `challenge: null` and `all_solved: true`. |
| RF-12 | 7 | Hint on request through a button: limit, wait and increasing detail | Each request returns a hint with level 1, 2, 3, 3, … and `hints_left` decreases by 1; a request before the wait ends returns 429 `hint_cooldown` with `retry_after`; after the limit the request returns 409 `hint_cap_reached`; a solved challenge returns 409 `already_solved`. |
| RF-13 | 7 | One automatic hint after the first wrong answer, with the answer in the request | The first wrong submission returns a hint and does not change `hints_left`; later wrong submissions return `hint: null`; the request sent to the AI contains the submitted answer. |
| RF-14 | 7 | AI review of a professor's challenge, suggestions only | Review returns `rule_violations` and `suggestions`; the challenge is unchanged afterwards. |
| RF-15 | 7 | AI draft saved as draft, with published examples of the same type in the request | A draft request creates a challenge with `status: draft` and `origin: ai`; the request sent to the AI contains at most 3 published challenges of the same type from the same professor; an invalid AI answer returns 422 and stores nothing. |
| RF-16 | 6 | Professor sees progress, completion rate, full ranking and solve statistics | The progress endpoint returns, per student, XP in the class, level, solved count, missions completed, hints used and streak, plus the percentage of students who completed every mission, matching the actions performed; the challenge list shows how many distinct students tried and solved each challenge. |
| RF-17 | 5 | Profile | The profile returns username, level, title, XP, XP to next level, streak, badges, missions completed, solved count per skill and first-try solves. |
| RF-18 | 3 | Students join and leave classes with a code, in several classes at once | A valid code adds the student to the class; an unknown code returns 404; joining twice changes nothing; a student can belong to two classes; after leaving, the class's missions return 404 and the student's XP and badges are unchanged. |
| RF-19 | 6 | Weekly class goal shared by its members | The class goal shows target and progress; each first solve by a member on the class's challenges adds 1; when the target is reached every member who contributed that week receives the `class_goal_1` badge once and members who did not contribute do not; a target set by the professor replaces the automatic one; the target never exceeds the first solves the members can still make, and a class with nothing left to solve has `goal: null`. |
| RF-20 | 6 | Optional public profile | With the setting off (default) the public profile returns 404; with it on, any logged-in user gets the username, level, title and earned badges. |
| RF-21 | 8 | Base game available to every student | After loading the base content, a newly registered student sees the base missions with challenges of the four types; loading again creates nothing new. |
| RF-22 | 4 | Editing a challenge after students answered it | Text changes are accepted at any time; changing the type, items or solution of a challenge that already has answers returns 409; duplicating creates a draft copy that can be changed freely. |

## Safeguards

| ID | Phase | Requirement | Acceptance |
|---|---|---|---|
| SG-01 | 7 | The hint request to the AI contains the statement, the solution, the level and the instruction not to reveal it | Each hint request sent to the AI contains the statement, every item text, the solution, the hint level and the "nunca revele a solução" instruction. |
| SG-02 | 5 | No free-text channel from the student to the AI | No student endpoint accepts free text that is sent to the AI; hint endpoints take no body. |
| SG-03 | 7 | A hint that contains the solution is discarded | When the AI returns a hint that contains the solution, the student receives the fixed fallback hint instead, and the discarded hint does not count toward the limit. |
| SG-04 | 7 | Hint limit and wait enforced | With the default limit of 5, the 6th requested hint for the same challenge returns 409; two requests closer than the configured wait return 429. |
| SG-05 | 7 | No AI draft reaches students without professor approval | An AI draft is not visible to students until the professor publishes it. |
| SG-06 | 7 | No personal data in any request to the AI | No request sent to the AI contains the username, user id or class name, for every AI feature. |
| SG-07 | 5 | XP only from solved challenges | Logging in, time passing, the streak, the daily challenge, the class goal, badges and hints never create XP. |
| SG-08 | 5 | The student API never returns the solution | No student response contains a `solution` key at any depth, for every type; the explanation appears only after a correct answer. |
| SG-09 | 3 | Only username and password are collected; password stored as a hash | Sign-up accepts only username and password; no response contains the password or its hash. |
| SG-10 | 6 | Rankings by period | The weekly rankings count XP from Monday 00:00 (São Paulo) and the monthly rankings from day 1; XP earned now appears in both. |
| SG-11 | 5 | Game elements are not shown in isolation | MANUAL: inspect the student screens; badges always appear next to XP, level and title. |
| SG-12 | 8 | Base challenges need no programming knowledge | MANUAL: inspect the base game statements against the Bebras criteria cited in the text. |
| SG-13 | 6 | Public profile is private by default and minimal | A new account has `profile_public: false`; the public profile response has exactly the fields username, level, title and badges. |

## Non-functional requirements

| ID | Phase | Requirement | Acceptance |
|---|---|---|---|
| RNF-01 | 0 | Layered architecture enforced by automated checks | MANUAL: `lint-imports` passes with the layer contracts in `pyproject.toml` and a violating import makes it fail (checked by the phase gate, not over HTTP). |
| RNF-02 | 7 | AI provider replaceable by configuration | The server runs with `LLM_PROVIDER=fake`; the provider is chosen only by environment variables. |
| RNF-03 | 7 | The application keeps working when the AI fails | With the AI failing, hint requests return 200 with the fallback hint and review still returns `rule_violations`. |
| RNF-05 | 0 | Error messages in Portuguese | Every error response has `detail` (code) and a Portuguese `message`. |
