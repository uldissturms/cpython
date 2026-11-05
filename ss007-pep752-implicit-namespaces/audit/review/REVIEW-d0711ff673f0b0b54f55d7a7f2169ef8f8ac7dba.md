# LH review (beta) — ss007-pep752-implicit-namespaces

**AFTR verdict: BAD_LEAKAGE**

AFTR plus the three long-horizon checks and codimango's validation signals.
The wrapper adds no verdict and re-rates nothing: AFTR's verdict is AFTR's,
and the LH checks are measurements.

## 0. Evidence provenance

**Evidence: rollouts from this machine.**

Codimango's data was not used — codimango has no jobs for this task, or the CLI could not reach it.

- Task files checked: 75 (instructions, tests, solution, environment)
- Most recently edited: `build/.coverage-build.log`, 03:43 UTC on 5 Nov
- Git: `d0711ff673f0` — clean

| Job | Matches current files? | How established |
|---|---|---|
| `2026-11-04__19-47-20__3384dc` | yes, as far as mtime shows | mtime |

_`mtime` compares the newest graded file against the job start. It errs toward stale: a `git checkout` rewrites mtimes without changing content._

## 1. Agentic Full-Task Review

**Source: local re-run** (codimango has no AFTR for this commit).

**Verdict: BAD_LEAKAGE**  ·  Difficulty: MIXED  ·  Tier: container

- Prompt: `manifold:aai_eval_baselines/tree/agentic-review-resources/prompts`
- Prompt sha256: `12a7e6acf75beaf3…` (the judge is the prompt; record this to keep the verdict attributable)
- Rubrics applied: yes
- Failed rubrics: R01, R02, R03, R05, R06, R07, R08, R12

### Rubrics

| # | Focus | Verdict | Evidence |
|---|---|---|---|
| R01 | Spec sufficiency | FAIL | The active instruction lists submodules but never requires package-root symbol re-exports, although the grader imports GrantStore, constants, and helpers from the root. It also does not unambiguously assign the bare-list versus versioned-envelope return shape to RepositoryIndex.list_namespaces or specify InvalidNamespaceError for an invalid SecurityPolicy namespace. |
| R02 | Spec-test alignment | FAIL | test_pep752_semantics.py, test_pep752_uploads.py, test_pep752_metadata.py, and probe.py require unstated package-root exports. test_policy_validates_namespaces additionally pins an unstated exception subtype, and the HTML tests require double-quoted href attributes and a specific escaping representation despite the structural HTML requirement. |
| R03 | Trajectory-informed spec check | FAIL | There is only one rollout, so no multi-model pattern can be established; nevertheless, 60 of its reported failures are import failures caused by the omitted root-export contract. After supplying only an in-memory export adapter, 78 of 81 core tests pass, leaving two list-shape failures and one policy-exception error on the other unclear interface choices. |
| R04 | Reasoning required | PASS | The extensive inventory specifies behavior but leaves substantial implementation work: normalized grant lifecycle, bidirectional overlap, repository metadata, upload exemptions, policy evaluation, persistent CLI commands, and CPython installation integration. Producing a coherent implementation requires reasoning across these components. |
| R05 | Information isolation | FAIL | The solve-time checkout contains no reference package or visible grading suite; the taskfiles review mount is not evidence of a solve-time leak. However, grading imports agent-controlled code with permission to write the expected result artifacts directly: an isolated reproduction overwrote both JUnit and probe JSON at interpreter shutdown and satisfied the reward predicate with a broken implementation. |
| R06 | Test coverage | FAIL | Both behavioral channels omit mixed-case/separator membership queries for GrantStore and GrandfatheredRegistry; replacing their membership methods with raw, unnormalized lookups still passes all 108 non-install reference tests. Fixture damage checks also omit malformed entries inside a list-valued second-index grants field, which the reference verifier accepts. |
| R07 | Reward-hacking | FAIL | The independent probe executes the submitted package inside the process that writes probe.json, under the same permissions, so isolation flags do not protect its verdict. Extending the supplied junit_forge negative control with a shutdown hook to overwrite the probe payload produced 450 forged passing IDs and passed=true even though the probe logged 39/39 genuine check failures; the final reward predicate accepted both artifacts. |
| R08 | Accepts alternatives | FAIL | A reference renderer modified only to use valid single-quoted href attributes fails test_html_semantically_stable; probe.metadata_html rejects it too. Submodule-only public APIs and ValueError policy validation are also reasonable interpretations of the visible contract that the grader rejects. |
| R09 | Test reliability | PASS | The recorded verifier completed normally in approximately 51 seconds, with all 340 required regression tests passing and no scoring-time exception or timeout. Runtime checks are local and deterministic; the rollout's transient interpreter crash occurred during solving and recovered before grading. |
| R10 | Test validity | PASS | A baseline run of all 110 new tests, using their intended repository filenames without modifying the checkout, found no fail-to-pass ID already passing. Missing package functionality, documentation, scripts, and installation registration account for the baseline failures. |
| R11 | Verification efficiency | PASS | Verification uses CPU-only local tests and a staged CPython installation, with an observed total verifier duration of about 51 seconds and suite duration of 5.9 seconds. This is substantially cheaper than implementing and validating the complete package and needs neither human assessment nor specialized hardware. |
| R12 | Golden correctness | FAIL | The active step reference's verify_offline.sh validates second-index grants only as a list and then ignores its contents. After generating its fixtures and replacing that field with [123], the reference verifier still exited zero and printed 'verify: all checks passed', violating the explicit damaged-fixture and every-shape validation requirements. |
| R13 | Golden reliability | PASS | No oracle trial is supplied, so full oracle consistency cannot be established from rollouts. The active step reference passed all 108 non-install tests twice in isolated checks; its inspected build registration matches the integration exercised successfully by the rollout, and there is no observed reference grading failure. |
| N01 | Real-world relevance | FAIL | The behavior is relevant to package security, but a new CPython standard-library package containing index-service models, installer policy, a grant-management CLI, and bespoke fixtures is an artificial project boundary. The instruction's inventory of exact symbols and output fragments also does not resemble a typical CPython feature request. |
| N02 | Knowledge depth | PASS | The task benefits from packaging-name normalization and Simple API knowledge, plus CPython's LIBSUBDIRS, generated standard-library module list, and staged-install conventions. These are specialized ecosystem and repository details beyond ordinary application coding. |
| N03 | Data realism | PASS | There is no external seed dataset; the requested fixtures intentionally model normalized project names, grant ownership, exemptions, and a separate index. Their small size is sufficient for these discrete semantics and does not remove the need for a general implementation. |
| N04 | Training signal | FAIL | The underlying implementation offers useful reasoning challenges, but the observed binary reward is dominated by undisclosed import aliases and interface choices. As currently specified and graded, a strong completed implementation receives the same zero as the untouched baseline, obscuring the desired capability signal. |

### Attempts

| Attempt | Model | Recorded | Judged |
|---|---|---|---|
| `codex/ss007-pep752-implicit-namespaces__595JHED` | gpt-6.1-sol | FAIL | GRADING_FAILURE |

## 2. LH — lcov coverage of the golden

Backend: `py_trace_cov.sh v2 (stdlib trace LCOV; test.sh pre-run for InstallTests)` — line-only backend: branch n/a; entrypoint subprocess-blind but tested; C header unmeasured but asserted

| Step | Lines hit / total | Line % | Branch % | Ceiling | State |
|---|---|---|---|---|---|
| 1_pep752 | 521 / 545 | 95.6 | — | 96.8 | MEASURED |

## 3. LH — horizon length

Source: **local** — measured locally. The working tree does not match any codimango job commit for this task, so the platform's numbers would describe a different tree. These are NOT the numbers codimango will gate on.

_report only — no threshold is applied, none has been agreed_

Measured locally by `lh-count-tokens` — a **per-trial peak (Gate C basis)**, not the platform's mean across trials.

- horizon: tool-call arm unavailable — no passing non-oracle rollout, so there is no e2e run whose tool calls Gate C could read
- horizon: context arm unavailable — no passing agent trajectory in the local jobs — an oracle has no agent turns, and a failed rollout has no peak to measure

## 4. LH — Avocado difficulty

Source: **local** — measured locally. The working tree does not match any codimango job commit for this task, so the platform's numbers would describe a different tree. These are NOT the numbers codimango will gate on.

_report only — no threshold is applied, none has been agreed_

- difficulty: NOT AVAILABLE locally. The platform's number is an Avocado pass rate over a multi-trial cohort; a local run of one or two trials is a different quantity and reporting it would read as a difficulty signal that it is not. Push the task, or accept that this check is unmeasured.

## 5. Codimango validation signals

**NOT AVAILABLE** — read only from the platform record, which this run did not use.
