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
        print(f"Dashboard URL: {self.axonops.dash_url()}")

        print("Info from server:")
        nodes = Nodes(self.axonops, self.args)
        print(nodes)


