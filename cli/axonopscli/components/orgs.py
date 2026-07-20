from ..urls import ORGS_URL


class Orgs:

    # Cluster health as reported by the orgs tree
    status_labels = {
        0: "OK",
        1: "Warning",
        2: "Error",
    }

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args
        self.full_url = ORGS_URL
        self.orgs_data = None

    def get_orgs(self):
        if self.orgs_data is None:
            if self.args.v:
                print("Getting orgs with URL:", self.full_url)

            response = self.axonops.do_request(
                url=self.full_url,
                method='GET',
            )
            if self.args.v:
                print("Response orgs:", response)
            if response:
                self.orgs_data = response
            else:
                print("No orgs found")
        return self.orgs_data

    def get_clusters(self):
        """
        Flatten the orgs tree (org -> type -> cluster) into a list of
        (org, cluster_type, cluster_name, status) tuples.
        """
        orgs = self.get_orgs()
        if not orgs:
            return []

        clusters = []
        for org in orgs.get('children') or []:
            for cluster_type in org.get('children') or []:
                for cluster in cluster_type.get('children') or []:
                    clusters.append((
                        org.get('name'),
                        cluster.get('type', cluster_type.get('name')),
                        cluster.get('name'),
                        cluster.get('status'),
                    ))
        return clusters

    def status_label(self, status) -> str:
        return self.status_labels.get(status, "Unknown")

    def __str__(self) -> str:
        clusters = self.get_clusters()
        if not clusters:
            return "No clusters found"

        result = "Clusters:\n"
        for org, cluster_type, name, status in clusters:
            label = self.status_label(status)
            health = "healthy" if status == 0 else f"NOT healthy ({label})"
            result += f"- {org}/{cluster_type}/{name}: {health}\n"

        unhealthy = [c for c in clusters if c[3] != 0]
        if unhealthy:
            result += "\nNon-OK clusters:\n"
            for _, cluster_type, name, status in unhealthy:
                result += f"{cluster_type}/{name}: {self.status_label(status)}\n"
        else:
            result += "\nAll clusters are healthy\n"

        return result
