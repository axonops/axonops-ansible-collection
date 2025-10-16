# VPC ID
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.cassandra.id
}

# Subnet IDs
output "subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

# Security Group ID
output "security_group_id" {
  description = "ID of the security group"
  value       = aws_security_group.cassandra.id
}

# Node IP addresses
output "node_ips" {
  description = "Public IP addresses of Cassandra nodes"
  value = {
    for idx, instance in aws_instance.cassandra :
    "node-${idx + 1}" => instance.public_ip
  }
}

# Node private IPs
output "node_private_ips" {
  description = "Private IP addresses of Cassandra nodes"
  value = {
    for idx, instance in aws_instance.cassandra :
    "node-${idx + 1}" => instance.private_ip
  }
}

# Node instance IDs
output "node_instance_ids" {
  description = "EC2 instance IDs of Cassandra nodes"
  value = {
    for idx, instance in aws_instance.cassandra :
    "node-${idx + 1}" => instance.id
  }
}

# SSH connection info
output "ssh_connection" {
  description = "SSH connection command for each node"
  value = {
    for idx, instance in aws_instance.cassandra :
    "node-${idx + 1}" => local.create_ssh_key ? "ssh -i ssh_key ubuntu@${instance.public_ip}" : "ssh ubuntu@${instance.public_ip}"
  }
}

# Private key location (only if generated)
output "ssh_key_path" {
  description = "Path to the generated SSH private key (only if auto-generated)"
  value       = local.create_ssh_key ? local_file.ssh_private_key[0].filename : "Using existing SSH public key"
}

# Seed nodes (first 2 nodes)
output "seed_nodes" {
  description = "Private IP addresses to use as Cassandra seeds (first 2 nodes)"
  value       = join(",", slice(aws_instance.cassandra[*].private_ip, 0, 2))
}

# Ansible inventory snippet
output "ansible_inventory" {
  description = "Ansible inventory snippet for the cluster"
  value       = <<-EOT
[${var.environment}]
${join("\n", [for idx, instance in aws_instance.cassandra : "${instance.public_ip} cassandra_rack=rack${(idx % 3) + 1} ansible_hostname=cassandra-node-${idx + 1} private_ip=${instance.private_ip}"])}

[cassandra:children]
${var.environment}

[all:vars]
ansible_user=ubuntu
${local.create_ssh_key ? "ansible_ssh_private_key_file=${local_file.ssh_private_key[0].filename}" : "# Using existing SSH key"}
  EOT
}

# AWS Region
output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

# Availability Zones
output "availability_zones" {
  description = "Availability zones used for the deployment"
  value       = local.availability_zones
}
