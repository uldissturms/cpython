# Carried findings -- ss007-pep752-implicit-namespaces

generated: 2026-11-04T11:12:16-08:00
open: 11   adjudicated: 0   total: 11

Critical and High never appear here -- those route to BUILD immediately.
This is the Medium/Low/WARN ledger, collected across every stage and
decided TOGETHER, once, rather than one at a time as each stage runs.
An entry is closed only by an explicit `fix` or `wontfix`; a `wontfix`
states its reason. Nothing here is auto-closed and there is no allowlist.

| stage | source | check | sev | finding | verdict | reason |
|---|---|---|---|---|---|---|
| A | bench validate --qualitative-only | - | medium | [Critical] Solution: [1_pep752] The reference (gold) patch fails a fail_to_pass test: metadata.py `simple_html` renders indented HTML with ` <head><title>Links for ...</title></head>` on one line, but `test.test_pep752_metadata.MetadataTests.test_html_byte_stable` asserts byte-equality against a NON-indented layout with `<head>`, `<title>`, `</head>` on three separate lines (and no leading spaces | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Medium] Spec: [1_pep752] Direction A gap: `test_html_byte_stable` enforces an exact HTML byte format that instruction.md never specifies. The spec only states the HTML Simple API is 'unchanged', carries 'no namespace metadata', and 'escapes special characters'. The precise indentation/line structure is a graded axis omitted from the spec, so even absent the gold mismatch a correct engineer could | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Meta: [1_pep752] README.md is not present among the provided task files (P18 checks `<task-dir>/README.md`). README is not agent-facing, so impact is limited to missing author Model Analysis / Oracle-pass documentation — which is precisely where the broken-gold defect should have been caught. | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Env: [1_pep752] task.toml declares a separate verifier (`[steps.verifier] environment_mode = "separate"`) but the provided tests/ directory contains only config.json, test.sh, run_script.sh, and parser.py — no tests/Dockerfile is shown. If a separate verifier image is genuinely required, the contract may be incomplete; if the verifier reuses the build image, this is benign. Cannot be confirm | **OPEN** | - |
| A | bench validate --provenance-only | - | low | UNMEASURED (unparseable): no JSON document in the CLI output | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Medium] Tests: [1_pep752] test_html_byte_stable asserts a byte-exact HTML Simple-API page (exact DOCTYPE casing, 2-space indent, single-line <head>, <br/> style), but instruction.md only states `HTML Simple API is unchanged`, `contains no namespace metadata`, and `escapes special characters`. The exact template is the reference implementation's choice and is not PEP 503-canonical, so a reasonable | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Meta: [1_pep752] README.md for the task was not present in the provided materials; could not confirm presence/quality (Model Analysis, Oracle pass-rate). README is not agent-facing, so impact is limited to reviewer/platform metadata. | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Tests: [1_pep752] Documentation fail_to_pass tests verify only substring presence, so they are satisfiable with minimal doc stubs rather than genuine documentation. | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Env: [1_pep752] task.toml declares [steps.verifier] environment_mode = "separate" and artifacts = ["/app"], but no tests/Dockerfile was present among the provided tests/ files. If the separate-verifier image contract is not completed by the platform, verifier staging could be incomplete. The Dockerfile's symlink-delinking step shows the author engineered for separate-verifier artifact captur | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Spec: [1_pep752] Prose `API_VERSION = 1.5` reads as a float while tests require the string "1.5"; resolved only by the quoted JSON envelope example. A careful reader derives the correct type, but it is a minor inconsistency in the spec text. | **OPEN** | - |
| A | structural | - | warn | WARN Dockerfile — RUN uses 'name=$(...)' command substitution without an explicit 'SHELL ["/bin/bash", "-c"]' directive — dash (the default /bin/sh on Debian/Ubuntu base images) parses some of these patterns differently and may fail at build with "Syntax error - can't find = in ...". Either add a SHELL directive or write the RUN as `RUN bash -c "..."` | **OPEN** | - |
