"""AxonOps API endpoint URL templates. Shared across CLI components."""

ALERT_RULES_URL = "/api/v1/alert-rules/{org}/{cluster_type}/{cluster}"
INTEGRATIONS_URL = "/api/v1/integrations/{org}/{cluster_type}/{cluster}"
# query_range is served at the base URL without org/cluster path segments —
# the org is implicit via base_url (e.g. https://dash.axonops.cloud/{org}).
# Cluster context is carried by label filters inside the promql query itself.
QUERY_RANGE_URL = "/api/v1/query_range"
