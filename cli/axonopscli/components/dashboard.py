import json


class Dashboard:
    dashboardtemplate_url = "/api/v1/dashboardtemplate"

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args
        self.full_dashboard_url = f"{self.dashboardtemplate_url}/{args.org}/cassandra/{args.cluster}?dashver=2.0"
        self.dashboard_data = None

    def get_actual_dashboards(self):
        """ Get all dashboards from AxonOps. """
        if self.args.v:
            print("Getting all dashboards")

        response = self.axonops.do_request(
            url=self.full_dashboard_url,
            method='GET',
        )
        if not response:
            if self.args.v:
                print("No response received when checking for existing dashboards")
            return []
        elif 'dashboards' in response and response['dashboards']:
            if self.args.v:
                print(f"Found {len(response['dashboards'])} dashboards")
            self.dashboard_data = response['dashboards']
            return response['dashboards']
        else:
            if self.args.v:
                print("No dashboards found")
            return []

    def list_dashboards(self):
        """ List all dashboards in AxonOps. """
        dashboards = self.dashboard_data
        if dashboards:
            print("Dashboards in AxonOps:")
            for dashboard in dashboards:
                print(f"- {dashboard['name']}")
        else:
            print("No dashboards found in AxonOps.")

    def export_dashboard(self, path: str, dashboard_name: str | None = None):
        """ Export a specific dashboard from AxonOps, or all of them if no name is given. """
        dashboards = self.dashboard_data
        if not dashboards:
            print("No dashboards data available to export.")
            return
        if dashboard_name:
            for dashboard in dashboards:
                if dashboard['name'] == dashboard_name:
                    self._dowload_dashboard(dashboard, path, dashboard_name)
                    break
        else:
            for dashboard in dashboards:
                dashboard_name = dashboard['name']
                self._dowload_dashboard(dashboard, path, dashboard_name)

    def _dowload_dashboard(self, dashboard: dict, path: str, dashboard_name: str):
        """ Download a specific dashboard to a file. """
        filename = f"{path}/{dashboard_name}_dashboard.json"
        with open(filename, 'w') as f:
            json.dump(dashboard, f, indent=4)
        print(f"Exported dashboard '{dashboard_name}' to file '{filename}'")

    def import_dashboard(self, file_path: str, dashboard_name: str | None = None, position: int | None = None,
                         overwrite: bool = False):
        """ Import a specific dashboard to AxonOps. If no name is given, import all dashboards found in the file. """
        old_position = None
        # Load dashboard(s) from the specified file
        with open(file_path, 'r') as f:
            dashboard_data = json.load(f)

        # Determine which dashboards to import
        dashboards_to_import = []
        if dashboard_name:
            if dashboard_data['name'] == dashboard_name:
                dashboards_to_import.append(dashboard_data)
            else:
                print(f"Dashboard '{dashboard_name}' not found in file '{file_path}'.")
                return
        else:
            dashboards_to_import.append(dashboard_data)

        for dashboard in dashboards_to_import:

            # Remove existing dashboard if it exists and overwrite is specified
            existing_dashboards = self.dashboard_data
            for i, existing_dashboard in enumerate(existing_dashboards):
                if existing_dashboard['name'] == dashboard['name']:
                    if overwrite:
                        if self.args.v:
                            print(f"Overwriting existing dashboard '{dashboard['name']}', position {i + 1}")
                        del existing_dashboards[i]
                        old_position = i
                        break
                    else:
                        print(f"Dashboard '{dashboard['name']}' already exists. Use overwrite option to replace it.")
                        return

            if position:
                n = len(self.dashboard_data)
                if position > 0:
                    insert_position = (position - 1) % len(self.dashboard_data)
                else:
                    insert_position = n + position + 1
                # clamp to [0, n] so insert works correctly
                insert_position = max(0, min(insert_position, n))
                if self.args.v:
                    print(f"Inserting dashboard '{dashboard['name']}' at specified position {insert_position + 1}")
            else:
                if old_position is None:
                    insert_position = len(self.dashboard_data)
                else:
                    insert_position = old_position
                if self.args.v:
                    print(f"Inserting dashboard '{dashboard['name']}' at old position {insert_position + 1}")
            # Insert the new dashboard at the specified position

            self.dashboard_data.insert(insert_position, dashboard)

            # Update AxonOps with the new list of dashboards
            update_payload = {
                'type': 'cassandra',
                'dashboards': self.dashboard_data
            }
            response = self.axonops.do_request(
                url=self.full_dashboard_url,
                method='PUT',
                json_data=update_payload,
            )

    def delete_dashboard(self, deletedashboard: str):
        """ Delete a specific dashboard from AxonOps"""
        dashboards = self.dashboard_data
        if not dashboards:
            print("No dashboards data available to delete.")
            return
        if deletedashboard:
            dashboards_to_delete = [d for d in dashboards if d['name'] == deletedashboard]
        else:
            print("No dashboard name provided to delete.")
            return

        for dashboard in dashboards_to_delete:
            self.dashboard_data.remove(dashboard)
            if self.args.v:
                print(f"Deleted dashboard '{dashboard['name']}'")

        # Update AxonOps with the new list of dashboards
        update_payload = {
            'type': 'cassandra',
            'dashboards': self.dashboard_data
        }
        response = self.axonops.do_request(
            url=self.full_dashboard_url,
            method='PUT',
            json_data=update_payload,
        )
