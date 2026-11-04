# DECISIONS — ss007-pep752-implicit-namespaces

## LIVE (the tree as it stands)

Shape: single-turn task in the multi-turn form — exactly one `[[steps]]`
(`1_pep752`), `format = "swe_bench_multi_turn"`, separate verifier,
`artifacts = ["/app"]`. Graded in the verifier from `steps/1_pep752/tests/`
alone (test.sh, run_script.sh, parser.py, config.json, Dockerfile);
task-level `tests/` mirrors the harness with stub config values.

Contract: 101 `fail_to_pass` (six `Lib/test/test_pep752_*.py` conformance
files) + 340 `pass_to_pass` (stable dotted-id subset of test_ensurepip,
test_venv, test_json, test_htmlparser). Reward 1 iff every required id is
present with status PASSED. All lists generated from real in-container
parser runs, never by hand. The 101-list was regenerated from a real
in-container solved parser run after AUTHOR_1P re-authored the suite
(stale `test_html_byte_stable` out; `test_html_semantically_stable` +
six new tooling/semantics ids in). test_patch already installs the
re-authored suite (the parser emits all 101 from the test.sh-installed
tree), so no repack changed any entry; the config edit was id lists
only. Evidence: `build/.probe/1_pep752/{base,output}.json`.

- New package `Lib/packagenamespaces/` (normalize, matching, grants,
  uploads, metadata, policy, cli, `__main__`), `Tools/packagenamespaces/`
  shell harness, `Doc/library/packagenamespaces.rst` + distribution
  toctree + whatsnew 3.16 + NEWS entry. Golden patch: 15 files, +1367.
  Chose `packagenamespaces` over `namespaces`/`repouns`: collision-free
  (no `Lib/*namespace*` outside PEP 420 fixtures) and self-describing.
- Overlap is BIDIRECTIONAL (a longer proposal under an existing grant
  overlaps), read off "MUST NOT overlap ownership" + the same-owner
  nesting sentence; the one-directional sentence is the documented rival
  reading with a permanent neg control (`subtly_wrong`). Rejected the
  literal one-directional reading: it lets `foo` + `foo-bar` coexist
  under different owners, which is overlapping ownership.
- Same-owner nesting allowed (PEP: a grant "only possible for the owner
  of the former"); different-owner overlap rejected both directions.
- `DEFAULT_DEPTH_LIMIT = 3`; `None` disables. CLI has no depth flag
  (repo policy, not grant management) — rejected a `--depth-limit` flag
  as unneeded surface.
- Upload denial is `UploadConflictError` with `status_code == 409`
  (never an int return); CLI maps it to exit 3 with `409 Conflict` on
  stderr. Rejected exit 1 for conflicts: 409 is the PEP's status and
  deserves its own code.
- `owned` is per-grant (`project owner == grant owner`); grandfathered
  projects report `owned: false`; removal nulls the key. The three-way
  null/owned/unowned distinction has one test each.
- Legacy repos (`supports_namespaces=False`) report 1.4, omit the key,
  and raise `NotSupportedError` from list/detail. Rejected returning
  `[]`/None: a missing endpoint must raise, not answer.
- HTML Simple API: `simple_html(project, files)` compared STRUCTURALLY
  (doctype, html/head/body/title/h1, ordered href+text anchors, no
  `namespace` keys, deterministic re-render). Whitespace, indentation,
  attribute order and `<br>` vs `<br/>` are all free: the pre-push trial's
  valid unindented `<br>` page failed the old byte pin, and the
  instruction only ever required unchanged escaped HTML without
  namespace metadata. Rejected keeping the byte pin (rejects correct
  renderers) and pinning a template in the instruction (over-fits one
  spelling). The page stays a NEW function (CPython has no Simple
  renderer to extend); "untouched" = absence + determinism.
- Docs PEP mention accepts the literal `PEP 752` OR the `:pep:` role
  with 752: the trial's `:pep:` page is standard CPython practice (the
  golden page itself uses the role in body text). Rejected literal-only
  (false negative on idiomatic docs).
- Name validity is fullmatch: `$`-anchored `match()` accepts `"foo\n"`.
  Newline/tab/control cases are pinned in naming + reserve tests.
  Rejected `match()` (the measured bug) and stripping inputs (masks it).
- `transfer` into another owner's overlapping grant raises `OverlapError`
  (both directions probed; failed transfer leaves owners unchanged;
  same-owner/disjoint transfers still succeed). Rejected silent
  re-ownership (creates overlapping owners, the invariant violation).
- CLI `_load_index` wraps per-entry `ValueError`/`TypeError` (non-string
  owners, bad projects, non-string exemptions) into `GrantError`, so
  `main` returns 1 with `error` on stderr instead of raising. `GrantError`
  subclasses still pass through unwrapped. Six value-level corruptions
  pinned in the corrupt-store test. Rejected letting `main` raise
  (breaks the exit-status contract).
- CLI diagnostics pin the FULL phrases `overlaps the grant` and `unknown
  grant` (case-insensitive); corrupt-store and empty-owner failures pin
  the word `error`. The weak-substring checks let a reworded tree score
  1 (demonstrated bypass, now a neg control). Rejected keeping
  substrings (the measured hole).
- Fixture schemas are instruction facts now (`grants` list of
  name+owner mappings with >=2 entries, `projects` mapping,
  `grandfathered` list, second index with empty `grants` list); the gen
  test asserts each shape. Rejected leaving the schema unspecified
  (the trial's self-consistent alternative encoding then fails
  requirements the instruction never stated).
- `verify_offline.sh` is graded NEGATIVELY too: missing fixtures and two
  damaged shapes must exit nonzero WITHOUT the success marker (a stub
  printing only the marker fails both). The existence pre-assert keeps
  both fail_to_pass (a missing script fails, it does not pass by
  nonzero). Rejected marker-only grading (the demonstrated stub).
- Build integration is graded: `Makefile.pre.in` LIBSUBDIRS names the
  package (else `make install` omits it) and
  `Python/stdlib_module_names.h` lists it (else `sys.stdlib_module_names`
  omits it). Static registration test (fast) + InstallTests (DESTDIR
  install contains the package; rebuilt binary reports membership).
  Both facts are in the instruction, so agents know to do them.
  Rejected source-only checks (would not catch a miswired install).
- The RUNNER builds and stages the DESTDIR install pre-suite
  (`/tmp/lambo-destdir` + `.lambo-installed` marker, guarded by package
  presence + input timestamps + marker); the suite NEVER spawns `make`.
  Rebuilding from inside the suite relinks the running `./python`
  (measured SIGSEGV), and even a no-op `make` as a subprocess of this
  alpha interpreter segfaults the parent (measured, deterministic on
  the new image, absent on the old -- root cause unknown, bounded to
  make-children: direct `./python`/seq/sleep grandchildren are all
  safe). Rejected in-suite builds (two measured segfaults) and
  in-suite installs (same crash class).
- R09 root cause: CPython's `sharedmods` rule is PHONY, so every agent
  `make` recreates 75 build/*.so symlinks, and link-bearing trees
  refuse artifact capture (trial agent ran make twice; 75/75 links sat
  under build/lib.*). The image now stages shared extensions as COPIES
  (Makefile.pre.in rule, `cp -f $$mod` -- relative to the image root,
  which `ln` never cared about and `cp` does; survives the config.status
  regen the agent's own Makefile.pre.in edit triggers) and freezes the
  mechanical tree changes as one commit (clean `git status`, so a tidy
  `git checkout -- .` cannot restore the link rule). Verified: 0 links
  at rest AND after `make -j4`, 75 staged extensions, extensions
  import. Rejected narrowed artifacts (drops unlisted agent files;
  kept as fallback), whole-dir excludes (also drop
  configure-generated `_sysconfigdata`, which no make rule restores --
  measured), and `*.so` glob excludes (unknown harbor glob
  semantics). Size is exonerated: two prior oracle runs scored 1.00
  staging the ~571M delinked tree through the separate verifier.
- The image build fails LOUDLY now: no `|| true` on the configure/make
  RUN (it once swallowed a sharedmods failure and shipped an image
  with zero staged extensions -- measured this round) plus a
  post-make `.so`-count assert (>50) in both Dockerfiles.
- Neg control `verify_spoof` replicates the demonstrated bypass
  (marker-only verify script + reworded diagnostics keeping the weak
  substrings): scores 1 on the pre-fix suite (replicated: 95/95 pass),
  0 on the new suite (exactly the 4 targeted tests fail). Rejected
  rewordings that drop the weak substrings (a weaker attack than the
  demonstrated one).
- Policy rule: admit iff `project_owner == policy.owner` AND some
  allowed namespace matches with an active grant for that owner on the
  given index. Rejected grant-holder-only (would admit mallory-owned
  grandfathered projects to a trusting installer) and match-only
  (no ownership check at all).
- CLI `main(argv) -> int`, never raises for app errors (exit codes 0/1,
  argparse 2, conflict 3). No `serve` subcommand (test-time sockets;
  `dump` covers metadata reads). `build_parser`/`DEFAULT_STORE` are
  deliberately unpinned: tests always pass `--store`.
- Shell scripts stage a private copy of the package (`mktemp` +
  `PYTHONPATH`) instead of `PYTHONPATH=$ROOT/Lib`, which shadows the
  interpreter's own stdlib and breaks startup (measured).
- Parser reads ONLY the runner-written JUnit XML report
  (`--junit-xml`); console streams are logs, never grading input.
  Dotted ids come from testcase `name` (= `test.id()`, identical
  scheme to the old console channel -- all 435 required ids resolve
  unchanged, verified by dual-parse diff: junit is a strict superset
  with zero status diffs, recovering 38 docstring-id venv tests the
  console regex could not see). Duplicate ids resolve worst-wins
  (ERROR>FAILED>PASSED>SKIPPED); missing/unparseable report grades
  zero tests (fail closed). Rejected console-text verdicts entirely:
  agent code can print fake `... ok` lines (proven: spoof scored 1
  pre-fix). Rejected stdout-carried XML (same forgery class) and a
  mktemp+marker path (in-process agent code reads env/argv, so
  obscurity buys nothing over the fixed runner-owned path).
- Runner is locked down four ways: neutral cwd (`/`, never /app),
  absolute interpreter path, `-I -S` (no PYTHONPATH/cwd/user-site,
  no site/sitecustomize), `PYTHONSAFEPATH=1` + scrubbed PYTHONPATH.
  The stdlib under test still resolves from the build tree via the
  binary's prefix (`import test` -> `/app/Lib/test`, verified).
  Rejected `-S`-only (leaves cwd shadowing) and keeping cwd=/app
  (leaves `/app/test.py` shadowing `-m test`, proven live).
- Image delinks every symlink under /app into a copy at build time
  (79 -> 0, asserted fail-closed in the RUN). Separate-verifier
  staging refuses link-bearing trees; copies stage. Rejected
  excluding Misc (a docs test reads Misc/NEWS.d -- proven breakage)
  and excluding build/ (the built interpreter under test lives
  there). NOTE: Dockerfile RUN uses dash -- the first delink loop
  used `read -d` and silently no-op'd; the shipped form is POSIX
  find -exec. Rejected silent success: the RUN fails unless zero
  links remain.
- solve.sh applies idempotently (`git apply --check` gate; present
  sentinel = already applied = exit 0; anything else fails loud).
  Rejected bare `patch -N` (exit code still nonzero under set -e)
  and silent skip (a genuinely conflicted tree must fail loud).
- Contract pins every CLI test's exact argv (incl. required `--owner`),
  verified against the golden implementation before re-authoring.
  Test-side fix, not golden-side: facts/instruction already required
  --owner. (The round-2 HTML byte pin is SUPERSEDED by structural
  comparison; see the HTML bullet above.)
- Neg control `console_spoof` ships the proven exploit (fake oks via
  /app/test.py shadowing + /app/Lib/sitecustomize.py startup import)
  over a broken implementation: scores 1 on the old harness, 0 now.
- p2p is the 340 stable PASSED ids (3 identical runs; the only delta
  across runs was junk `bash/csh/fish` ids the fixed parser rejects).
  Docstring-id tests still RUN (a build break zeroes everything) but
  cannot be listed. Skips (9) are excluded, not pinned.
- Coverage counts executable (bytecode-mapped) added lines of
  `Lib/packagenamespaces/*.py` under `trace`: 95.7%. Shell/docs are
  behaviorally covered, not line-measured. `__main__` runs only in a
  subprocess (entrypoint test), so it reads 0 under trace by design.
- Verifier Dockerfile is the full environment image + `COPY . /tests`
  (skeleton-faithful; drift-free by construction). `.dockerignore`
  keeps `sources/` out of the image.
- Image pins: ubuntu digest + all apt versions verified against the
  archive (git pin corrected 7.3→7.4 after a live query); CPython via
  shallow fetch of base_commit; `make -j4` capped to declared cpus=4;
  memory 8192. System `python3` (3.12) installed for the grader so the
  parser never runs under the agent-owned tree.
- task.toml author: Uldis Sturms / uldis@meta.com (repo has no git
  identity configured; unixname + user record). Rejected leaving the
  fields blank (gate fails) or using a tool name (gate fails).
- Provenance tags `private-repo-automation-v0` + `generator:pact`
  stamped by the repo hook's ensure-tag script; kept per its rule.

Can the agent cheat or game this grader? Closed or controlled, each
with a control or a reason: (1) hardcoded answers — the suite asserts
negative/boundary cases per behavior (hyphen boundary both ways,
overlap both directions, owned true AND false, unknown/denied policy
cases); `gaming_hardcode` (match-all + allow-all) scores 0. (2) No-op /
wrong-shape — `null_noop` and `cosmetic_only` score 0. (3) Rival spec
reading — `subtly_wrong` scores 0 on exactly the six rival assertions.
(4) Reward-file tampering from inside the suite — test.sh writes the
reward AFTER the suite from parsed verdicts, overwriting anything the
run left behind; both reward files are zeroed first. (5) Parser
silencing via sitecustomize — parser runs under `/usr/bin/python3 -I
-S`, outside the agent tree. (6) Fake `... ok` lines printed by agent
code — CLOSEd last round: verdicts come only from the runner-written
JUnit report (console is logs-only), and `console_spoof` proves the
old attack (1 pre-fix) now scores 0. The runner additionally ignores
`/app/test.py` shadows and startup imports (neutral cwd, -I -S),
verified live against planted hostile files. Measured subtlety: a
sitecustomize at the repo ROOT never fires (cwd joins sys.path after
site runs) -- the live startup-import placement is `/app/Lib/`, which
is what the control ships. (7) Success-marker + reworded-diagnostics
spoof — CLOSEd this round: full-phrase pins plus verify_offline
negative probes, and `verify_spoof` proves the demonstrated bypass
(1 pre-fix, replicated 95/95) now scores 0 (exactly the 4 targeted
tests fail). (8) Build-input gaming (skipping Makefile.pre.in / the
stdlib-names header while shipping the Lib tree) — closed by the
registration + DESTDIR-install + runtime-membership tests: a tree
that installs without the package fails three required ids. Out of threat model (inherent to
SWE-bench, would read as TOO_EASY in calibration): agent code
monkeypatching unittest mid-run (same power would also rewrite the
JUnit file via atexit -- one accepted residual, not two); replacing
the `./python` binary (the artifact carries it). The separate verifier
closes the cross-turn vectors (no /tests or /tmp/grade in the agent
container).

Declined on merits (do not re-litigate): one-directional overlap;
match-without-hyphen; owned-always-true; CLI serve subcommand;
`--depth-limit` flag; bare-word anchors for `list`/`get`/`main` (weak —
replaced by usage/dotted anchors); counting unparseable FAIL lines;
running baseline files under a custom unittest runner (regrtest
fidelity + REPO.md baseline win); `allow_internet = false`
(maps to NO_NETWORK, kills trials); multi-turn shape (the concept is
one milestone; phases are guidance).

Open unknowns: none blocking. Post-AUTHOR_1P list regeneration is
done (this round); controls re-run (`verify_spoof` must flip 1→0) and
coverage (≥80%) ride the next full gate pass.
R09 already closed end-to-end this round: local oracle 1/1 reward 1.00
in 4:06 with complete /app capture (job 2026-11-04__13-34-25__3b50e5).
Calibration will judge difficulty and horizon.

## ARCHIVE (round history; appended, never rewritten)

- Round 1 (BUILD): scaffolded the task; implemented the golden patch
  (15 files) and a 95-test reference suite; f2p 3/3 + offline 3/3
  green; controls pos→1/neg→0/twice-identical; coverage 95.7%;
  wrote INSTRUCTION_FACTS (166 anchors, validated), GRADING_CONTRACT,
  AUTHORING_JOBS, DECISIONS. instruction.md and test sources intentionally
  absent (approved author writes them).
- Round 2 (REVISION, sanity FIXES NEEDED): closed all four findings.
  13h: parser now JUnit-XML-only + runner locked down (neutral cwd,
  absolute interpreter, -I -S, safepath); spoof control 1 pre/0 post.
  21-artifacts: Dockerfile delinks 79->0 symlinks (fail-closed RUN;
  first attempt silently no-op'd under dash -- POSIX rewrite).
  21-golden-mismatch: contract pins exact HTML bytes + CLI argv
  (verified vs golden; 2 targets await revise-in-place). 22: solve.sh
  idempotent (replay 0, was 1). Preserved green: 340/340 p2p under
  the new parser, zero id-scheme drift (dual-parse diff clean).
- Round 3 (REVISION, pre-push REVISE): closed all seven findings.
  R12: golden +2 files (Makefile.pre.in LIBSUBDIRS,
  stdlib_module_names.h) +3 fixes (fullmatch validity, transfer
  overlap check, store value-error wrapping); patch regenerated (17
  files). R01: facts +25 lines (container protocols, parent/children
  types, fixture schemas, string versions, error-word diagnostics,
  :pep: forms, build registration); anchors 166->189; instruction
  revise-flagged. R02/R08: HTML byte pin -> structural compare (trial's
  valid page passes now); docs accept :pep: role; fixtures + error-word
  now fact-backed; transfer-conflict + verify negatives + install
  tests added (95->101 f2p; 4 targets await revise-in-place).
  R06/R07: full-phrase diagnostics, value-corrupt stores, verify
  negatives; verify_spoof control 1 pre/0 post (replicated 95/95).
  R09: image stages extensions as copies (regen-surviving rule) +
  freeze commit; 0 links before+after make; size exonerated by two
  prior 1.00 oracles. Runner builds + stages DESTDIR pre-suite (two
  measured in-suite segfaults); image build fails loud (no || true +
  .so assert). Validated: 441/441 via real test.sh online AND
  --network=none; base 101/101 fail; p2p 340/340 green. Preserved
  green: every previously-green behavior still green on current tests;
  `verify_spoof` flips to 0 after AUTHOR_1P.
- Round 4 (REVISION, stale f2p id): closed the single finding. Config
  still listed `test_html_byte_stable` (renamed to
  `test_html_semantically_stable`) and missed six new ids, so the
  oracle sat at 434/435 reward 0. Regenerated fail_to_pass (95->101)
  from a REAL in-container solved parser run; p2p untouched (340/340
  green both states). Verified with the task's own test.sh in
  containers of the task image: solved 441/441 reward 1, base 340/441
  reward 0 (0/101 f2p passing at base). Measured quirk (pre-existing,
  fail-closed, out of scope): `test_whatsnew_announces_module` fails
  purely inside subTests with no `require_impl` guard, so regrtest's
  `RegressionTestResult` (no `addSubTest` override) leaves a bare
  nameless `<testcase />` the parser skips — missing at base, PASSED
  at solved. Missing grades as not-PASSED, so the reward is correct
  in both states; fixing it would mean editing AUTHOR_1P-owned test
  sources. Evidence in `build/.probe/1_pep752/`.
