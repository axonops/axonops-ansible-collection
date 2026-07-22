# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Scope: this file covers `cli/` (the `axonopscli` Python CLI). The repository root
`CLAUDE.md` covers the Ansible collection and carries the mandatory agent gates /
commit standards that apply here too.

## Commands

All commands run from `cli/`.

```bash
# Run the CLI (no console-script entry point; invoke the wrapper directly)
python3 axonops.py health
python3 axonops.py <subcommand> -h

# Credentials come from env vars — see .env.axonops.example
cp .env.axonops.example .env.axonops && source ./.env.axonops

# Tests (unittest-based; pytest also collects them)
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_get_jwt_unittest -v                                  # single module
python3 -m unittest tests.test_get_jwt_unittest.TestGetJWT.test_get_jwt_calls_do_request_and_caches_token
pytest tests/                                                                        # equivalent
```

Tests import `axonopscli.*` as a top-level package, so they must be run with `cli/`
as the working directory.

There is no CI workflow for the CLI — every `.github/workflows/*.yml` is a molecule
job for an Ansible role. CLI changes are only verified by running the tests locally.

## Dependency notes

`requests` is the only runtime dependency, and it is not declared anywhere in this
directory. The root `pyproject.toml` covers lint tooling for the collection, not the
CLI. `README.md` instructs users to `pip install -r requirements.txt` or use pipenv,
but neither `requirements.txt` nor `Pipfile` exists — treat those README sections as
stale rather than as a description of the current layout.

## Architecture

Three layers, top to bottom:

1. **`axonops.py`** (repo-root wrapper) — thin `main()` that constructs
   `Application` and calls `run(sys.argv[1:])`.
2. **`axonopscli/application.py`** — the entire CLI surface. One `argparse`
   subparser per subcommand (`health`, `repair`/`adaptiverepair`, `scheduledrepair`,
   `dashboard`, `silence`), each wired via `set_defaults(func=self.run_*)`. Every
   global option defaults to an `AXONOPS_*` env var, so flags and environment are
   interchangeable. Cross-flag validation (e.g. `--tables` requires `--keyspace`)
   lives inline in `run()` after `parse_args`; per-command validation lives in the
   matching `run_*` method. Adding a subcommand means adding a subparser plus a
   `run_*` handler here — there is no plugin/registry mechanism.
3. **`axonopscli/axonops.py`** — the `AxonOps` HTTP client. Owns base-URL
   resolution, auth, and `do_request()`, which every component funnels through.
4. **`axonopscli/components/*.py`** — one class per API area
   (`AdaptiveRepair`, `ScheduledRepair`, `Dashboard`, `Silence`, `Nodes`). Each
   holds a class-level relative endpoint constant (e.g.
   `adaptive_repair_url = "/api/v1/adaptiveRepair"`) and builds
   `self.full_url = f"{endpoint}/{org}/cassandra/{cluster}"` in `__init__`.

### Component convention

Mutating components follow a fixed read–modify–write sequence, driven from the
`run_*` handler in `application.py`:

`get_actual_*()` → GET the current server-side payload → `check_*()` → mutate it in
place via `set_options()` (each CLI flag maps to one payload key, guarded by
`getattr(self.args, 'flag', None) is not None`) → `set_repair()` POSTs the whole
modified payload back. The CLI never constructs payloads from scratch; it patches
what the server returned. Preserve this when adding options — a new flag is a new
guarded block in `set_options()`, not a new request.

Note the `cassandra` segment is hardcoded into every component's `full_url` even
though `AxonOps` carries a configurable `cluster_type` — only `AxonOps`'s own
methods (`get_integration_output`, `find_nodes_ids`) honour `cluster_type`.

### Auth and base URL

`AxonOps.__init__` picks the environment:
- no `base_url` → AxonOps Cloud, `https://dash.axonops.cloud/{org}` (org is part of
  the path)
- explicit `base_url` → self-hosted axon-server, org is *not* appended

Auth precedence in `do_request`: username/password logs in via `/api/login` for a
JWT, but an `api_token`, if present, overwrites the bearer afterwards.

### Known inconsistency in `do_request`

`do_request` returns a bare `dict` (or raises `HTTPCodeError` on an unexpected
status), but `get_jwt`, `get_integration_output`, `find_integration_*`, and
`find_nodes_ids` all unpack it as `result, error = ...`. Those call sites are broken
against the real implementation and only pass because the tests mock `do_request` to
return a tuple. Component code (`repair.py`, `silence.py`, etc.) uses the correct
single-value form. Do not copy the tuple-unpacking pattern into new code.
