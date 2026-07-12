# Contributing

Contributions are welcome: bug reports, fixes, features, and docs.

## Workflow

1. Fork/branch from `main` (the `legacy` branch is frozen).
2. Set up: `uv sync && uv run pre-commit install`.
3. Make your change; add or update tests for anything with logic.
4. Run the gate locally - CI runs the same:

```sh
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

5. Open a pull request against `main` with a conventional-commit style title
   (e.g. `feat(services): ...`, `fix(auth): ...`).

## Ground rules

- No secrets in the repo - configuration comes from `.env` (gitignored);
  pre-commit and CI run gitleaks.
- This repository is a Spotify connector only: no AI, recommendation,
  curation, analytics, or application-specific business logic.
- `repository/` methods are atomic Spotify API operations only - no
  sequencing or algorithms. `services/` owns all business logic and
  workflows, and takes explicit identifiers only (never a URL/URI - parsing
  happens exclusively at the `cli/`/`tools/` boundary). Only `cli/` may print
  or prompt. See [docs/architecture.md](docs/architecture.md).
- New MCP tools need an entry in
  [`tools/capabilities.py`](src/spotify_mcp/tools/capabilities.py) (read_only,
  destructive, idempotent, confirmation_required, scopes) - a test enforces
  this.
- Keep it minimal: prefer the standard library, avoid new dependencies, and
  don't add abstractions without a second consumer.

## Bug reports

Open a [GitHub issue](../../issues/new/choose) with steps to reproduce,
expected vs actual behavior, and sample references (playlist/track links) where relevant.

## License

By contributing you agree your contributions are licensed under the project's
[MIT License](LICENSE).
