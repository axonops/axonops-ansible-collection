"""Discovery of the clusters an AxonOps environment knows about."""

from typing import List, NamedTuple, Optional

from .axonops import AxonOps
from .urls import ORGS_URL


class Cluster(NamedTuple):
    """One cluster to export, as named by the orgs tree."""

    org: str
    cluster_type: str
    name: str


def discover_clusters(axonops: AxonOps, org: Optional[str] = None) -> List[Cluster]:
    """Flatten the orgs tree (org -> type -> cluster) into a list of clusters.

    Every cluster carries the type the API reports for it, so an org holding both
    Cassandra and Kafka clusters is exported with the right type for each.
    `org` narrows the result down to a single organisation.
    """
    tree = axonops.do_request(ORGS_URL) or {}

    clusters = []
    for org_node in tree.get('children') or []:
        org_name = org_node.get('name')
        if org and org_name != org:
            continue

        for type_node in org_node.get('children') or []:
            for cluster_node in type_node.get('children') or []:
                node_type = cluster_node.get('type') or type_node.get('name')
                clusters.append(Cluster(org_name, node_type, cluster_node.get('name')))

    return clusters
