"""
Central registry of the AxonOps API endpoints the exporter reads from.

All paths are relative to the base URL resolved by `AxonOps.dash_url()` and must
start with a leading slash. Cluster-scoped endpoints are completed at request
time with `/{org}/{cluster_type}/{cluster}`.
"""

# Authentication
LOGIN_URL = "/api/login"

# Org and cluster inventory
ORGS_URL = "/api/v1/orgs"
NODES_URL = "/api/v1/nodes"

# Cluster-scoped configuration endpoints
ALERT_RULES_URL = "/api/v1/alert-rules"
DASHBOARD_TEMPLATE_URL = "/api/v1/dashboardtemplate"
INTEGRATIONS_URL = "/api/v1/integrations"
HEALTHCHECKS_URL = "/api/v1/healthchecks"
LOGCOLLECTORS_URL = "/api/v1/logcollectors"
SILENCE_WINDOW_URL = "/api/v1/silenceWindow"
ADAPTIVE_REPAIR_URL = "/api/v1/adaptiveRepair"
# GET returns the running, scheduled and adaptive repairs of the cluster.
# (`/api/v1/cassandrascheduledrepair` only answers POST, to create one.)
REPAIR_URL = "/api/v1/repair"
BACKUP_SCHEDULE_URL = "/api/v1/cassandraScheduleSnapshot"
COMMITLOG_SETTINGS_URL = "/api/v1/cassandraCommitLogsSettings"
AGENT_DISCONNECTION_TOLERANCE_URL = "/api/v1/configs/agentDisconnectionTolerance"

# The configuration areas the exporter knows how to read, in export order.
# name -> (endpoint, query string appended to the cluster-scoped URL)
SECTIONS = {
    "alert_rules": (ALERT_RULES_URL, ""),
    "dashboards": (DASHBOARD_TEMPLATE_URL, "?dashver=2.0"),
    "integrations": (INTEGRATIONS_URL, ""),
    "healthchecks": (HEALTHCHECKS_URL, ""),
    "logcollectors": (LOGCOLLECTORS_URL, ""),
    "silences": (SILENCE_WINDOW_URL, ""),
    "adaptive_repair": (ADAPTIVE_REPAIR_URL, ""),
    "scheduled_repairs": (REPAIR_URL, ""),
    "backups": (BACKUP_SCHEDULE_URL, ""),
    "commitlog_archive": (COMMITLOG_SETTINGS_URL, ""),
    "agent_disconnection_tolerance": (AGENT_DISCONNECTION_TOLERANCE_URL, ""),
}

SECTION_NAMES = list(SECTIONS)


def cluster_url(endpoint: str, org: str, cluster_type: str, cluster: str, query: str = "") -> str:
    """Build a cluster-scoped relative URL for the given endpoint."""
    return f"{endpoint}/{org}/{cluster_type}/{cluster}{query}"
