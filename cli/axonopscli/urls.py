"""
Central registry of AxonOps API endpoints.

All paths are relative to the base URL resolved by `AxonOps.dash_url()` and must
start with a leading slash. Components build their full URL by appending the
org / cluster-type / cluster segments to one of these constants.
"""

# Authentication
LOGIN_URL = "/api/login"

# Org and cluster inventory
ORGS_URL = "/api/v1/orgs"
NODES_URL = "/api/v1/nodes"
INTEGRATIONS_URL = "/api/v1/integrations"

# Repairs
ADAPTIVE_REPAIR_URL = "/api/v1/adaptiveRepair"
ADD_REPAIR_URL = "/api/v1/addrepair"
REPAIR_URL = "/api/v1/repair"
CASSANDRA_SCHEDULED_REPAIR_URL = "/api/v1/cassandrascheduledrepair"

# Dashboards and alerting
DASHBOARD_TEMPLATE_URL = "/api/v1/dashboardtemplate"
SILENCE_WINDOW_URL = "/api/v1/silenceWindow"
