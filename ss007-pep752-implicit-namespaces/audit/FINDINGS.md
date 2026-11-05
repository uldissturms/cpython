# Carried findings -- ss007-pep752-implicit-namespaces

generated: 2026-11-05T08:29:30-08:00
open: 0   adjudicated: 5   total: 5

Critical and High never appear here -- those route to BUILD immediately.
This is the Medium/Low/WARN ledger, collected across every stage and
decided TOGETHER, once, rather than one at a time as each stage runs.
An entry is closed only by an explicit `fix` or `wontfix`; a `wontfix`
states its reason. Nothing here is auto-closed and there is no allowlist.

| stage | source | check | sev | finding | verdict | reason |
|---|---|---|---|---|---|---|
| A | bench validate --qualitative-only | - | medium | [Low] Spec: [1_pep752] instruction.md is written in an extremely dense, run-on style with garbled grammar in several places; all requirements remain extractable and consistent with the tests, so the impact is readability only. | wontfix | Dense anchor prose is readability-only: every requirement extracts (oracle 1.0, INSTRUCTION_FACTS/anchors green, human_voice gate passed). Rewording at PUSH would invalidate validated Stage A/B artifacts for zero grading gain. |
| A | bench validate --qualitative-only | - | medium | [Low] Env: [1_pep752] Separate-verifier auxiliary files referenced by test.sh are not inlined, so E12 (separate-verifier contract completeness) cannot be fully confirmed from the provided materials. | wontfix | Aux files exist in-task (tests/test.sh, parser.py, probe.py, run_script.sh, config.json, tree_manifest.json); not-inlined is the check material-set boundary, and E12 separation is evidenced by the committed verifier design. |
| A | bench validate --qualitative-only | - | medium | [Low] Meta: [1_pep752] README is not present among the inlined task files, so README quality / Model Analysis cannot be verified. | wontfix | README.md present at task root; not-inlined is the check material-set boundary, not a task gap. |
| A | bench validate --provenance-only | - | low | UNMEASURED (unparseable): no JSON document in the CLI output | wontfix | Provenance verified by dedicated gates (provenance=ok, provenance_platform=ok); unparseable CLI output is a check-side measurement gap with no task-side artifact to repair. |
| A | structural | - | warn | WARN Dockerfile — RUN uses 'name=$(...)' command substitution without an explicit 'SHELL ["/bin/bash", "-c"]' directive — dash (the default /bin/sh on Debian/Ubuntu base images) parses some of these patterns differently and may fail at build with "Syntax error - can't find = in ...". Either add a SHELL directive or write the RUN as `RUN bash -c "..."` | wontfix | Advisory static-match: every task image (coverage, oracle, k1, AFTR) builds green repeatedly with zero observed dash failures; reviewer directives order not to edit the task to silence it. |
