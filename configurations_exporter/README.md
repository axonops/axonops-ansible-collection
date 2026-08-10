# AxonOps Configuration Exporter

This python script allows you to export your AxonOps configuration, including alert rules, dashboards, and integrations, into a structured YAML format. 
This can be useful for backup purposes or for migrating configurations between different AxonOps instances.

## Requirements
- Python 3.10 or higher
- pip / pip3 / pipenv / uv
- Access to the AxonOps API with appropriate permissions

## Installation
1. Clone the repository or download the script directly.
2. Install the required Python dependencies using one of the methods described below.
3. Configure your API credentials and organization/cluster information as environment variables or in a configuration file.
4. Run the script to export your configuration.

### Install Python dependencies

This project provides multiple ways to install Python dependencies.  
Choose the method that best fits your workflow.

The dependencies are declared at the root of the project (where `requirements.txt`,
`Pipfile` and `pyproject.toml` are located), so install them from there.

---

#### Option 1: Using pipenv (recommended)

Pipenv is a popular tool for managing Python dependencies and virtual environments. 
It provides an easy way to create isolated environments and manage dependencies.

```shell
pip install pipenv
pipenv install
```
To run commands inside the environment:
```shell
pipenv shell
cd configurations_exporter
python3 configurations_exporter.py -h
```
Or:
```shell
cd configurations_exporter
pipenv run python configurations_exporter.py -h
```

#### Option 2: Using `venv` and `pip`

This is the most portable and widely supported method.

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Run the application:
```shell
cd configurations_exporter
python3 configurations_exporter.py -h
````
#### Option 3: Using uv

uv is a fast alternative to pip.

Install uv:

```shell
pip install uv
```
Then install dependencies:

```shell
uv pip install -r requirements.txt
```
To run the application:
```shell
cd configurations_exporter
uv run python configurations_exporter.py -h
```

#### Optional: Install from pyproject.toml

If you prefer modern Python packaging tools:

```shell
pip install .
```
With uv:
```shell
uv pip install .
```

**Note:** all the examples below are run from the `configurations_exporter` directory.
To run from a different directory, use the relative path — e.g.
`configurations_exporter/configurations_exporter.py` from the root of the project.

## Usage

To run the tool:

```shell
python3 configurations_exporter.py [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]
```

Commands:

| Command | Purpose |
| --- | --- |
| `export` | Export the configuration of your clusters as YAML |
| `sections` | List the configuration sections the tool can export |

### Global options

Every global option falls back to an environment variable, so flags and the environment
are interchangeable.

| Option | Environment variable | Default | Example | Description |
| --- | --- | --- | --- | --- |
| `--org` | `AXONOPS_ORG` | — (required) | `acme` | Name of your organisation |
| `--cluster` | `AXONOPS_CLUSTER` | every cluster of the org | `prod` | Name of your cluster, e.g. `prod`, `stage`, `dev` |
| `--cluster-type` | `AXONOPS_CLUSTER_TYPE` | `cassandra` | `kafka` | Type of the cluster: `cassandra`, `dse` or `kafka` |
| `--token` | `AXONOPS_TOKEN` | — | `axon_...` | API token used to authenticate with AxonOps Cloud (SaaS) |
| `--username` | `AXONOPS_USERNAME` | — | `admin` | Username for AxonOps Self-Hosted when authentication is enabled |
| `--password` | `AXONOPS_PASSWORD` | — | `s3cret` | Password for AxonOps Self-Hosted when authentication is enabled |
| `--url` | `AXONOPS_URL` | AxonOps Cloud | `https://axonops.internal:3000` | AxonOps URL when not using AxonOps Cloud |
| `-v`, `--verbose` | — | off | `-v` | Print the requests being made (repeatable) |
| `--version` | — | — | `--version` | Print the version and exit |

`--org` is the only required option. When `--url` is omitted the tool talks to AxonOps
Cloud.

### Choosing the clusters

`--cluster` name one cluster. Optional. Without it,
every cluster of the organisation is exported, each into its own directory.

`--cluster-type` says what kind of cluster it is: `cassandra` (the default), `dse` or
`kafka`. It describes the cluster named by `--cluster`; without `--cluster` each
cluster is exported with its own type.

Credentials are necessary when authentication is enabled:

* `--token` for AxonOps Cloud.
* `--username` and `--password` for a self-hosted instance with authentication
  enabled. A `--token`, if given, wins.

```shell
python3 configurations_exporter.py \
  --url http://127.0.0.1:3000 --org acme --cluster dev export
```

### `export` options

| Option | Default | Example | Description |
| --- | --- | --- | --- |
| `--section` | all sections | `--section alert_rules` | Export only this section — repeat the flag for several |
| `--fail-on-error` | off | `--fail-on-error` | Abort the export when a section cannot be exported, instead of skipping it |

Exportable sections: `alert_rules`, `dashboards`, `integrations`, `healthchecks`,
`logcollectors`, `silences`, `adaptive_repair`, `scheduled_repairs`, `backups`,
`commitlog_archive`, `agent_disconnection_tolerance`.

The export always writes one YAML file per section into
`exports/<org>/<cluster>/<section>.yaml`, relative to the directory you run the tool
from. Existing files are overwritten, so re-running the export refreshes the copy on
disk.

Not every section exists on every cluster — one with no commitlog archiving
configured, for instance, has no `commitlog_archive`. Those sections are skipped and
named in the summary, so the rest of the export still lands on disk:

```text
Exported 10 section(s) to exports/acme/prod-cassandra/, 1 skipped (commitlog_archive)
```

Pass `--fail-on-error` to stop at the first section that cannot be exported instead.

### Examples

Export everything from an AxonOps Cloud cluster:

```shell
export AXONOPS_ORG=acme
export AXONOPS_CLUSTER=prod-cassandra
export AXONOPS_TOKEN=axon_your_api_token

python3 configurations_exporter.py export
# -> exports/acme/prod-cassandra/alert_rules.yaml, dashboards.yaml, ...
```

Export only the alert rules and dashboards of a self-hosted cluster:

```shell
python3 configurations_exporter.py \
  --url https://axonops.internal:3000 \
  --org acme --cluster prod-cassandra \
  --username admin --password "$AXONOPS_PASSWORD" \
  export --section alert_rules --section dashboards
```

Export a single Kafka cluster, showing each request as it is made:

```shell
python3 configurations_exporter.py -v \
  --org acme --cluster prod-kafka --cluster-type kafka --token "$AXONOPS_TOKEN" \
  export
# -> exports/acme/prod-kafka/alert_rules.yaml, ...
```

Export **every** cluster of an organisation from a local instance with authentication
disabled — no `--cluster`, so they are all exported:

```shell
python3 configurations_exporter.py \
  --url http://127.0.0.1:3000 --org acme export
# -> exports/acme/prod-cassandra/..., exports/acme/prod-kafka/..., ...
```

### Output format

Every file holds a single section and records the cluster it came from:

`exports/acme/prod-cassandra/alert_rules.yaml`:

```yaml
org: acme
cluster: prod-cassandra
cluster_type: cassandra
configuration:
  alert_rules:
  - alert: CPU high
    operator: '>'
    warning_value: 80
```

### CLI settings

Alongside the YAML, every export writes two files into `exports/<org>/`:

| File | What it is |
| --- | --- |
| `.env.axonops` | The connection settings for the [AxonOps CLI](../cli), ready to `source ./.env.axonops` |
| `<org>.sh` | The CLI commands that reproduce the exported configuration on another environment |

**No credential is ever written to disk.** `AXONOPS_ORG`, `AXONOPS_CLUSTER`,
`AXONOPS_URL` and `AXONOPS_USERNAME` are filled in from the run; the token and the
password are left as commented placeholders to complete by hand.

```shell
# exports/acme/.env.axonops
export AXONOPS_ORG=acme
export AXONOPS_URL=https://axonops.internal:3000
# export AXONOPS_TOKEN='aaaabbbbccccddddeeee'
# export AXONOPS_PASSWORD='I <3 AxonOps!'
```

One script covers every cluster of the org, each named explicitly:

```shell
# exports/acme/acme.sh
AXONOPS_CLI="${AXONOPS_CLI:-python3 axonops.py}"

### cluster prod-cassandra (cassandra)

# adaptive_repair
$AXONOPS_CLI --cluster prod-cassandra repair --disabled --gcgrace 86400 \
  --tableparallelism 10 --segmentretries 3 --excludetwcstables true
```

Replay it against the target environment with:

```shell
source ./exports/acme/.env.axonops                       # edit in the credentials first
AXONOPS_CLI='python3 /path/to/cli/axonops.py' bash ./exports/acme/acme.sh
```

Only the sections the CLI can set today become commands — `adaptive_repair`,
`scheduled_repairs` and `silences`. The rest are listed as a `TODO` comment at the
end of the script and remain available as YAML.

## Development

```shell
# Run the tests (unittest based; pytest collects them too)
python3 -m unittest discover -s tests -v
pytest tests/
```

Layout:

| Path | Responsibility |
| --- | --- |
| `configurations_exporter.py` | Front end — builds `Application` and runs it |
| `src/application.py` | Argument parsing and command dispatch |
| `src/axonops.py` | HTTP client: base URL resolution, auth, `do_request()` |
| `src/clusters.py` | Discovery of the clusters of an org from `/api/v1/orgs` |
| `src/cli_script.py` | Renders `.env.axonops` and `<org>.sh` from the exported configuration |
| `src/exporter.py` | Fetches the configuration sections and renders the YAML |
| `src/urls.py` | Registry of the API endpoints and the exportable sections |
| `src/utils.py` | Shared errors and helpers |

Adding a section means adding one entry to `SECTIONS` in `src/urls.py` — the CLI help,
the `sections` command, and the export all read from that registry.

## Support

Maintained by [AxonOps](https://axonops.com). For support, contact us at
[axonops.com/contact](https://axonops.com/contact).