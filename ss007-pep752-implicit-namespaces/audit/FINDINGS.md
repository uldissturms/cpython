# Carried findings -- ss007-pep752-implicit-namespaces

generated: 2026-11-04T15:55:01-08:00
open: 6   adjudicated: 0   total: 6

Critical and High never appear here -- those route to BUILD immediately.
This is the Medium/Low/WARN ledger, collected across every stage and
decided TOGETHER, once, rather than one at a time as each stage runs.
An entry is closed only by an explicit `fix` or `wontfix`; a `wontfix`
states its reason. Nothing here is auto-closed and there is no allowlist.

| stage | source | check | sev | finding | verdict | reason |
|---|---|---|---|---|---|---|
| A | bench validate --qualitative-only | - | medium | [Low] Spec: [1_pep752] Overlap-detection algorithm is prescribed in prose rather than left to the engineer: 'overlap appends a hyphen to both normalized names and overlap is detected in both directions'. This mildly spoils the mechanism for grants_overlap, though it chiefly defines the foo/foobar edge-case semantics that tests check behaviorally. | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Tests: [1_pep752] test_html_semantically_stable asserts a specific HTML Simple API structure ('Links for <project>' in title/h1 and `<a href=...>filename</a>` anchors) that instruction.md does not state explicitly — it only says the HTML API is unchanged, carries no namespace metadata, and escapes special characters. The format is inferable from the PEP 503 convention, and the test regex is | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Meta: [1_pep752] README.md is not present in the inlined task files, so README section completeness (Oracle pass-rate, Model Analysis, etc.) cannot be verified. README is not agent-facing, so this is cosmetic. | **OPEN** | - |
| A | bench validate --qualitative-only | - | medium | [Low] Env: [1_pep752] task.toml declares a separate verifier (environment_mode = 'separate', artifacts = ['/app']) but tests/Dockerfile is not inlined, so the separate-verifier contract cannot be fully confirmed statically. Additionally, run_script.sh performs a full `make` + `make install DESTDIR` inside the verifier to satisfy InstallTests, which increases false-negative/flakiness risk; the Dock | **OPEN** | - |
| A | bench validate --provenance-only | - | low | UNMEASURED (unparseable): no JSON document in the CLI output | **OPEN** | - |
| A | structural | - | warn | WARN Dockerfile — RUN uses 'name=$(...)' command substitution without an explicit 'SHELL ["/bin/bash", "-c"]' directive — dash (the default /bin/sh on Debian/Ubuntu base images) parses some of these patterns differently and may fail at build with "Syntax error - can't find = in ...". Either add a SHELL directive or write the RUN as `RUN bash -c "..."` | **OPEN** | - |
