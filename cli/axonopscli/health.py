from .components.nodes import Nodes
from .components.orgs import Orgs


class Health:

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args

    def print_settings(self):
        """ Connection and authentication settings, printed with -v only. """
        print("Info from settings:")
        print(f"Organization: {self.args.org}")
        print(f"Cluster: {self.args.cluster}")
        print(f"Cluster Type: {self.axonops.get_cluster_type()}")
        print()

        if self.args.url:
            print(f"A custom url has been specified: {self.args.url}.")
            print("This is usually done for AxonOps Self-Hosted.")
        else:
            print("No URL specified, the connection will be made to AxonOps Cloud")
        print(f"Dashboard URL: {self.axonops.dash_url()}")
        print()

        if self.args.token:
            if len(self.args.token) != 40:
                print("An AxonOps was specified but it doesn't look like a valid token. Please check your settings and try again.")
            print("Token: " + self.args.token[0] + '*' * (len(self.args.token) - 1))
            print("This is usually used in AxonOps Cloud")
        elif self.args.password or self.args.username:
            if not self.args.password:
                print("No password specified. Please check your settings and try again.")
            if not self.args.username:
                print("No username specified. Please check your settings and try again.")
            print("Username: " + self.args.username)
            print("This is usually used in AxonOps Self-Hosted with LDAP set.")
        else:
            print("No authentication specified. This is usually used in AxonOps Self-Hosted with no LDAP set.")
        print()

    def print_health(self) -> bool:
        """
        Print the health of every cluster the org can see.

        Returns True when every cluster reports OK, False otherwise.
        """
        if self.args.v:
            self.print_settings()

        orgs = Orgs(self.axonops, self.args)
        clusters = orgs.get_clusters()

        if not clusters:
            print("No clusters found")
            return True

        unhealthy = orgs.get_unhealthy_clusters()
        if unhealthy:
            print("Unhealthy clusters:")
            for _, cluster_type, name, status in unhealthy:
                print(f"{cluster_type}/{name}: {orgs.status_label(status)}")
        else:
            print("All clusters are healthy")

        if getattr(self.args, 'show_healthy', False):
            healthy = orgs.get_healthy_clusters()
            print()
            if healthy:
                print("Healthy clusters:")
                for org, cluster_type, name, _ in healthy:
                    print(f"- {org}/{cluster_type}/{name}")
            else:
                print("No healthy clusters")

            print()
            print(Nodes(self.axonops, self.args))

        if getattr(self.args, 'show_orgs', False):
            print()
            org_names = orgs.get_org_names()
            if org_names:
                print("Orgs:")
                for name in org_names:
                    print(f"- {name}")
            else:
                print("No orgs found")

        return not unhealthy
