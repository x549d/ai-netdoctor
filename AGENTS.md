# AI NetDoctor maintenance

- Read [CONTRIBUTING.md](CONTRIBUTING.md) for the local test command and review process.
- Keep regression tests offline. Mock DNS, sockets, TLS, and HTTP as needed. Use synthetic data for diagnostic examples.
- Keep public JSON fields, exit codes, and CLI entry points compatible unless the change explicitly documents a break.
- Keep both READMEs aligned for user-visible behavior. Keep package, CLI, and release versions aligned.

## Code Review Rules

- Prioritize actionable regressions in resolver timeout and subprocess cleanup, proxy scoping and credential redaction, TLS verification, redirects, HTTP header allowlists, and response-body privacy.
- Check that network reachability, HTTP response, and authenticated API access remain distinct.
- Flag changes that widen GitHub Actions permissions, expose release credentials, or allow publishing from unreviewed refs.
- Report findings with file and line, impact, and a reproducible scenario. Review is advisory and the maintainer decides whether to merge.
