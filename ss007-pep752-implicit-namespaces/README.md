# ss007-pep752-implicit-namespaces

Implement Accepted PEP 752 (Implicit namespaces for package repositories)
inside CPython: a namespace-grant core library, an upload-authorization
gate, a PEP 691 JSON Simple API v1.5 repository service, an
installer-side security-policy engine, a grant-management CLI with shell
fixture/verification scripts, a spec-conformance test matrix, and full
`Doc/` documentation.

Single-turn long-horizon SWE-Bench Pro task (one `[[steps]]` block in the
multi-turn form). Binary reward: 1 iff every `fail_to_pass` and
`pass_to_pass` test in `steps/1_pep752/tests/config.json` passes AND the
independent probe (`tests/probe.py`, a second behavioral channel that never
reads the JUnit report) passes.

Round 7 (REVISION): pins conflict-owner-as-uploader, the bare-dump
envelope, record-without-authorize, empty-owner upload rejection, sparse
direct-only links and project-naming (wording-free) HTML; adds the
persisted-schema, distribution-backlink, network-free and damaged-fixture
coverage; fixes the golden empty-owner and second-index behaviors; closes
the in-process JUnit-rewrite route with the probe. 110 fail_to_pass (9 new
ids authored by AUTHOR_1P next) + 340 pass_to_pass.
