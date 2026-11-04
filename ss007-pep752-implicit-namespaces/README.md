# ss007-pep752-implicit-namespaces

Implement Accepted PEP 752 (Implicit namespaces for package repositories)
inside CPython: a namespace-grant core library, an upload-authorization
gate, a PEP 691 JSON Simple API v1.5 repository service, an
installer-side security-policy engine, a grant-management CLI with shell
fixture/verification scripts, a spec-conformance test matrix, and full
`Doc/` documentation.

Single-turn long-horizon SWE-Bench Pro task (one `[[steps]]` block in the
multi-turn form). Binary reward: 1 iff every `fail_to_pass` and
`pass_to_pass` test in `steps/1_pep752/tests/config.json` passes.
