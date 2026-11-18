# configurations_exporter — CLAUDE.md

Python CLI that exports the configuration of AxonOps clusters (alert rules, dashboards,
integrations, repairs, backups…) to YAML, plus the `.env.axonops` and `<org>.sh` files
that let the [AxonOps CLI](../cli) replay that configuration elsewhere.

It is a standalone tool inside an otherwise Ansible collection — the collection-wide
role/molecule conventions in the root `CLAUDE.md` do not apply here.

## Working directory

Everything is run from `configurations_exporter/`: the entry point resolves `src` as a
top-level package relative to itself, and the tests import `src.*` the same way.

```shell
python3 configurations_exporter.py --help
python3 configurations_exporter.py --org acme --url http://127.0.0.1:3000 export
python3 -m unittest discover -s tests -v
```

Dependencies are declared at the **repo root** (`requirements.txt`, `Pipfile`,
`pyproject.toml`), so install from there. A working venv lives at `../.venv`.

## Layout

| Path | Responsibility |
| --- | --- |
| `configurations_exporter.py` | Front end only — builds `Application` and runs it. Keep it thin. |
| `src/application.py` | Argument parsing, command dispatch, top-level error handling |
| `src/axonops.py` | HTTP client: base URL resolution, auth, `do_request()` |
| `src/clusters.py` | Discovers the clusters of an org from `/api/v1/orgs` |
| `src/exporter.py` | Fetches the sections and writes the YAML |
| `src/cli_script.py` | Renders `.env.axonops` and `<org>.sh` |
| `src/urls.py` | Registry of API endpoints and exportable sections |
| `src/utils.py` | Shared errors (`ExporterError`, `HTTPCodeError`, `APIConnectionError`) and helpers |

## Conventions

- **Adding a section**: one entry in `SECTIONS` in `src/urls.py` — the CLI help, the
  `sections` command and the export all read from that registry. Do not special-case a
  section in `exporter.py`.
- **Never write a credential to disk.** `.env.axonops` gets org / cluster / url /
  username as live exports; `AXONOPS_TOKEN` and `AXONOPS_PASSWORD` stay commented
  placeholders. `test_the_token_is_never_written_to_disk` guards this — keep it passing.
- **Errors** surface as `Error: …` on stderr with exit code 1; never let a `requests`
  traceback reach the user.
- **Leniency is the default**: a section the API rejects is skipped and named in the
  summary. `--fail-on-error` opts into strict mode.
- **Global options precede the subcommand** (`--org acme export`, not
  `export --org acme`) — argparse subparsers, so tests must be written that way too.
- Everything is written under `exports/<org>/<cluster>/`, relative to the cwd.
  `exports/` is gitignored; tests must chdir into a temp dir (see `ApplicationTestCase`)
  so they never write into the repo.

## Tests

`unittest` + `unittest.mock`, matching the sibling `cli/` tool rather than the
pytest-bdd standard used elsewhere. `pytest tests/` collects them too. Cover the happy
path and the invalid/edge input. Fixtures use `demo`/`demo-cluster`; user-facing docs
use `acme`.

## Docs

`README.md` is user-facing: no internal API paths, no implementation detail, examples
run from this directory. Internals belong in its Development section or here. Every
behaviour change also updates the root `CHANGELOG.md` under `[Unreleased]`.
