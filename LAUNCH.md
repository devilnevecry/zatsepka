# Launch prompts

Put PROJECT.md (and docs/reference/) into an empty project folder, then give the agent ONE of the prompts below.

## A. Single agent (Kilo Code / opencode / Claude Code / Cursor)
Read PROJECT.md completely and build the entire project autonomously, from stage 1 to the final acceptance in stage 12, following its rules to the letter. Do not stop for stage reports, do not ask me questions or for more prompt text; resolve ambiguity with the defaults in the file. Keep going until FINAL_REPORT.md exists and the acceptance checks pass. Write progress only to PROGRESS.md. Message me once, at the very end.

## B. Kilo orchestrator
You are the orchestrator. PROJECT.md is the full specification and the only source of truth. Drive the project autonomously to a finished, tested result: delegate stages 1-12 to code agents strictly in order (all stages touch the browser profile or the shared codebase, so no parallel stages), giving each sub-task the stage text, the Autonomy rules, the Token and loop discipline and the Testing standard from PROJECT.md. After every sub-task verify the result yourself by running the tests and checking the Definition of Done; if it fails, send a fix task with the exact failing output (max 3 attempts, then follow the failure ladder). Do not stop for phase reports and do not ask me to write or extend prompts. Report to me once, after FINAL_REPORT.md exists and acceptance passes.

## C. If the agent stops early
Continue the project. Read PROJECT.md and PROGRESS.md, resume from the first unfinished stage, do not recap, do not ask questions, keep going until FINAL_REPORT.md exists.
