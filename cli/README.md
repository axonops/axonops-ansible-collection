# AxonOps CLI

This CLI is designed to extend the AxonOps Configuration Automation Ansible module.

## Installation

### Install Python dependencies

This project provides multiple ways to install Python dependencies.
Choose the method that best fits your workflow.

All install commands should be run from the root of the project directory.
The application should instead be run from the `cli` directory to avoid import issues with the Ansible module.

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
python3 <command.py>
```
Or:
```shell
pipenv run python <command.py>
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
python3 <command.py>
````

### Authentication and Settings

This CLI accepts both command-line parameters and environment variables.

For easy of use; an environment configuration file was created to set the required environment variables for authentication and connection settings.
You can find the template for this file in `cli/.env.axonops.example`. You can copy this file to `.env.example` and set the required values for your environment.

You can load the environment variables from the file using the following command:

```shell
source .env.axonops
```
Now we specify the required environment variables for the most common cases of connecting to AxonOps.

#### connect to AxonOps Cloud
AxonOps clouds require the `AXONOPS_ORG`, `AXONOPS_CLUSTER`, and `AXONOPS_TOKEN` environment variables to be set for authentication.
The token can be obtained from the AxonOps Cloud UI by navigating to the "API Tokens" section in the left menu of the Organization main page.

Example of variables for AxonOps Cloud:
```shell
export AXONOPS_ORG='test'
export AXONOPS_CLUSTER="thingscluster"
export AXONOPS_TOKEN='aaaaabbbbccccddddeeee'
```

#### connect to AxonOps Self-Hosted
AxonOps Self-Hosted requires the `AXONOPS_URL` to specify the URL of your AxonOps instance.
If authentication is enabled, you also need to set the `AXONOPS_USERNAME` and `AXONOPS_PASSWORD` environment variables.

Example of variables for AxonOps Self-Hosted with authentication enabled:
```shell
export AXONOPS_URL='http://localhost:3000'
export AXONOPS_USERNAME='john.doe'
export AXONOPS_PASSWORD='I<3AxonOps!'
```
Example of variables for AxonOps Self-Hosted with authentication disabled:
```shell
export AXONOPS_URL='http://localhost:3000'
```

## Using of CLI

### Global Options

All commands accept those attributes

* `--org` Name of your organisation (environment variable `AXONOPS_ORG`).
* `--cluster` Name of your cluster (environment variable `AXONOPS_CLUSTER`).
* `--token` AUTH_TOKEN used to authenticate with the API in AxonOps Cloud (environment variable `AXONOPS_TOKEN`).
* `--username` Username used for AxonOps Self-Hosted when authentication is enabled (environment variable `AXONOPS_USERNAME`).
* `--password` Password used for AxonOps Self-Hosted when authentication is enabled (environment variable `AXONOPS_PASSWORD`).
* `--url` Specify the AxonOps URL if not using the AxonOps Cloud environment (environment variable `AXONOPS_URL`).

### Connections

The CLI uses the same connection methods as the Ansible module. Please refer to the connection section of the main
project for more information.

The following examples are for the organisation `test` and the cluster `thingscluster` on AxonOps Cloud.
For self-hosted authentication, refer to the authentication section of the main project.

Authenticate to the cluster:

```shell
export AXONOPS_ORG='test'
export AXONOPS_CLUSTER="thingscluster"
export AXONOPS_TOKEN='aaaaabbbbccccddddeeee'
```

### `info` Subcommand
Prints general information about the cluster.
This can be used to verify that the connection to the cluster is working and to get some basic information about the cluster.
#### Examples:

```shell
$ pipenv run python axonops.py info
```

### `adaptiverepair` Subcommand

Manages **Adaptive Repair** in AxonOps.

#### Options:

* `--enabled` Enables AxonOps Adaptive Repair.
* `--disabled` Disable AxonOps Adaptive Repair.
* `--excludedtables` Excluded Tables. This parameter accepts a comma-separated list in the format
  `keyspace.table1,keyspace.table2`.
* `--excludetwcstables` Exclude TWCS tables.
* `--gcgrace` GG Grace Threshold in Seconds.
* `--segmentretries` Segment Retries.
* `--maxsegmentspertable` Max Segments Per Table.
* `--segmenttargetsizemb` Segment Target Size in MB.
* `--tableparallelism` Concurrent Repair Processes.

#### Examples:

Print the list of options for the repair command:

```shell
$ pipenv run python axonops.py repair -h
```

Enable the AxonOps Adaptive Repair:

```shell
pipenv run python axonops.py repair --enabled
```

Disable the repair:

```shell
$ pipenv run python axonops.py repair --disable
```

Enable the repair and set the GC Grace Threshold to 86,400 seconds (AxonOps will ignore tables that have a
gc_grace_seconds value lower than the specified threshold):

```shell
$ pipenv run python axonops.py repair --enable --gcgrace 86400
```

Enable the repair and set the table parallelism to 100 (number of tables processed in parallel):

```shell
$ pipenv run python axonops.py repair --enable --tableparallelism 100
```

Enable the repair and set the segment retry limit to 10 (number of times a segment can fail before raising an alert and
stopping repairs for that cycle):

```shell
$ pipenv run python axonops.py repair --enable --segmentretries 10
```

Enable the repair and set the segment chunk size to 250 MB (amount of data repaired at a time):

```shell
$ pipenv run python axonops.py repair --enable --segmenttargetsizemb 250
```

Exclude specific tables from repair (comma separated list of `keyspace.table`):

```shell
$ pipenv run python axonops.py repair --enable --excludedtables system_auth.roles,system_auth.role_permissions
```

Set the Maximum Segments Per Table to 131,072:

```shell
$ pipenv run python axonops.py repair --enable --maxsegmentspertable 131072
```

Set the timeout per Segment to 3 hours:

```shell
pipenv run python axonops.py repair --enable --segmenttimeout 3h
```

### `scheduledrepair` Subcommand

Manages **Scheduled Repair** in AxonOps.

#### Options:

* `--keyspace` Keyspace to repair. If not set, all keyspaces will be repaired.
* `--tables` Comma-separated list of tables to repair within the specified keyspace. If not set, all tables in the
  keyspace will be repaired.
* `--excludedtables` Excluded Tables. This parameter accepts a comma-separated list in the format
  `keyspace.table1,keyspace.table2`.
* `--nodes` Comma-separated list of node IP addresses to run the repair on. If not set, all nodes in the cluster will be
  included.
* `--scheduleexpr` Cron Expression for Scheduled Repair. If not set, Scheduled Repair will run immediately. Crontab are in UTC time.
* `--segmented` Enables Segmented Repair.
* `--segmentspernode` Number of Segments Per Token Range (only applicable if `--segmented` is set).
* `--incremental` Enables Incremental Repair. If not set, a full repair will be performed.
* `--jobthreads` Number of Job Threads to use for the repair process. If not set, the default value of 1 will be used.
* `--partitionerrange` Repair Partitioner Range Only.
* `--parallelism` Repair Parallelism. Accepted values are `sequential`, `parallel`, and `dc_aware`. If not set, the
  default value of `sequential` will be used.
* `--optimisestreams` Optimize Streams during repair (require Cassandra 4.1+).
* `--datacenters` Comma-separated list of datacenters to include in the repair. If not set, all datacenters will be
  included.
* `--tags` Tags to associate with the scheduled repair job. Tags are used to identify repair jobs in AxonOps.
  This parameter accepts a string value.
* `--paxosonly` Run paxos repair only. Default is false.
* `--skippaxos` Skip paxos repair. Default is false.
* `--delete` Delete Scheduled Repair. This option needs to be paired with a tags value to identify which scheduled
  repair job to delete.
* `--deleteall` Delete all Scheduled Repairs. This removes all scheduled repair jobs from the cluster.

#### Examples:

Print the list of options for the scheduled repair command:

```shell
$ pipenv run python axonops.py scheduledrepair -h
```

Run a scheduled repair immediately:

```shell
$ pipenv run python axonops.py scheduledrepair
```

Run a scheduled repair with a cron expression (this example runs the repair every Sunday at midnight):

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0'
```

Run a scheduled repair for a specific keyspace with a cron expression (this example runs the repair for the
`axonopslove` keyspace every Sunday at midnight):

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --keyspace axonopslove
```

Run a scheduled repair for specific tables in a keyspace with a cron expression (this example runs the repair for the
`steps5` and `steps60` tables in the `axonopslove` keyspace every Sunday at midnight):

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --keyspace axonopslove --tables steps5,steps60
```

Run a scheduled repair for a specific keyspace excluding certain tables with a cron expression (this example runs the
repair for the `axonopslove` keyspace every Sunday at midnight, excluding the `bad1` and `bad6` tables):

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --keyspace axonopslove --excludedtables axonopslove.bad1,axonopslove.bad6
```

Run a scheduled repair on specific nodes with a cron expression (this example runs the repair every Sunday at midnight
on nodes with IP addresses `172.18.0.[1,2]`):

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --nodes 172.18.0.1,172.18.0.2
```

Run a segmented scheduled repair with a cron expression:

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --segmented
```

Run a segmented scheduled repair with a cron expression and specify the number of segments per node (100 in this
example):

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --segmented --segmentspernode 100
```

Run an incremental scheduled repair with a cron expression:

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --incremental
```

Run a scheduled repair with 100 job threads and a cron expression:

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --jobthreads 100
```

Run a scheduled repair for the partitioner range only with a cron expression:

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --partitionerrange
```

Run a scheduled repair with parallelism set to 'parallel' with a cron expression:

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --parallelism parallel
```

Run a scheduled repair optimizing streams with a cron expression:

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --optimisestreams
```

Run a scheduled repair for a specific datacenter with a cron expression (`dc` in this example):

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --datacenters dc
```

Run a scheduled repair with tags with a cron expression:

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --tags 'Weekly repair'
```

Run a scheduled paxos-only repair with a cron expression:

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --skippaxos
```

Run a scheduled repair skipping paxos repair with a cron expression:

```shell
$ pipenv run python axonops.py scheduledrepair --scheduleexpr '0 0 * * 0' --paxosonly
```

Delete a scheduled repair job with specific tags:

```shell
$ pipenv run python axonops.py scheduledrepair --delete --tags 'Weekly repair'
```

Delete all scheduled repair jobs:

```shell
$ pipenv run python axonops.py scheduledrepair --deleteall
```

### `dashboard` Subcommand

Manages the AxonOps Dashboards.

#### Options:

* `--importfile` Path to the dashboard JSON file to import.
* `--exportpath` Path to save the exported dashboard JSON file.
* `--list` List all dashboards in the cluster.
* `--deletedashboard` Delete a dashboard by its name.
* `--dashboardname` Name of the dashboard to delete or export.
* `--position` X position of the dashboard used during import. Accepted value are integers from 1 to n or -1 to -n (negative number indicates position from the end). If not set, the dashboard will be imported at the end.
* `--overwrite` Overwrite an existing dashboard during import if a dashboard with the same name exists.

#### Examples:

Print the list of options for the dashboard command:

```shell
$ pipenv run python axonops.py dashboard -h
```

List all dashboards in the cluster:

```shell
$ pipenv run python axonops.py dashboard --list
```

Export a dashboard by its name to the current directory:

```shell
$ pipenv run python axonops.py dashboard -h --exportpath . --dashboardname Table
```

Export all dashboards to the current directory:

```shell
$ pipenv run python axonops.py dashboard --exportpath .
```

Override an existing dashboard with one from a JSON file:

```shell
$ pipenv run python axonops.py dashboard --dashboardname Table --importfile ./Table_dashboard.json  --overwrite
```

Override an existing dashboard with one from a JSON file, taking the name from the file:

```shell
$ pipenv run python axonops.py dashboard --importfile ./Table_dashboard.json  --overwrite
```

Override an existing dashboard with one from a JSON file, taking the name from the file and setting its X position to 3:

```shell
$ pipenv run python axonops.py dashboard --importfile ./Table_dashboard.json  --overwrite --position 3
```

Override an existing dashboard with one from a JSON file, taking the name from the file and setting its X position to
-1 (fist from the bottom):

```shell
$ pipenv run python axonops.py dashboard --importfile ./Table_dashboard.json  --overwrite --position -1
```

### `silence` subcommand

Manage the AxonOps Alert Silences.

#### Options:
* `--list` List all active silences in the cluster.
* `--create` Create a new silence.
* `--deletesilence` Delete a silence by its ID.
* `--cronexpr` Cron Expression for Recurring Silence. If not set, the silence will be created immediately. Crontab are in UTC time.
* `--duration` Duration of the silence. Accepted values are a number followed by a time unit (s for seconds, m for minutes, h for hours, d for days). If not set, the default duration of the silence will be 1 hour.
* `--dcs` JSON array of datacenters to include in the silence. If not set, all datacenters will be included.
The format of the JSON array should be `{"Name": "dc1","Racks": [{"Name": "RAC1","Nodes": ["b167aca6-b6b1-4bd5-bc45-3e27632e844d"]}]}`.
* `--silencemetricsalerts` Silence Metrics Alerts. If not set, all alerts will be silenced.
* `--silenceservicechecksalerts` Silence Service Checks Alerts. If not set, all alerts will be silenced.
* `--silenceeventalerts` Silence Event Alerts. If not set, all alerts will be silenced.
* `--silencebackupalerts` Silence Backup Alerts. If not set, all alerts will be silenced.
* `--silencebackuprestorealerts` Silence Backup Restore Alerts. If not set, all alerts will be silenced.
* `--silenceauditalerts` Silence Audit Alerts. If not set, all alerts will be silenced.
* `--silenceadaptiverepairalerts` Silence Adaptive Repair Alerts. If not set, all alerts will be silenced.
* `--silencegenericalerts` Silence Generic Alerts. If not set, all alerts will be silenced.
* `--silencegenerictaskalerts` Silence Generic Task Alerts. If not set, all alerts will be silenced.
* `--silencelogalerts` Silence Log Alerts. If not set, all alerts will be silenced.
* `--silencenodealerts` Silence Node Alerts. If not set, all alerts will be silenced.
* `--silencerepairalerts` Silence Repair Alerts. If not set, all alerts will be silenced.
* `--silencerollingrestartalerts` Silence Rolling Restart Alerts. If not set, all alerts will be silenced.
* `--silencescheduledreportsalerts` Silence Scheduled Reports Alerts. If not set, all alerts will be silenced.

#### Examples:

Print the list of options for the silence command:

```shell
$ pipenv run python axonops.py silence -h
```
List all active silences in the cluster:
```shell
$ pipenv run python axonops.py silence --list
```
Create a new silence with a duration of 1 hour (default) to the entire cluster:
```shell
$ pipenv run python axonops.py silence --create
```
Delete a silence by its ID: 0974a3e0-d552-4d65-a96b-c7439c90cd7b
```shell
$ pipenv run python axonops.py silence --deletesilence 0974a3e0-d552-4d65-a96b-c7439c90cd7b
```
Create a new recurring silence with a cron expression (this example creates a silence every day at 4 AM UTC):
```shell
$ pipenv run python axonops.py silence --create --cronexpr '0 4 * * *'
```
Create a new silence with a duration of 1 day to the entire cluster:
```shell
$ pipenv run python axonops.py silence --create --duration '1d'
```
Create a new instant silence on the metric alerts:
```shell
$ pipenv run python axonops.py silence --create --silencemetricsalerts
```
Create a new instant silence on the service checks alerts:
```shell
$ pipenv run python axonops.py silence --create --silenceservicechecksalerts
```
Create a new instant silence on the event alerts:
```shell
$ pipenv run python axonops.py silence --create --silenceeventalerts
```
Create a new instant silence on the backup alerts:
```shell
$ pipenv run python axonops.py silence --create --silencebackupalerts
```
Create a new instant silence on the backup restore alerts:
```shell
$ pipenv run python axonops.py silence --create --silencebackuprestorealerts
```
Create a new instant silence on the audit alerts:
```shell
$ pipenv run python axonops.py silence --create --silenceauditalerts
```
Create a new instant silence on the adaptive repair alerts:
```shell
$ pipenv run python axonops.py silence --create --silenceadaptiverepairalerts
```
Create a new instant silence on the generic alerts:
```shell
$ pipenv run python axonops.py silence --create --silencegenericalerts
```
Create a new instant silence on the generic task alerts:
```shell
$ pipenv run python axonops.py silence --create --silencegenerictaskalerts
```
Create a new instant silence on the log alerts:
```shell
$ pipenv run python axonops.py silence --create --silencelogalerts
```
Create a new instant silence on the node alerts:
```shell
$ pipenv run python axonops.py silence --create --silencenodealerts
```
Create a new instant silence on the repair alerts:
```shell
$ pipenv run python axonops.py silence --create --silencerepairalerts
```
Create a new instant silence on the rolling restart alerts:
```shell
$ pipenv run python axonops.py silence --create --silencerollingrestartalerts
```
Create a new instant silence on the scheduled reports alerts:
```shell
$ pipenv run python axonops.py silence --create --silencescheduledreportsalerts
```
Create a new silence with a duration of 1 hour to a specific datacenter, rack and node:
```shell
$ pipenv run python axonops.py silence --create --dcs '[{"Name": "dc2","Racks": [{"Name": "rack1","Nodes": ["a107315b-2cc1-4650-8363-386460421bcd"]}]}]'
```
