# Carried findings -- ss007-pep752-implicit-namespaces

generated: 2026-11-05T07:39:27-08:00
open: 5   adjudicated: 0   total: 5

Critical and High never appear here -- those route to BUILD immediately.
This is the Medium/Low/WARN ledger, collected across every stage and
decided TOGETHER, once, rather than one at a time as each stage runs.
An entry is closed only by an explicit `fix` or `wontfix`; a `wontfix`
states its reason. Nothing here is auto-closed and there is no allowlist.

| stage | source | check | sev | finding | verdict | reason |
|---|---|---|---|---|---|---|
| A | bench validate --qualitative-only | - | medium | [Low] Spec: [1_pep752] instruction.md is written in an extremely dense, run-on style with garbled grammar in several places; all requirements remain extractable and consistent with the tests, so the impact is readability only. | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Env: [1_pep752] Separate-verifier auxiliary files referenced by test.sh are not inlined, so E12 (separate-verifier contract completeness) cannot be fully confirmed from the provided materials. | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Meta: [1_pep752] README is not present among the inlined task files, so README quality / Model Analysis cannot be verified. | **OPEN** | - |
| A | bench validate --provenance-only | - | low | UNMEASURED (unparseable): no JSON document in the CLI output | **OPEN** | - |
| A | structural | - | warn | WARN Dockerfile — RUN uses 'name=$(...)' command substitution without an explicit 'SHELL ["/bin/bash", "-c"]' directive — dash (the default /bin/sh on Debian/Ubuntu base images) parses some of these patterns differently and may fail at build with "Syntax error - can't find = in ...". Either add a SHELL directive or write the RUN as `RUN bash -c "..."` | **OPEN** | - |
