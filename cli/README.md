# AxonOps CLI

This CLI is designed to extend the AxonOps Configuration Automation Ansible module.

## Installation

This CLI uses the same Python environment as the Ansible module and does not require any additional configuration.

### Export Environment Variables

This CLI accepts both command-line parameters and environment variables, just like the Ansible module.

## Using of CLI

### Global Options

All commands accept those attributes

* `--org` Name of your organisation.
* `--cluster` Name of your cluster.
* `--token` AUTH_TOKEN used to authenticate with the API in AxonOps Cloud.
* `--username` Username used for AxonOps Self-Hosted when authentication is enabled.
* `--password` Password used for AxonOps Self-Hosted when authentication is enabled.
* `--url` Specify the AxonOps URL if not using the AxonOps Cloud environment.

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
* `--scheduleexpr` Cron Expression for Scheduled Repair. If not set, Scheduled Repair will run immediately.
* `--segmented` Enables Segmented Repair.
* `--segmentspernode` Number of Segments Per Token Range (only applicable if `--segmented` is set).
* `--incremental` Enables Incremental Repair. If not set, a full repair will be performed.
* `--jobthreads` Number of Job Threads to use for the repair process. If not set, the default value of 1 will be used.
* `--partitionerrange` Repair Partitioner Range Only.
* `--parallelism` Repair Parallelism. Accepted values are `sequential`, `parallel`, and `dc_parallel`. If not set, the
  default value of `sequential` will be used.
* `--optimisestreams` Optimize Streams during repair (require Cassandra 4.1+).
* `--datacenters` Comma-separated list of datacenters to include in the repair. If not set, all datacenters will be
  included.
* `--tags` Tags to associate with the scheduled repair job. Tags are used to identify repair jobs in AxonOps.
  This parameter accepts a string value.
* `--paxosonly` Run paxos repair only. Default is false.
* `--skippaxos` Skip paxos repair. Default is false.
* `--delete` Delete Scheduled Repair. This option needs to be paired with a tags value to identify which scheduled
  repair job to disable.

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