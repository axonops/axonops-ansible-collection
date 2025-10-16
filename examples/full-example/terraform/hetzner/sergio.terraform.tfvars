# Hetzner Cloud Cassandra Cluster Configuration
# Copy this file to terraform.tfvars and customize as needed

# Environment name (used in resource naming)
environment = "prod"

# Hetzner Cloud location
# Options: nbg1 (Nuremberg), fsn1 (Falkenstein), hel1 (Helsinki), ash (Ashburn), hil (Hillsboro)
location = "hel1"

# Server type (affects CPU, RAM, and pricing)
# Small:   cx22 (2 vCPU, 4GB RAM)   - Testing only
# Medium:  cx32 (4 vCPU, 8GB RAM)   - Dev/small workloads
# Large:   cx42 (8 vCPU, 16GB RAM)  - Production
# XLarge:  cx52 (16 vCPU, 32GB RAM) - Heavy workloads
# Dedicated CPU options: ccx13, ccx23, ccx33 (better performance)
server_type = "cpx31"

# Data volume size in GB (for Cassandra data)
# Minimum: 10GB, Maximum: 10000GB
disk_size = 10

# OS Image
# image = "rocky-linux-9"

# CIDR blocks allowed to access CQL port (9042) and JMX port (7199)
# Use ["0.0.0.0/0", "::/0"] to allow from anywhere (not recommended for production)
# Use ["YOUR_IP/32"] to restrict to your IP only
allowed_cidrs = ["83.37.234.212/32"]

# SSH keys to use for servers
# Leave empty [] to auto-generate a new SSH key pair
# Or provide existing SSH key names from your Hetzner Cloud project
# Example: ssh_keys = ["my-laptop-key", "backup-key"]
ssh_keys = [
    "sergio"
]
