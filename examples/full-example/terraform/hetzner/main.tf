locals {
  name_prefix    = "cassandra-${var.environment}"
  create_ssh_key = length(var.ssh_keys) == 0

  # Determine which SSH keys to use
  ssh_key_ids = local.create_ssh_key ? [hcloud_ssh_key.cassandra[0].id] : [for key in data.hcloud_ssh_key.existing : key.id]
}

# Generate SSH key for instances (only if no existing keys provided)
resource "tls_private_key" "ssh" {
  count = local.create_ssh_key ? 1 : 0

  algorithm = "RSA"
  rsa_bits  = 4096
}

# Create SSH key in Hetzner (only if no existing keys provided)
resource "hcloud_ssh_key" "cassandra" {
  count = local.create_ssh_key ? 1 : 0

  name       = "${local.name_prefix}-key"
  public_key = tls_private_key.ssh[0].public_key_openssh
}

# Save private key locally (only if generated)
resource "local_file" "ssh_private_key" {
  count = local.create_ssh_key ? 1 : 0

  content         = tls_private_key.ssh[0].private_key_pem
  filename        = "${path.module}/ssh_key"
  file_permission = "0600"
}

# Data source to get existing SSH keys if provided
data "hcloud_ssh_key" "existing" {
  for_each = toset(var.ssh_keys)
  name     = each.value
}

# Initial firewall for Cassandra cluster (without inter-node rules)
resource "hcloud_firewall" "cassandra" {
  name = "${local.name_prefix}-firewall"

  # SSH access - restricted to allowed CIDRs
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.allowed_cidrs
  }

  # Cassandra CQL port
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "9042"
    source_ips = var.allowed_cidrs
  }

  # JMX port
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "7199"
    source_ips = var.allowed_cidrs
  }

  # ICMP for ping
  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

# Placement group to spread nodes across physical hosts
resource "hcloud_placement_group" "cassandra" {
  name = "${local.name_prefix}-placement"
  type = "spread"
}

# Data volume for each Cassandra node
resource "hcloud_volume" "cassandra" {
  count = 3

  name     = "${local.name_prefix}-volume-${count.index + 1}"
  size     = var.disk_size
  location = var.location
  format   = "ext4"
}

# Cassandra cluster nodes
resource "hcloud_server" "cassandra" {
  count = 3

  name               = "${local.name_prefix}-node-${count.index + 1}"
  server_type        = var.server_type
  location           = var.location
  image              = var.image
  ssh_keys           = local.ssh_key_ids
  firewall_ids       = [hcloud_firewall.cassandra.id]
  placement_group_id = hcloud_placement_group.cassandra.id

  public_net {
    ipv4_enabled = true
    ipv6_enabled = false
  }

  labels = {
    role        = "cassandra"
    environment = var.environment
    node_number = count.index + 1
  }

  lifecycle {
    ignore_changes = [user_data]
  }
}

# Attach volumes to nodes
resource "hcloud_volume_attachment" "cassandra" {
  count = 3

  volume_id = hcloud_volume.cassandra[count.index].id
  server_id = hcloud_server.cassandra[count.index].id
  automount = true
}

# Additional firewall for inter-node communication (created after servers)
resource "hcloud_firewall" "cassandra_internode" {
  name = "${local.name_prefix}-internode-firewall"

  # Cassandra inter-node communication (gossip) - only between cluster nodes
  dynamic "rule" {
    for_each = hcloud_server.cassandra
    content {
      direction  = "in"
      protocol   = "tcp"
      port       = "7000"
      source_ips = ["${rule.value.ipv4_address}/32"]
    }
  }

  # Cassandra SSL inter-node communication - only between cluster nodes
  dynamic "rule" {
    for_each = hcloud_server.cassandra
    content {
      direction  = "in"
      protocol   = "tcp"
      port       = "7001"
      source_ips = ["${rule.value.ipv4_address}/32"]
    }
  }
}

# Attach inter-node firewall to servers
resource "hcloud_firewall_attachment" "cassandra_internode" {
  firewall_id = hcloud_firewall.cassandra_internode.id
  server_ids  = [for server in hcloud_server.cassandra : server.id]
}
