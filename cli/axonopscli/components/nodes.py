_cached_data = None

class Nodes:
    node_url = "/api/v1/nodes"

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args
        self.full_url = f"{self.node_url}/{self.args.org}/cassandra/{self.args.cluster}"

        self.get_nodes()

    def get_nodes(self):
        global _cached_data
        if _cached_data is None:

            if self.args.v:
                print("Getting nodes with URL:", self.full_url)

            response = self.axonops.do_request(
                url=self.full_url,
                method='GET',
            )
            if self.args.v:
                print("Response node:", response)
            if response:
                _cached_data = response
            else:
                print("No nodes found")
        return _cached_data

    def print_by_id(self, node_id):
        for node in self.get_nodes():
            if node['host_id'] == node_id:
                if 'Details' in node and node['Details'] and 'human_readable_identifier' in node['Details']:
                    return node['Details']['human_readable_identifier']
                elif 'HostIP' in node:
                    return node['HostIP']
                else:
                    return node_id
        return node_id

    def __str__(self) -> str:
        if self.get_nodes():
            result = "Nodes:\n"
            for node in self.get_nodes():
                if 'Details' in node and node['Details'] and 'human_readable_identifier' in node['Details']:
                    result += f"- {node['Details']['human_readable_identifier']} (ID: {node['host_id']})\n"
                elif 'HostIP' in node:
                    result += f"- {node['HostIP']} (ID: {node['host_id']})\n"
                else:
                    result += f"- {node['host_id']}\n"
            return result
        else:
            return "No nodes found"
