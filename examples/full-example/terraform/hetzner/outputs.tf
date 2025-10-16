# Node IP addresses
output "node_ips" {
  description = "Public IP addresses of Cassandra nodes"
  value = {
    for idx, server in hcloud_server.cassandra :
    "node-${idx + 1}" => server.ipv4_address
  }
}

# Node names
output "node_names" {
  description = "Names of Cassandra nodes"
  value       = hcloud_server.cassandra[*].name
}

# SSH connection info
output "ssh_connection" {
  description = "SSH connection command for each node"
  value = {
    for idx, server in hcloud_server.cassandra :
    "node-${idx + 1}" => local.create_ssh_key ? "ssh -i ssh_key root@${server.ipv4_address}" : "ssh root@${server.ipv4_address}"
  }
}

# Private key location (only if generated)
output "ssh_key_path" {
  description = "Path to the generated SSH private key (only if auto-generated)"
  value       = local.create_ssh_key ? local_file.ssh_private_key[0].filename : "Using existing SSH keys: ${join(", ", var.ssh_keys)}"
}

# Seed nodes (first 2 nodes)
output "seed_nodes" {
  description = "IP addresses to use as Cassandra seeds (first 2 nodes)"
  value       = join(",", slice(hcloud_server.cassandra[*].ipv4_address, 0, 2))
}

# Ansible inventory snippet
output "ansible_inventory" {
  description = "Ansible inventory snippet for the cluster"
  value       = <<-EOT
[${var.environment}]
${join("\n", [for idx, server in hcloud_server.cassandra : "${server.ipv4_address} cassandra_rack=rack1 ansible_hostname=cassandra-node-${idx + 1}"])}

[cassandra:children]
${var.environment}

[all:vars]
ansible_user=root
${local.create_ssh_key ? "ansible_ssh_private_key_file=${local_file.ssh_private_key[0].filename}" : "# Using existing SSH keys configured in Hetzner"}
  EOT
}
