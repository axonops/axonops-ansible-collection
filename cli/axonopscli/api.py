"""AxonOps API endpoint URL templates. Shared across CLI components."""

ALERT_RULES_URL = "/api/v1/alert-rules/{org}/{cluster_type}/{cluster}"
INTEGRATIONS_URL = "/api/v1/integrations/{org}/{cluster_type}/{cluster}"
# query_range is served at the base URL without org/cluster path segments —
# the org is implicit via base_url (e.g. https://dash.axonops.cloud/{org}).
# Cluster context is carried by label filters inside the promql query itself.
QUERY_RANGE_URL = "/api/v1/query_range"

# Distinct values of a single label for a given metric expression. Path
# includes org and cluster context so the backend can scope the search.
# Query string: ?query=<metric_expr>&regex=<label>=([^:]+).
METRIC_LABEL_VALUES_URL = "/api/v1/metricLabelValues/{org}/{cluster_type}/{cluster}"

# Search log/event records. POST endpoint with a JSON body carrying the
# selector (source / level / message / type / host_id). Query string supplies
# start, end, and limit. Response metadata._count is the total match over
# the window — what we use to tune event-shape rules from observed rate
# instead of skipping them all up front.
EVENTS_SEARCH_URL = "/api/v1/events/{org}/{cluster_type}/{cluster}"
