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

### `repair` Subcommand

Manages **Adaptive Repair** in AxonOps.

#### Options:

* `--enabled` Enables AxonOps Adaptive Repair.
* `--disabled` Disable AxonOps Adaptive Repair.
* `--excludedtables` Excluded Tables. This parameter accepts a comma-separated list in the format `keyspace.table1,keyspace.table2`.
* `--excludetwcstables` Exclude TWCS tables.
* `--gcgrace` GG Grace Threshold in Seconds.
* `--segmentretries` Segment Retries.
* `--maxsegmentspertable` Max Segments Per Table.
* `--segmenttargetsizemb` Segment Target Size in MB.
* `--tableparallelism` Concurrent Repair Processes.

#### Examples: 

The following Activating Adaptive Repair examples are for the organisation `test` and the cluster `thingscluster` on AxonOps Cloud.
For self-hosted authentication, refer to the authentication section of the main project.

Authenticate to the cluster: 
```shell
export AXONOPS_ORG='test'
export AXONOPS_CLUSTER="thingscluster"
export AXONOPS_TOKEN='aaaaabbbbccccddddeeee'
```

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
Enable the repair and set the GC Grace Threshold to 86,400 seconds (AxonOps will ignore tables that have a gc_grace_seconds value lower than the specified threshold):
```shell
$ pipenv run python axonops.py repair --enable --gcgrace 86400
```
Enable the repair and set the table parallelism to 100 (number of tables processed in parallel):
```shell
$ pipenv run python axonops.py repair --enable --tableparallelism 100
```
Enable the repair and set the segment retry limit to 10 (number of times a segment can fail before raising an alert and stopping repairs for that cycle):
```shell
$ pipenv run python axonops.py repair --enable --segmentretries 10
```
Enable the repair and set the segment chunk size to 250 MB (amount of data repaired at a time):
```shell
$ pipenv run python axonops.py repair --enable --segmenttargetsizemb 250
```
Exclude specific tables from repair (comma separated list of `keyspace.table`):
```shell
pipenv run python axonops.py repair --enable --excludedtables system_auth.roles,system_auth.role_permissions
```
Set the Maximum Segments Per Table to 131,072:
```shell
pipenv run python axonops.py repair --enable --maxsegmentspertable 131072
```

Set the timeout per Segment to 3 hours:
```shell
pipenv run python axonops.py repair --enable --segmenttimeout 3h
```