from .components.nodes import Nodes

class Info:

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args

    def print_info(self):
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
        if self.args.v:
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

        print("Info from server:")
        nodes = Nodes(self.axonops, self.args)
        print(nodes)
