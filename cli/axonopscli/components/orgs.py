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

    def get_unhealthy_clusters(self):
        """ Clusters whose status is anything other than 0 (OK). """
        return [cluster for cluster in self.get_clusters() if cluster[3] != 0]

    def get_healthy_clusters(self):
        """ Clusters whose status is 0 (OK). """
        return [cluster for cluster in self.get_clusters() if cluster[3] == 0]

    def get_org_names(self):
        """ Names of every org returned by the API, in the order given. """
        orgs = self.get_orgs()
        if not orgs:
            return []
        return [org.get('name') for org in orgs.get('children') or []]

    def status_label(self, status) -> str:
        return self.status_labels.get(status, "Unknown")
