# DECISIONS — ss007-pep752-implicit-namespaces

## LIVE (the tree as it stands)

Shape: single-turn task in the multi-turn form — exactly one `[[steps]]`
(`1_pep752`), `format = "swe_bench_multi_turn"`, separate verifier,
closed-set artifacts (`/app/Lib`, `/app/Tools` parents plus the news dir
and five files -- the two package dirs share a basename so Harbor cannot
stage them directly; round 12). Graded in the verifier from
`steps/1_pep752/tests/` alone (test.sh, run_script.sh, parser.py,
probe.py, config.json, tree_manifest.json, Dockerfile); task-level
`tests/` mirrors the harness with stub config values.

Contract: 111 `fail_to_pass` (six `Lib/test/test_pep752_*.py` conformance
files) + 340 `pass_to_pass` (stable dotted-id subset of test_ensurepip,
test_venv, test_json, test_htmlparser). Reward 1 iff every required id is
present with status PASSED AND the independent probe passes (two data
channels; either alone is insufficient). The 111th f2p id
(`CliTests.test_cli_package_root_reexports_build_parser`, the round-13
R06 re-export check) landed via AUTHOR_1P round 14 and joined the graded
list in round 15; the golden tree grades 1 on all 111 with 45/45 probe
checks green -- measured in-container, online AND `--network=none`
(round 16 re-measured both on the hardened harness: 451/451 with the
suite, make/install and probe grandchildren all unprivileged). The
111-list is the verified 101-list plus the
nine round-7 ids plus the round-14 id, all from the contract's pinned
class/method names. test_patch installs the re-authored suite (the
parser emits all 111 from the test.sh-installed tree). No id changes
in round 16: both test revises (tooling whole-dir copy, uploads
import-from-root) keep every class/method name.

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
- `UploadConflictError.owner` is the attempted UPLOADER (the `owner`
  argument to `authorize_upload`), never the grant holder; the golden
  docstring already said so and the suite already asserted it, but the
  instruction never did -- pinned as facts now, so the grant-holder
  reading the k1 rollout chose is settled. Rejected grant-holder
  ownership (reports the victim instead of the actor, and contradicts
  the existing passing test).
- `authorize_upload` validates its owner FIRST (`ValueError` on
  empty/non-string, before any grant is consulted -- same rule and
  message as `register_project`/`SecurityPolicy`), so CLI
  `check-upload` with `--owner ""` exits 1 with `error` even for
  unreserved projects (the golden printed OK/0 there). Rejected
  validating only in the CLI (the library then accepts owners the CLI
  rejects, and the contract pins both levels).
- `register_project` records ownership and validates the owner; it
  does NOT authorize uploads (a stranger-owned project under a
  reserved prefix still registers -- asserted now). `grandfather`
  records the project's owner AND exempts it (both keys persist).
  Rejected register-time authorization (conflates recording with
  gating; the golden never did it) and ownerless exemptions (the
  `owned` flags and foreign-grandfathered policy denial need the
  recorded owner).
- `owned` is per-grant (`project owner == grant owner`); grandfathered
  projects report `owned: false`; removal nulls the key. The three-way
  null/owned/unowned distinction has one test each.
- Legacy repos (`supports_namespaces=False`) report 1.4, omit the key,
  and raise `NotSupportedError` from list/detail. Rejected returning
  `[]`/None: a missing endpoint must raise, not answer.
- HTML Simple API: `simple_html(project, files)` compared STRUCTURALLY
  (doctype, html/head/body, title+h1 that each NAME the project,
  ordered href+text anchors, no `namespace` keys, deterministic
  re-render). Whitespace, indentation, attribute order, `<br>` vs
  `<br/>`, list-vs-flat layout, and the title/heading WORDING are all
  free: the beta reviewer's valid renderer (ordered links, project
  title, no metadata) failed the old `Links for demo` pin, and no
  pre-existing renderer fixes that wording. The instruction now states
  the structure (full document, project-naming title/heading, ordered
  anchors) without fixing the words. Rejected keeping the wording pin
  (rejects correct renderers) and pinning a template in the
  instruction (over-fits one spelling). The page stays a NEW function
  (CPython has no Simple renderer to extend); "untouched" = absence +
  determinism. Pinned by the permanent `alternate_html` pos control
  (0 on the wording-pinned suite, 1 after the revise).
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
- Sparse chains pin the direct-only rule: with only `foo` and
  `foo-bar-baz` granted, `parent` is None and `children("foo")` is []
  (a missing middle grant breaks both links; nearest-granted-ancestor
  would answer `foo`/`[foo-bar-baz]` instead). The golden implements
  immediate direct links; the suite now asserts the gap case.
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
- The persisted store schema is pinned in BOTH directions: after
  reserve/register/grandfather the file holds exactly the documented
  `grants`/`projects`/`grandfathered` document (no envelope, no extra
  keys), and a hand-written documented document loads back (list,
  denied and grandfathered-allowed check-uploads). The beta reviewer's
  `private_payload` substitution passed the old suite; it fails the new
  schema tests AND the probe, and ships permanently as the
  `store_spoof` neg control (1 pre-fix, 0 post -- measured both).
  Rejected pinning only the load side (a private writer still passes)
  or only the write side (a private reader still passes).
- Bare `dump` prints the VERSIONED ENVELOPE
  (`{"api_version": "1.5", "namespaces": [{"name": ...}]}` with
  name-only entries from `list_namespaces`); `list --json` prints the
  name-and-owner entries; `dump --project` prints one project-detail
  mapping. The instruction showed both shapes without assigning them,
  and the k1 rollout guessed raw-store dump output -- each shape is a
  fact on its operation now. The existing dump test is unchanged
  (it already required the envelope); the spec caught up to it.
- Fixture schemas are instruction facts now (`grants` list of
  name+owner mappings with >=2 entries, `projects` mapping,
  `grandfathered` list, second index with empty `grants` list); the gen
  test asserts each shape. Rejected leaving the schema unspecified
  (the trial's self-consistent alternative encoding then fails
  requirements the instruction never stated).
- `verify_offline.sh` is graded NEGATIVELY too: missing fixtures and
  FIVE damaged shapes (invalid `grants.json`, empty `projects.json`,
  string-`grants` `second-index.json`, plus a `[123]` grants list and
  a grant entry with no owner) must exit nonzero WITHOUT the success
  marker (a stub printing only the marker fails all). The golden
  verifier validates every fixture's shape AND every entry up front
  (it once checked second-index `grants` only as a list, so `[123]`
  sailed through with exit 0). The existence pre-assert keeps both
  fail_to_pass (a missing script fails, it does not pass by
  nonzero). Rejected marker-only grading (the demonstrated stub)
  and list-typed-but-uninspected acceptance (the demonstrated gap).
- Docs pin the `distribution.rst` backlink (the suite checked the new
  page but never its toctree entry), and the shell scripts pin
  network-freedom by scanning for network command/library words
  (`curl`, `wget`, `ssh`, ..., `urllib`, `httpx`). Bare `requests`
  and `socket` words are deliberately NOT matched: the reference
  fixtures register a project literally named `requests`, which false
  positived the first draft of the probe (measured). Fixture URL
  strings stay allowed. Rejected substring matching without word
  boundaries (same false-positive class) and running the scripts
  under a blocked network (no enforcement primitive inside the
  suite; the static scan plus offline trial runs is the evidence).
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
- Runner is locked down five ways: neutral cwd (`/`, never /app),
  absolute interpreter path, `-I -S` (no PYTHONPATH/cwd/user-site,
  no site/sitecustomize), `PYTHONSAFEPATH=1` + scrubbed PYTHONPATH,
  and UNPRIVILEGED execution (setpriv nobody; round 16). The stdlib
  under test still resolves from the build tree via the binary's own
  prefix (`import test` -> `/app/Lib/test`, verified, nobody-owned
  tree included). Rejected `-S`-only (leaves cwd shadowing) and
  keeping cwd=/app (leaves `/app/test.py` shadowing `-m test`,
  proven live).
- Privilege separation is the outer boundary (round 16): test.sh runs
  as root, but EVERYTHING that touches submitted code -- the
  make/install in run_script.sh (the Makefile is agent-edited), the
  suite, and the probe's check grandchildren -- runs as nobody, while
  /tests is root-owned read-only and the verdict paths are
  root-owned. Neither scoring channel's reader is writable by the
  code it grades. Setup order matters: integrity gate (root, scrub)
  -> test_patch install (root, git) -> snapshot /tests hashes ->
  chmod a-w /tests -> chown repo to nobody -> unprivileged
  make/suite/probe. After the suite, test.sh re-verifies the /tests
  snapshot before parsing (second layer; a drift fails closed), and
  every grade starts by removing output.json/probe.json so a tripped
  gate can never reward from stale verdicts. Rejected keeping the
  suite root-owned with hash-pinning alone (bash reads test.sh
  incrementally, so a root in-process rewrite of test.sh's own tail
  could survive any self-check; uid separation closes it), and
  rejected hiding config.json (the installed test sources already
  name every id, so secrecy buys nothing -- unwritable readers plus
  the independent probe is the protection).
- The offline mirror copies the WHOLE `Tools/packagenamespaces/`
  directory (round 16): the spec never requires the two shell
  entrypoints to be self-contained, so sibling helpers they source
  or import travel with them and a legitimate split layout keeps
  working. Two-file copying rejected a correct decomposition
  (measured 0 pre-fix on the model's entrypoints-plus-helper tree,
  reproduced by the pre-push review). Both channels fixed: the probe
  copies the directory now, and the suite's
  `test_scripts_use_no_network` does the same via AUTHOR_1P revise
  (contract section rewritten, same id). Permanent pos control
  (`split_harness`).
- The package-root re-export of `GrandfatheredRegistry` is pinned
  (round 16): the probe's `grants.exports` check asserts identity
  with the uploads submodule's object, and the uploads tests import
  the name from the root via AUTHOR_1P revise (same ids -- a dropped
  root import fails the guarded import and every UploadTests method
  with it). Deleting the root import plus `__all__` entry scored 1
  pre-fix (reproduced by the pre-push review); the permanent
  `exports_drop_grandfathered` neg control scores 0 now. `__all__`
  spelling still unpinned (list or tuple).
- The integrity gate pins SOURCES, not build products (round 16):
  the 97 `Python/*.o` entries left the manifest (3219 -> 3122
  files) and the gate skips `*.o` (neither verified nor scrubbed --
  scrubbing would force a full rebuild every grade). Pinning them
  broke repeat grading (the first grade's post-header rebuild
  invalidated the second grade's gate; round 15 measured the trip).
  The `.o` files cannot smuggle anything in: they travel in neither
  artifact set. The `twice` control now prints 1.0,1.0 with a clean
  second-run gate. Rejected keeping the hashes (the measured
  repeat-run failure) and scrubbing build products (rebuild cost,
  same admission).
- The golden NEWS entry is blurb-valid (round 16):
  `2026-11-04-12-00-00.gh-issue-140000.ss007.rst`. The old
  `pep-752` middle field is unparsable to blurb (`Found unparsable
  field in 'next' filename: 'pep-752'`, reproduced with blurb's own
  `load_next`; normal doc builds invoke `blurb merge`). The issue
  number is a placeholder satisfying blurb's required issue field;
  the entry content is unchanged, so the keyword NEWS checks are
  unaffected. Same rename in both solve.sh files and the config
  `patch` (config diff: one line).
- Reward needs TWO data channels: the JUnit verdicts AND the
  independent probe (`tests/probe.py`, 39 checks over every graded
  surface, negatives included, specified behavior only). The probe
  SPLITS IN TWO: a child runs the checks in a FRESH locked-down
  interpreter post-suite (absolute repo-interpreter path, `-I -S`,
  cwd `/`, scrubbed env, script from verifier-owned `/tests`) and
  prints one marked result line, while the parent -- which never
  imports agent-controlled code -- demands exactly one well-formed
  line on a zero exit and only then writes the verdict file, after
  the child (and any shutdown hook it armed) is dead. The probe
  never reads the report -- so the in-process JUnit rewrite (an
  atexit hook suffices; replicated as the `junit_forge` neg
  control: 441/441 forged PASSED) scores 1 on a report-only grader
  and 0 once the probe joins (35 probe checks fail; measured both).
  The two-channel rewrite (same hook plus a probe-payload
  overwrite; replicated as `probe_forge`) scores 1 on the old
  single-process probe and 0 now (measured both). Missing,
  doubled, or malformed result lines, crashes, and timeouts all
  fail closed. Rejected report-path obscurity (in-process code reads
  env/argv -- buys nothing), running the probe under system python
  (agent code may use newer syntax than 3.12 parses), trusting the
  report alone (the measured hole), and single-process verdict
  writes (the measured hook route). Residuals out of model: a
  replaced `./python` binary faking BOTH channels (inherent to
  artifact-carries-binary), and a protocol-aware in-process stdout
  forgery that reads the probe source at grading time -- defeating
  the first needs binary attestation, the second needs a channel a
  process can hide from its own code, and neither exists here.
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
  archive (git pin corrected 7.3→7.4 after a live query; Round 5:
  libsqlite3-dev re-pinned .8→.9 after the archive moved, other 16
  pins re-verified current the same day via live apt-cache query;
  Round 6: one documenting comment above the libsqlite3-dev pin in
  the harness Dockerfile, pin/value-identical, so the record
  re-stamps the file after round 5's record gap);
  CPython via
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
that installs without the package fails three required ids.
(9) In-process JUnit rewrite (atexit hook, unittest monkeypatch,
patched regrtest) — CLOSEd last round: the reward needs the
independent probe too, which runs in a fresh locked-down interpreter
and never reads the report; `junit_forge` proves the replicated
attack (441/441 forged PASSED, 1 pre-fix) now scores 0 (35 probe
checks fail). (10) Private-envelope persistence — CLOSEd last round:
the store schema is pinned in both directions by new tests and the
probe; `store_spoof` proves the demonstrated bypass (1 pre-fix) now
scores 0 (probe `cli.schema` fails). (11) Two-channel rewrite
(shutdown hook overwriting the probe payload as well as the JUnit
report) — CLOSEd this round: the probe's parent writes the verdict
file after the armed child has exited, so the hook's overwrite is
moot; `probe_forge` proves the replicated attack (450 forged ids +
passed payload, 1 pre-fix) now scores 0 (genuine probe failures
stand). (12) Grading-reader rewrite (package init overwriting
`/tests/parser.py` + `/tests/probe.py` with all-pass forgeries) —
CLOSEd round 16: submitted code runs unprivileged with /tests
read-only, so the rewrite fails and the genuine failures stand;
`tests_tamper` proves the replicated attack (reward 1 pre-fix, with
the forged readers observed in place) now scores 0 (34 genuine
probe failures); a /tests snapshot re-verified after the suite is
the second layer. Out of threat model (inherent to SWE-bench,
would read as TOO_EASY in calibration): replacing the `./python`
binary (the artifact carries it) to fake BOTH channels, and a
protocol-aware in-process stdout forgery with early exit (no
software-only channel a process runs can hide from its own code).
The separate verifier closes the cross-turn vectors (no /tests or
/tmp/grade in the agent container).

Declined on merits (do not re-litigate): one-directional overlap;
match-without-hyphen; owned-always-true; CLI serve subcommand;
`--depth-limit` flag; bare-word anchors for `list`/`get`/`main` (weak —
replaced by usage/dotted anchors); counting unparseable FAIL lines;
running baseline files under a custom unittest runner (regrtest
fidelity + REPO.md baseline win); `allow_internet = false`
(maps to NO_NETWORK, kills trials); multi-turn shape (the concept is
one milestone; phases are guidance).

Open unknowns: none blocking. AUTHOR_1P revise is ARMED (instruction
+ 4 test files flagged; 9 new ids pre-listed in config, so the golden
tree grades 0 on exactly those until the revise lands); the oracle,
controls re-run (pos controls must flip 0→1, `alternate_html` with
them) and coverage (≥80%) ride the next full gate pass.
R09 already closed end-to-end in round 3: local oracle 1/1 reward 1.00
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
- Round 5 (REVISION, narrow: two findings from failed PRE_PUSH
  7b022947): closed both, graded surface byte-identical (no test,
  config, instruction, solution, or harness file touched).
  F1 stale apt pins: fresh builds died at apt exit 100
  (libsqlite3-dev .8 vs libsqlite3-0 .9). Live-queried today's
  archive for all 17 pins from the pinned ubuntu digest: only
  sqlite moved, so the fix is a one-line bump .8→.9, mirrored
  byte-identical into steps/1_pep752/tests/Dockerfile (apt blocks
  diff-clean). Rejected unpinning (reproducibility is the point of
  the pins) and bumping blindly without the full 17-pin re-check
  (same rot class could hide anywhere). Proved with a TRUE fresh
  build (`taskbuild.sh ... --no-cache`: all RUN layers executed,
  apt fetched libsqlite3-dev 2.9, delink 0 links, freeze commit)
  plus solve (exit 0) + graded test.sh in the resulting container:
  441/441 reward 1.0. Scratch logs under worktree .scratch/,
  removed after the run.
  F2 runner scratch in review snapshot: snapshot 4c33f8a tracked
  runner scratch because the worktree .gitignore lacked the flow's
  rules. Diagnosed the FULL tracked set, not just the three named:
  the finding named base.json/output.json/.coverage-build.log but
  `git ls-files` also showed .controls-build.log + seven
  build/.evalgt/* files, same never-commit class (the flow's own
  ensure_gitignore.sh lists `.evalgt/`). `git rm --cached` all 11
  (files left on disk; no CPython tracked file or rule touched).
  Appended 9 rules to the WORKTREE ROOT .gitignore (where this
  task's git repo lives): the flow's six bare forms (.probe/
  .offline/ .controls/ .coverage/ .preauthor/ __pycache__/) +
  .evalgt/ + two build-log rules (.*controls*.log,
  .*coverage*.log) in the flow's existing `.*<name>*.log` family.
  The two log rules are a diagnosed extension of the finding
  sketch: the six alone leave build/.coverage-build.log (and its
  .controls twin) unignored, so the finding's own `git add -A`
  verification would still sweep them; in the control repo they
  are covered only by `/*/build/`, which must NOT be copied here
  (this worktree commits build/ docs legitimately). Verified:
  `git check-ignore` hits all six scratch classes;
  `git add -A --dry-run -- <task>` sweeps no scratch. Preserved
  green: 441/441 solved reward 1 on the fresh image; controls and
  coverage scripts untouched and interface-identical.
  run_coverage.sh re-run end-to-end: COVERAGE 1_pep752 95.6 (exit
  0, threshold 80%); its image is layer-identical to the no-cache
  proof image (same per-task builder cache entry from the new
  Dockerfile text) and dpkg-confirms libsqlite3 .9 inside.
- Round 6 (REVISION, surgical re-stamp): closed the provenance gap
  on steps/1_pep752/tests/Dockerfile. Round 5 re-entered via start
  --phase BUILD, which snapshots no harness base, so its legit .8→.9
  pin bump was never stamped and gate_provenance flagged the file
  as "modified after authoring". Fix is one documenting comment
  directly above the libsqlite3-dev pin (pin requirement + .8/.9
  rot history + identical-pins note); no pin value, package list,
  or build behavior changed. Verified: diff vs round 5 shows ONLY
  the added line; TRUE fresh build (taskbuild.sh --no-cache,
  tag ss007-r6-proof:v1) green end to end (apt fetched 2.9, 75
  shared extensions, freeze commit, dpkg-confirms 2.9, tree clean).
  environment/Dockerfile and all test/config/instruction files
  untouched. New sha256 of the harness Dockerfile:
  87db6dd5e9d865e1d0298f7e938b1277be9d02a0c6578aa46b86fe33b84b1c3d.
  Scratch (round-5 snapshot, probe + proof logs) under
  /home/uldis/cpython/.scratch/ss007-r6/.
- Round 7 (REVISION, pre-push beta REVISE with 6 findings): closed all
  six. R01/R02: facts +20 lines pinning the four ambiguities --
  conflict-owner is the attempted uploader (suite already asserted
  it; the k1 rollout's grant-holder guess is settled), bare dump is
  the versioned envelope / list --json the name-owner entries / dump
  --project one detail, register records without authorizing,
  grandfather records + exempts -- and the instruction revise is
  flagged. Existing stranger-owner and dump tests UNCHANGED (the spec
  caught up to them). R02/R08: HTML title/h1 wording freed -- the
  test now requires each to NAME the project instead of the exact
  `Links for demo` (the reviewer's valid renderer passes the new
  wording; replicated in-container); instruction states the structure
  without fixing the words; permanent `alternate_html` pos control
  (0 on the pinned suite, 1 after the revise). R06: nine new tests
  across four files (persisted-schema both directions, sparse
  parent/children gaps, distribution backlink, network-free scripts,
  empty-owner uploads both levels, register-without-authorization)
  plus the second-index damaged case and the HTML revise; f2p
  101->110 with the pinned ids pre-listed. R07: reward needs the new
  independent probe (39 checks, fresh locked-down interpreter, never
  reads the report) AND every required id; `junit_forge` (441/441
  forged PASSED) and `store_spoof` (private envelope) both measured
  1 on the pre-fix harness, 0 with the probe. R12: golden
  `authorize_upload` validates owners first (empty check-upload now
  exits 1, was 0/OK) and `verify_offline.sh` validates every fixture
  shape up front (string-grants second index now exits 1, was
  0/marker); patch regenerated (2 files) and spliced byte-identical
  into solve.sh + config. Validated in containers of the task image:
  golden 101/101 old f2p + 340/340 p2p + 39/39 probe green online
  AND --network=none (reward 0 on exactly the 9 AUTHOR_1P-pending
  ids); pos alternate_core 1 with the probe; full run_controls
  green-modulo-pending (all negs 0, twice identical, pos 0 only on
  the 9 missing ids). Preserved green: every previously-green
  behavior still green; `local:sanity` untouched (parser/runner
  bytes identical, harness mirrors in sync). Scratch under
  /home/uldis/cpython/.scratch/ss007-r7/, removed after the run.

## R8 surgical: strip revise keys from kind=tests jobs
AUTHOR_1P parked authoring_blocked: "revise": true is valid only on
kind="instruction" jobs. Removed "revise" and "revise_reason" from
all four kind="tests" jobs that carried them (semantics, uploads,
metadata, tooling); naming and policy already clean. Kept "revise":
true on the kind="instruction" job. No contract edits, no redraw
flags added (no target needs blank-slate treatment). Verified valid
JSON, 7 jobs intact, zero kind="tests" jobs carry revise/redraw keys.

## R9 surgical: redraw (not revise) for the kind=instruction job
AUTHOR_1P's revise pass on steps/1_pep752/instruction.md returned "needs
no change", but the kept page (91 lines, byte-identical) omits the
round-7 facts (INSTRUCTION_FACTS.md 254 -> 300 lines): no
conflict-owner-as-uploader disambiguation (facts l99; "uploader" /
"attempted" absent from the page), no register-records-without-
authorizing (facts l142; absent), no bare-dump envelope vs list
--json entries distinction (facts l225; the page's one "envelopes"
mention covers list_namespaces routes, not the dump shape), and the
re-authored tests assert these behaviors, so the page trails the
grader. Adjudicated redraw over a second revise: the author never
sees revise_reason and the identical revise prompt just no-changed,
so another revise risks a second no-change round, while one
blank-slate pass from the current 300-line facts guarantees the new
disambiguations get woven and the 91-line page is cheap to rewrite.
Set ONLY "redraw": true + redraw_reason on the kind="instruction"
job (revise keys removed from it); all six kind="tests" jobs
untouched, still carrying neither revise nor redraw keys. Verified
valid JSON, 7 jobs intact.

## R10 surgical: anchor all 20 round-7 facts additions, re-arm redraw

The R9 redraw landed a 23-line page that still omits the R01
disambiguations (driver-verified by grep: no uploader/conflict-owner
language, no register/grandfather record-vs-authorize semantics, no
dump-envelope vs list-entries distinction). Root cause confirmed: the
round-7 facts additions (+20 lines, uncommitted vs HEAD) were never
added to INSTRUCTION_PUBLIC_ANCHORS.json, so the anchor gate passes
while the author drops them. Fix anchors all 20, in facts order
(189 -> 209), each verified a verbatim substring of the facts file:

Required 6 (R01 disambiguations): conflict-owner-as-uploader x2 ->
test_stranger_upload_conflicts (uploads; asserts owner == "mallory");
register-without-authorizing -> test_register_project_records_without_
authorization (metadata); grandfather-records-plus-exempts ->
test_cli_persists_documented_store_schema (both keys persist) +
test_cli_loads_documented_store_schema (exemption effective); bare
dump envelope + name-only entries x2 -> test_cli_dump.

OTHER 14 (same defect class, each test-pinned): stranger-owned
still registers -> test_register_project_records_without_
authorization; list --json entries -> test_cli_reserve_and_list;
dump --project detail -> test_cli_dump_project; sparse-chain gap ->
test_children_sparse_chain_skips_gap + test_parent_sparse_chain_is_
none; HTML doctype/title+heading/ordered-anchors x3 ->
test_html_semantically_stable; persist-exactly-schema ->
test_cli_persists_documented_store_schema; hand-written loads back
-> test_cli_loads_documented_store_schema; empty/non-string owner
ValueError + validate-before-grants x2 ->
test_authorize_upload_rejects_empty_owner (unreserved "requests"
case proves ordering); CLI empty-owner-unreserved -> test_cli_check_
upload_rejects_empty_owner; verify-validates-shapes + malformed
second index x2 -> test_verify_offline_rejects_damaged_fixtures
(second-index.json string-grants subTest).

Scan disposition for the remaining pre-round-7 unanchored lines:
excluded deliberately, not overlooked. They were covered without
anchors in the reviewed 91-line page (the beta R01 finding named
only the four ambiguities), and each is either substance-covered by
a sibling anchor (L38 by the hyphen-suffix anchor; L98 by the dotted
conflict attrs; L101 by True/False; L144/L160/L163 by the JSON shape
literals; L166-L168/L285 by instruction prose; L290 by the :pep:
anchor) or a bare symbol the rounds declined as weak (main/list/
dump/status_code). Re-armed the kind="instruction" redraw with a
CHANGED redraw_reason (prior request consumed); no revise keys
anywhere, all six tests jobs untouched. Verified valid JSON both
files, +20 anchors, zero duplicates.
- Round 8 (REVISION, pre-push beta REVISE with 7 findings): closed all
  seven. R01/R02/R08 (spec): facts +4 lines (package-root re-exports
  of every public symbol with the three graded root-only classes
  named, bare-list list_namespaces, dump-only versioned envelope) +
  5 anchors (the 4 new lines plus the unanchored
  invalid-policy-namespaces fact the author kept dropping);
  instruction redraw re-armed with a changed reason. The graded root
  imports, exception subtype, and bare-list shape are spec now, so
  submodule-only APIs, ValueError policy validation, and envelope
  guesses are unreasonable readings. R02/R08 (HTML): contract frees
  the href quote (single or double, same-quote open/close) and
  replaces the exact-entity pins with unescape round-trips plus raw
  absence; probe mirrors both. R06: contract + probe add
  normalization-sensitive membership probes (mixed-case and
  separator spellings for `in`/`covers` on both containers) and two
  malformed second-index entry corruptions; no new test ids anywhere
  this round (110 f2p + 340 p2p unchanged). R05/R07: probe splits
  into a check child plus a verdict-writing parent that never
  imports agent code (exactly-one marked line, zero exit, schema
  check, every anomaly fail-closed); new `probe_forge` neg control
  replicates the reviewer's two-channel shutdown-hook attack.
  R12: golden verify_offline.sh validates every second-index entry
  (dict with string name+owner) and every projects value; spliced
  into steps solve.sh + config patch + task-level solve.sh (which
  also picks up the round-7 fixes it missed), patch re-verified
  applicable at base. Validated in containers of the task image:
  oracle 450/450 reward 1 online AND --network=none with 39/39
  probe; probe_forge 1 pre-fix (HEAD harness) / 0 post-fix with the
  forged 450-id report confirmed moot; full run_controls green
  (pos 1.0 x2, all 8 negs 0.0, twice 1.0,1.0). Preserved green:
  every previously-green behavior still green; harness mirrors in
  sync. Test-source and instruction re-authoring ride the next
  AUTHOR_1P (4 contract slices changed, 0 id changes, instruction
  redraw armed). Scratch under /home/uldis/cpython/.scratch/ss007-r8/
  plus /tmp probe files, removed after the run.
- Round 9 (REVISION, pre-push beta REVISE, BAD_LEAKAGE, 7 routed
  findings; R03 and difficulty not routed). R01/R02/R12-spec: the
  graded suite, probe and golden already required raise-on-deny and a
  tuple policy container -- the instruction's bare `False` wording
  and missing container type were the outliers, so facts drop the
  bare True/False lines for explicit raise/tuple lines plus two
  build_parser lines, anchors synced, and the instruction job moves
  from redraw to revise:true with a one-line reason (kept page
  re-checked against facts). R12-golden: the package root now
  re-exports build_parser (cli.__all__ already declared it public),
  spliced into both solve.sh copies plus the config patch with
  byte-identical text, hunk count fixed, `git apply --check`
  verified. R05/R07: closed-set artifacts (Lib + Tools package dirs,
  news dir, 5 files) so the agent's built interpreter never reaches
  the separate verifier, whose image already holds a pristine base
  build; run_script.sh assures the interpreter unconditionally
  before anything executes it (non-ELF removed and relinked via
  `make python`); the probe parent runs under /usr/bin/python3 and
  refuses to spawn a non-ELF child. Measured: a full make relinks
  `python` unconditionally, which is why the pre-fix exploit won
  only without a package dir (the make block was guarded on it).
  R06: new probe `grants.exports` check (Grant/GrantError from the
  root plus root __all__ self-consistency); probe-only, no new suite
  ids (110 f2p + 340 p2p unchanged; probe 39 -> 40 checks). R08:
  the offline check is behavioral in probe and contract (PATH stubs
  logging invocations + comment-carrying copies in a mirrored
  Tools/ layout), same test id, no text matching. New
  `exec_forge` neg control (forged /app/python, no package)
  replicates the reviewer's exploit: 1 on the pre-fix harness, 0
  post-fix with the binary observed relinked to ELF. Validated in
  containers of the task image: oracle 1 online AND --network=none
  at 40/40 probe; base 0; sensitivity demos (Grant/GrantError
  removal fails grants.exports; `curl ... || true` in a script
  fails harness.offline); full run_controls green (pos 1.0 x2, all
  9 negs 0.0, twice 1.0,1.0). Preserved green: every
  previously-green behavior still green; harness mirrors in sync.
  Instruction + tooling test re-authoring ride the next AUTHOR_1P.
  Scratch under /home/uldis/cpython/.scratch/ss007-rev/, removed
  after the run.
- Round 12 (SURGICAL, harbor preflight ArtifactCaptureError): the
  round-9 closed-set declaration died before any grading --
  `/app/Lib/packagenamespaces` and `/app/Tools/packagenamespaces`
  share a basename and Harbor stages each entry under the shared
  artifacts dir keyed by basename (proven by oracle
  sanity-ss007-r10 in _collect_step_artifacts). Fix declares the
  two package dirs via their non-colliding parents `/app/Lib` and
  `/app/Tools`; the other six entries keep distinct basenames
  (8/8 unique, TOML-parsed). R05/R07 intent preserved: the set
  stays closed to source paths -- no build/, no python binary, no
  libpython links reach the separate verifier (staged set
  observed: Lib 62M + Tools 4.3M + Library + 5 files). Link-free:
  0 symlinks under Lib/Tools/Doc/NEWS.d/next at base commit
  416e8d89 (find), the image delinks the whole tree anyway, and
  make-created links land only under build/ (now copies via the
  sharedmods patch), /app root, or DESTDIR -- none under the
  widened entries; the staged capture itself holds 0 symlinks.
  Proven end to end with a real oracle run: `codimango bench run
  -p ss007-pep752-implicit-namespaces -a oracle -k 1` (job
  2026-11-05__00-39-17__e02225), staged, graded, reward 1.0,
  failure_mode NONE, zero ArtifactCaptureError/overlap mentions.
  No test, config, instruction, solution, or harness file touched.
- Round 13 (REVISION, pre-push beta REVISE, BAD_LEAKAGE, 5 routed
  findings; R03 and difficulty not routed). R02/R08 (spec-test
  alignment + alternatives): probe `grants_root_exports` no longer
  pins the `__all__` spelling -- absent pins nothing, present accepts
  list or tuple with every entry resolving from the root, and
  Grant/GrantError must be identical to the grants submodule's
  objects; probe `metadata_html` compares anchors by PARSING
  (HTMLParser collector, tag/attribute names case-insensitive,
  quote style, `=` spacing and extra attributes free) instead of
  lowercase-only regexes. R06 (build_parser unchecked): new probe
  check `cli.root_exports` (resolves from the root, identical to
  `cli.build_parser`, builds an ArgumentParser, parses a documented
  command; destinations and `__all__` not pinned) plus a new pinned
  suite id `CliTests.test_cli_package_root_reexports_build_parser`
  in the tooling contract slice (f2p 110 -> 111 once AUTHOR_1P
  authors it). R05 (isolation): test.sh runs a tree integrity gate
  FIRST -- every file under Lib/Tools/Python outside the feature
  surface must hash-match the verifier-owned `tree_manifest.json`
  (3219 files, generated from the pristine image, deterministic
  across runs), bytecode caches are deleted so a crafted .pyc can
  never shadow a verified source, and unexpected files are scrubbed,
  not graded; the test_patch install verifies by CONTENT
  (reverse-apply means MSL already applied it) instead of trusting a
  sentinel, scrubs planted new-file paths, and fails closed. The
  artifact set stays the round-12 directories: file-level narrowing
  was rejected because it breaks legitimate extra-module solutions
  and risks missing-entry capture failures, while the basename
  collision still blocks directory narrowing -- the closed set is
  now enforced IN the verifier by hash rather than at the boundary.
  R07 (live forge): the probe splits in three -- the check child now
  reports per-check bytecode digests sampled around every check, an
  attestation grandchild that never imports agent code supplies
  ground truth, and the parent fails closed on any mismatch; four
  new integrity checks run first (no trace hook + real builtin
  sampler, every check's code filename is the probe's own,
  TestCase.run code-identity vs freshly compiled tree source,
  TestCase.run behavioral truthfulness). No suite-side canary was
  added: a patched `TestCase.run` never executes the canary body, so
  only the attested probe can catch it. Residual risks recorded:
  full `_child_main` replacement via a call-event trace, and
  grader-exfil (single-turn: grading runs after the agent session,
  so no in-trial feedback; platform-level).
  Validated in containers of the task image: 1-pre proofs on the
  HEAD harness (`trace_forge` 1.0 with 40/40 forged probe,
  `exports_drop` 1.0, `tuple_all` 0.0, `upper_html` 0.0); post-fix
  full run_controls green (pos 1.0 x3, all 11 negs 0.0, twice
  1.0,1.0) except `upper_html` at 0.0 as designed -- its probe
  passes 45/45 post-fix (proven by full grade: probe True while the
  two HTML suite ids fail on the old lowercase regexes) and the
  suite half rides the next AUTHOR_1P like round 7's pending ids.
  Forensics: trace_forge dies on `check code mismatch for
  integrity.no_trace (pre)`; plants run 110/110 pre-fix but are
  scrubbed (6 files) with genuine tests failing post-fix; the
  shipped install scrubber proven in isolation (neutralized-gate
  run: `scrubbed 6 planted file(s)`, genuine patch applied);
  oracle 1.0 online AND `--network=none` at 45/45 probe. Preserved
  green: every previously-green behavior still green; harness
  mirrors in sync; `probe_forge`'s forged count synced 39 -> 45.
  Separate-verifier end to end with the new harness: `codimango
  bench run -p ss007-pep752-implicit-namespaces -a oracle -k 1`
  (job 2026-11-05__03-27-14__24df65), staged, graded, reward 1.0,
  failure_mode NONE. Suite re-authoring (metadata anchor parsing,
  tooling build_parser id) rides the next AUTHOR_1P (3 contract
  slices changed: shared imports, metadata, tooling; 0 id changes
  until it lands). Scratch under /tmp/ss007rev/, removed after
  the run.
- Round 15 (SURGICAL, id-list round): graded the round-14 AUTHOR_1P
  id. fail_to_pass listed 110 while the suite holds 111 test methods
  -- `test.test_pep752_tooling.CliTests.test_cli_package_root_reexports_build_parser`
  (the round-13 R06 re-export check) graded nothing. Regenerated the
  FULL fail_to_pass
  list from a REAL in-container solved parser run (task image rebuilt
  via taskbuild.sh, layer-identical to the controls image): the
  parser emits exactly 111 pep752 ids, all PASSED solved, and the new
  id is the only delta (reverse audit clean: zero stale ids, the old
  110 equal the solved set minus the new id). Config diff is one
  added line; every other key byte-identical. Verified with the
  task's own test.sh in fresh one-shot containers of the task image:
  solved reward 1.0 (451/451, new id PASSED, probe 45/45 True), base
  reward 0.0 (340/451, new id FAILED, probe False); pass_to_pass
  340/340 green in BOTH states. test_patch NOT repacked:
  pack_test_patch.py --check reports unit 1_pep752 `current`
  (6 authored, 0 carried, 0 changed) -- the suite bytes already carry
  the new test and the patch already installs it (proven: both
  containers applied it cleanly). No suite, instruction, solution,
  or harness file touched. Measured quirk (pre-existing, fail-closed,
  same as round 4): at base the parser emits 110 pep752 verdicts
  (109 FAILED + 1 ERROR, 0 PASSED) because
  `DocsTests.test_whatsnew_announces_module` fails purely inside
  subTests with no require_impl guard, leaving a bare nameless
  testcase the parser skips -- missing grades as not-PASSED, so the
  base reward stays correct. Second test.sh run in one solved
  container trips the integrity gate on a rebuilt `Python/sysmodule.o`
  (run 1's make recompiles after the golden header edit); grading is
  one-shot per container, so verification used fresh containers.
- Round 16 (REVISION, pre-push beta REVISE with 7 High findings):
  closed all seven, zero id changes. R02/R08: the offline mirror
  copies the whole `Tools/packagenamespaces/` directory now (probe
  fixed directly; suite's `test_scripts_use_no_network` via AUTHOR_1P
  revise -- contract section rewritten, same id -- plus the permanent
  `split_harness` pos control). R05/R07: privilege separation --
  make/install/suite/probe-grandchildren run as nobody, /tests is
  root-owned read-only, the /tests snapshot is re-verified after the
  suite, and verdict files are removed up front so a tripped gate
  can never reward from stale verdicts; the permanent `tests_tamper`
  neg control replicates the demonstrated reader-rewrite bypass.
  R06: `grants.exports` pins the `GrandfatheredRegistry` root
  re-export (identity), and the uploads tests import it from the
  root via AUTHOR_1P revise (same ids); permanent
  `exports_drop_grandfathered` neg control. R09: the 97
  `Python/*.o` entries left the manifest and the gate skips `*.o`.
  R12: golden NEWS renamed to the blurb-valid
  `2026-11-04-12-00-00.gh-issue-140000.ss007.rst` (old name
  reproduced invalid, new name valid, both with blurb's own
  `load_next`; same rename in both solve.sh files and the config
  patch, whose diff is one line). Validated in containers of the
  task image: oracle 1.0 (451/451, probe 45/45, integrity 3122
  verified, all unprivileged); `tests_tamper` 1 pre-fix (forged
  readers observed in place) / 0 post-fix (34 genuine probe
  failures); `exports_drop_grandfathered` 0 post-fix (precise
  `grants.exports` ImportError); probe-level split flip proven
  separately (old probe fails `harness.offline` on the missing
  sibling, new probe passes); `twice` 1.0,1.0 with a clean
  second-run gate; `split_harness` 0 until the tooling
  re-authoring lands (expected, round-7 pattern). Preserved green:
  every previously-green behavior still green (full suite: 4/4 prior
  pos at 1.0 including upper_html, 12/12 prior neg at 0.0, twice
  1.0,1.0). Harness mirrors in sync
  (probe/test.sh/run_script.sh/manifest identical in both trees).
  Scratch under /home/uldis/cpython/.scratch/ss007-r16/, removed
  after the run.

## R17 surgical: strip revise keys from kind=tests jobs (2nd occurrence)
AUTHOR_1P parked authoring_blocked again on the exact R8
misconfiguration: "revise": true is valid only on kind="instruction"
jobs. Found and removed "revise" + "revise_reason" from TWO
kind="tests" jobs (uploads: import GrandfatheredRegistry from the
package root; tooling: copy the whole Tools/packagenamespaces dir) --
all six test jobs checked, the other four were already clean. Kept
"revise": true on the kind="instruction" job (the round-9 re-check
request is still pending; no instruction page update has landed
since). No contract edits, no redraw flags added (no target needs
blank-slate treatment -- both test slices re-author revise-in-place
automatically on the contract change). Rewrote the file indented
(same 7 jobs, same targets/sources); verified valid JSON, 7 jobs
intact, zero kind="tests" jobs carry revise/redraw keys.
Durable avoidance: before touching AUTHORING_JOBS.json, re-read this
rule -- "revise" exists ONLY on kind="instruction"; kind="tests"
re-authoring rides the contract change automatically, so a tests job
gets NO revise/redraw keys, ever -- and after any edit, run the
zero-tests-with-revise/redraw assert (the python one-liner used this
round) before finishing. A tests slice that genuinely needs a
blank-slate rewrite gets "redraw": true plus a stated reason here,
never "revise".
