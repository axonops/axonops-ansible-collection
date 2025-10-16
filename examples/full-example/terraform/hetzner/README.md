# Hetzner Cloud - 3 Node Cassandra Cluster

This Terraform configuration creates a simple 3-node Cassandra cluster on Hetzner Cloud.

## Prerequisites

1. **Hetzner Cloud Account**: Sign up at [hetzner.com](https://www.hetzner.com/cloud)
2. **API Token**: Generate an API token from your Hetzner Cloud Console
3. **Terraform**: Install Terraform >= 1.0

## What This Creates

- **3 Cassandra Nodes**: Deployed across different physical hosts using placement groups
- **Data Volumes**: 100GB additional volume per node for Cassandra data
- **SSH Key**: Auto-generated and saved locally
- **Firewall**: Configured for Cassandra ports (7000, 7001, 7199, 9042) and SSH
- **Public IPs**: Each node gets a public IPv4 address

## Configuration

### Default Settings

- **Location**: Helsinki (hel1)
- **Server Type**: cx32 (4 vCPUs, 8GB RAM)
- **Disk Size**: 100GB per node
- **OS Image**: Ubuntu 22.04

### Customization

Edit [terraform.tfvars](terraform.tfvars) or pass variables:

```hcl
environment   = "prod"           # Environment name
location      = "hel1"           # hetzner location (nbg1, fsn1, hel1, ash)
server_type   = "cx32"           # Server size
disk_size     = 100              # Data volume size in GB
allowed_cidrs = ["0.0.0.0/0"]    # IPs allowed to access CQL/JMX
ssh_keys      = []               # Leave empty to auto-generate, or provide existing SSH key names
```

## Usage

### 1. Set API Token

```bash
export HCLOUD_TOKEN="your-hetzner-api-token"
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Plan Deployment

```bash
terraform plan
```

### 4. Deploy Cluster

```bash
terraform apply
```

### 5. Get Connection Info

```bash
# Show all outputs
terraform output

# SSH to a node
terraform output -raw ssh_key_path  # Shows path to SSH key
ssh -i ssh_key root@<node-ip>

# Get seed nodes for Cassandra config
terraform output -raw seed_nodes

# Get Ansible inventory
terraform output -raw ansible_inventory > inventory.ini
```

## Outputs

After deployment, Terraform provides:

- **node_ips**: Public IP addresses of all nodes
- **node_names**: Server names in Hetzner
- **ssh_connection**: Ready-to-use SSH commands
- **ssh_key_path**: Path to generated SSH private key
- **seed_nodes**: Comma-separated IPs for Cassandra seeds configuration
- **ansible_inventory**: Ready-to-use Ansible inventory snippet

## SSH Key Management

This configuration supports two SSH key options:

### Option 1: Auto-Generate SSH Key (Default)

Leave `ssh_keys = []` in your configuration. Terraform will:
- Generate a new RSA 4096-bit SSH key pair
- Save the private key to `ssh_key` (keep this secure!)
- Upload the public key to Hetzner Cloud
- Attach it to all nodes

**Example:**
```hcl
ssh_keys = []  # Auto-generate
```

### Option 2: Use Existing SSH Keys

If you already have SSH keys in your Hetzner Cloud project:

1. List your existing SSH keys in Hetzner Cloud Console
2. Add their names to the `ssh_keys` variable:

```hcl
ssh_keys = ["my-laptop-key", "backup-key"]
```

**Note:** When using existing keys, no new SSH key will be generated, and you must use your own private keys to connect.

## Network Security

The firewall allows:
- **SSH (22)**: From anywhere (0.0.0.0/0)
- **CQL (9042)**: From IPs in `allowed_cidrs` variable
- **Gossip (7000)**: From anywhere (inter-node communication)
- **SSL Gossip (7001)**: From anywhere (inter-node communication)
- **JMX (7199)**: From IPs in `allowed_cidrs` variable
- **ICMP**: From anywhere (ping)

To restrict CQL and JMX access, set `allowed_cidrs`:

```bash
terraform apply -var='allowed_cidrs=["YOUR_IP/32"]'
```

## Using with Ansible

After deployment, use the Ansible playbooks in the parent directory:

```bash
# Get the inventory
terraform output -raw ansible_inventory > inventory.ini

# Run Ansible playbook
cd ../../
ansible-playbook -i terraform/hetzner/inventory.ini cassandra.yml
```

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

**Warning**: This will permanently delete all servers and volumes!

## Cost Estimation

Approximate monthly costs (as of 2024):
- **cx32 (3 nodes)**: ~€32/month (3 × €10.60)
- **100GB volumes (3×)**: ~€15/month (3 × €5.04)
- **Total**: ~€47/month

Check current pricing at [Hetzner Cloud Pricing](https://www.hetzner.com/cloud#pricing)

## Files Generated

- `ssh_key`: Private SSH key (keep secure!)
- `ssh_key.pub`: Public SSH key
- `terraform.tfstate`: Terraform state (keep secure!)

## Notes

- The placement group ensures nodes are spread across different physical hosts for better availability
- Volumes are automatically mounted to `/mnt/HC_Volume_<id>`
- Default Ubuntu 22.04 image includes latest security updates
- SSH key is RSA 4096-bit for better security

## Troubleshooting

### "Error creating server: placement group is full"
The spread placement group can only hold a limited number of servers. This is normal - Terraform will retry automatically.

### Cannot connect via SSH
Ensure your firewall/ISP isn't blocking port 22, and that the SSH key permissions are correct:
```bash
chmod 600 ssh_key
```

### Volume not mounted
Check volume status:
```bash
ssh -i ssh_key root@<node-ip> "lsblk"
```

## Next Steps

After deployment:
1. Configure Cassandra using the Ansible playbooks
2. Set up proper monitoring with AxonOps
3. Configure backups
4. Adjust JVM settings for your workload
5. Set up SSL/TLS for client connections
