"""Render the exported configuration as AxonOps CLI settings.

Two files are produced next to the exported YAML, in `exports/<org>/`:

* `.env.axonops` — the connection settings, in the shape the CLI expects
  (`source ./.env.axonops`). Secrets are never written: the token and the
  password are left as commented placeholders to fill in by hand.
* `<org>.sh` — the `axonopscli` commands that reproduce the exported
  configuration on another environment.

Only the configuration areas the CLI can set today are turned into commands;
the rest are listed as a TODO comment at the end of the script.
"""

import json
import shlex
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import VERSION
from .clusters import Cluster

# Alert types a silence can cover: payload key -> CLI flag.
SILENCE_ALERT_FLAGS = {
    'MetricsAlerts': '--silencemetricsalerts',
    'ServiceChecksAlerts': '--silenceservicechecksalerts',
    'EventAlerts': '--silenceeventalerts',
    'BackupAlerts': '--silencebackupalerts',
    'BackupRestoreAlerts': '--silencebackuprestorealerts',
    'AuditAlerts': '--silenceauditalerts',
    'AdaptiveRepairAlerts': '--silenceadaptiverepairalerts',
    'GenericAlerts': '--silencegenericalerts',
    'GenericTaskAlerts': '--silencegenerictaskalerts',
    'LogAlerts': '--silencelogalerts',
    'NodeAlerts': '--silencenodealerts',
    'RepairAlerts': '--silencerepairalerts',
    'RollingRestartAlerts': '--silencerollingrestartalerts',
    'ScheduledReportsAlerts': '--silencescheduledreportsalerts',
}

# Sections the CLI can reproduce, in the order they are written to the script.
SUPPORTED_SECTIONS = ('adaptive_repair', 'scheduled_repairs', 'silences')


def render_env_file(org: str, url: Optional[str] = None, cluster: Optional[str] = None,
                    username: Optional[str] = None) -> str:
    """Render the `.env.axonops` for this environment.

    The token and the password are deliberately left commented out — an export
    never writes a credential to disk.
    """
    lines = [
        "# Connection settings for the AxonOps CLI, written by the AxonOps",
        f"# Configurations Exporter {VERSION}.",
        "#",
        "# Once filled with your details, export the variables with:",
        "# $ source ./.env.axonops",
        "",
        "# export your org",
        "# This is the only mandatory variable value",
        f"export AXONOPS_ORG={shlex.quote(org)}",
        "",
    ]

    if cluster:
        lines += [
            "# export your cluster",
            "# Leave it unset to work on every cluster of the org",
            f"export AXONOPS_CLUSTER={shlex.quote(cluster)}",
            "",
        ]

    lines += [
        "# export your token",
        "# token is used to authenticate in AxonOps Cloud.",
        "# export AXONOPS_TOKEN='aaaabbbbccccddddeeee'",
        "",
        "# export the AxonOps url",
        "# this needs to be specified if you are using AxonOps Self-Hosted.",
    ]
    if url:
        lines.append(f"export AXONOPS_URL={shlex.quote(url)}")
    else:
        lines.append("# export AXONOPS_URL=http://127.0.0.1:3000")
    lines.append("")

    lines += [
        "# export user and password",
        "# this needs to be specified if your authentication method is user and password",
    ]
    if username:
        lines.append(f"export AXONOPS_USERNAME={shlex.quote(username)}")
    else:
        lines.append("# export AXONOPS_USERNAME='my_user'")
    lines += [
        "# export AXONOPS_PASSWORD='I <3 AxonOps!'",
        "",
    ]

    return "\n".join(lines)


def render_script(org: str, exports: Sequence[Tuple[Cluster, Dict[str, Any]]]) -> str:
    """Render the `<org>.sh` reproducing the exported configuration."""
    lines = [
        "#!/usr/bin/env bash",
        f"# AxonOps CLI settings for the org '{org}', written by the AxonOps",
        f"# Configurations Exporter {VERSION}.",
        "#",
        "# The org comes from AXONOPS_ORG, so point the environment at the target",
        "# instance and run the script:",
        "#   source ./.env.axonops",
        f"#   bash {org}.sh",
        "",
        "set -euo pipefail",
        "",
        "# The CLI to drive. Override it to match your checkout, for example:",
        "#   AXONOPS_CLI='python3 /path/to/cli/axonops.py' bash " + f"{org}.sh",
        'AXONOPS_CLI="${AXONOPS_CLI:-python3 axonops.py}"',
        "",
    ]

    missing = set()
    for cluster, configuration in exports:
        lines += [
            f"### cluster {cluster.name} ({cluster.cluster_type})",
            "",
        ]

        for section in SUPPORTED_SECTIONS:
            if section not in configuration:
                continue

            commands = render_section(section, cluster, configuration[section])
            lines.append(f"# {section}")
            lines += commands or [f"# nothing to set for {section}"]
            lines.append("")

        missing.update(name for name in configuration if name not in SUPPORTED_SECTIONS)

    if missing:
        lines += [
            "# TODO: the CLI has no command for these sections yet, so they are only",
            "# available as YAML next to this script:",
        ]
        lines += [f"#   - {name}" for name in sorted(missing)]
        lines.append("")

    return "\n".join(lines)


def render_section(section: str, cluster: Cluster, payload: Any) -> List[str]:
    """Render one exported section as CLI commands."""
    if section == 'adaptive_repair':
        return render_adaptive_repair(cluster, payload)
    if section == 'scheduled_repairs':
        return render_scheduled_repairs(cluster, payload)
    if section == 'silences':
        return render_silences(cluster, payload)
    return []


def render_adaptive_repair(cluster: Cluster, payload: Any) -> List[str]:
    """`repair` command mirroring the adaptive repair settings."""
    if not isinstance(payload, dict):
        return []

    options = ['--enabled' if payload.get('Active') else '--disabled']

    for key, flag in (('GcGraceThreshold', '--gcgrace'),
                      ('TableParallelism', '--tableparallelism'),
                      ('MaxSegmentsPerTable', '--maxsegmentspertable'),
                      ('SegmentRetries', '--segmentretries'),
                      ('SegmentTargetSizeMB', '--segmenttargetsizemb')):
        if payload.get(key) is not None:
            options += [flag, str(payload[key])]

    if payload.get('BlacklistedTables'):
        options += ['--excludedtables', ','.join(payload['BlacklistedTables'])]

    if payload.get('FilterTWCSTables') is not None:
        options += ['--excludetwcstables', str(payload['FilterTWCSTables']).lower()]

    timeout = payload.get('SegmentTimeout')
    if timeout and timeout != '0s':
        options += ['--segmenttimeout', timeout]

    return [command(cluster, 'repair', options)]


def render_scheduled_repairs(cluster: Cluster, payload: Any) -> List[str]:
    """One `scheduledrepair` command per scheduled repair."""
    if not isinstance(payload, dict):
        return []

    commands = []
    for repair in payload.get('ScheduledRepairs') or []:
        params = repair.get('Params') if isinstance(repair, dict) else None
        if isinstance(params, list):
            params = params[0] if params else None
        if not isinstance(params, dict):
            continue

        options: List[str] = []
        for key, flag in (('keyspace', '--keyspace'),
                          ('scheduleExpr', '--scheduleexpr'),
                          ('parallelism', '--parallelism'),
                          ('tag', '--tags')):
            if params.get(key):
                options += [flag, str(params[key])]

        for key, flag in (('tables', '--tables'),
                          ('blacklistedTables', '--excludedtables'),
                          ('nodes', '--nodes'),
                          ('specificDataCenters', '--datacenters')):
            if params.get(key):
                options += [flag, ','.join(str(item) for item in params[key])]

        for key, flag in (('segmentsPerNode', '--segmentspernode'),
                          ('jobThreads', '--jobthreads')):
            if params.get(key) is not None:
                options += [flag, str(params[key])]

        for key, flag in (('segmented', '--segmented'),
                          ('incremental', '--incremental'),
                          ('primaryRange', '--partitionerrange'),
                          ('optimiseStreams', '--optimisestreams'),
                          ('skipPaxos', '--skippaxos'),
                          ('paxosOnly', '--paxosonly')):
            if params.get(key):
                options.append(flag)

        commands.append(command(cluster, 'scheduledrepair', options))

    return commands


def render_silences(cluster: Cluster, payload: Any) -> List[str]:
    """One `silence --create` command per silence window."""
    if not isinstance(payload, list):
        return []

    commands = []
    for silence in payload:
        if not isinstance(silence, dict):
            continue

        options = ['--create']
        if silence.get('Duration'):
            options += ['--duration', str(silence['Duration'])]
        if silence.get('IsRecurring') and silence.get('CronExpr'):
            options += ['--cronexpr', str(silence['CronExpr'])]
        if silence.get('DCs'):
            options += ['--dcs', json.dumps(silence['DCs'])]

        # SilenceAll is what the CLI assumes when no alert type is named.
        if not silence.get('SilenceAll'):
            options += [flag for key, flag in SILENCE_ALERT_FLAGS.items() if silence.get(key)]

        commands.append(command(cluster, 'silence', options))

    return commands


def command(cluster: Cluster, subcommand: str, options: Sequence[str]) -> str:
    """Build one CLI invocation for a cluster, quoted for the shell."""
    argv = ['--cluster', cluster.name, subcommand, *options]
    return '$AXONOPS_CLI ' + ' '.join(shlex.quote(argument) for argument in argv)
