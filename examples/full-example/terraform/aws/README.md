# AWS - 3 Node Cassandra Cluster

This Terraform configuration creates a simple 3-node Cassandra cluster on AWS EC2.

## Prerequisites

1. **AWS Account**: Sign up at [aws.amazon.com](https://aws.amazon.com)
2. **AWS Credentials**: Configure AWS CLI or set environment variables
3. **Terraform**: Install Terraform >= 1.0

## What This Creates

- **VPC**: Dedicated VPC with Internet Gateway
- **3 Public Subnets**: One per availability zone for node distribution
- **3 Cassandra Nodes**: EC2 instances spread across different AZs using placement groups
- **EBS Volumes**: 100GB gp3 volume per node for Cassandra data
- **SSH Key**: Auto-generated and saved locally (or use your own)
- **Security Group**: Configured for Cassandra ports (7000, 7001, 7199, 9042) and SSH
- **Public IPs**: Each node gets a public IPv4 address

## Configuration

### Default Settings

- **Region**: us-east-1
- **Instance Type**: t3.xlarge (4 vCPUs, 16GB RAM)
- **Data Disk Size**: 100GB (gp3 EBS)
- **Root Disk Size**: 20GB
- **OS Image**: Latest Ubuntu 22.04 LTS AMI (auto-selected)

### Customization

Create a `terraform.tfvars` file or pass variables:

```hcl
environment          = "prod"                    # Environment name
aws_region           = "us-east-1"               # AWS region
availability_zones   = []                        # Auto-select 3 AZs if empty
instance_type        = "t3.xlarge"               # EC2 instance type
disk_size            = 100                       # Data volume size in GB
root_volume_size     = 20                        # Root volume size in GB
allowed_cidrs        = ["0.0.0.0/0"]             # IPs allowed to access CQL/JMX
ssh_public_key       = ""                        # Leave empty to auto-generate
vpc_cidr             = "10.0.0.0/16"             # VPC CIDR block
public_subnet_cidrs  = []                        # Auto-calculate if empty
```

## Usage

### 1. Configure AWS Credentials

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

# Option 2: AWS CLI profile
aws configure
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
ssh -i ssh_key ubuntu@<node-ip>

# Get seed nodes for Cassandra config (uses private IPs)
terraform output -raw seed_nodes

# Get Ansible inventory
terraform output -raw ansible_inventory > inventory.ini
```

## Outputs

After deployment, Terraform provides:

- **vpc_id**: ID of the created VPC
- **subnet_ids**: IDs of the public subnets
- **security_group_id**: ID of the security group
- **node_ips**: Public IP addresses of all nodes
- **node_private_ips**: Private IP addresses of all nodes (for inter-node communication)
- **node_instance_ids**: EC2 instance IDs
- **ssh_connection**: Ready-to-use SSH commands
- **ssh_key_path**: Path to generated SSH private key
- **seed_nodes**: Comma-separated private IPs for Cassandra seeds configuration
- **ansible_inventory**: Ready-to-use Ansible inventory snippet
- **aws_region**: Region where resources are deployed
- **availability_zones**: List of AZs used

## SSH Key Management

This configuration supports two SSH key options:

### Option 1: Auto-Generate SSH Key (Default)

Leave `ssh_public_key = ""` in your configuration. Terraform will:
- Generate a new RSA 4096-bit SSH key pair
- Save the private key to `ssh_key` (keep this secure!)
- Create an AWS key pair with the public key
- Attach it to all instances

**Example:**
```hcl
ssh_public_key = ""  # Auto-generate
```

### Option 2: Use Existing SSH Key

If you already have an SSH key pair:

```hcl
ssh_public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQ... your-key-here"
```

**Note:** When using an existing key, you must use your own private key to connect.

## Network Architecture

- **VPC**: Isolated network (default: 10.0.0.0/16)
- **3 Public Subnets**: 10.0.1.0/24, 10.0.2.0/24, 10.0.3.0/24 (auto-calculated)
- **Internet Gateway**: For public internet access
- **Spread Placement Group**: Ensures nodes are on different physical hardware
- **3 Availability Zones**: For high availability

## Security

The security group allows:
- **SSH (22)**: From anywhere (0.0.0.0/0)
- **CQL (9042)**: From IPs in `allowed_cidrs` variable
- **Gossip (7000)**: From anywhere (inter-node communication)
- **SSL Gossip (7001)**: From anywhere (inter-node communication)
- **JMX (7199)**: From IPs in `allowed_cidrs` variable
- **ICMP**: From anywhere (ping)

To restrict CQL and JMX access:

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
ansible-playbook -i terraform/aws/inventory.ini cassandra.yml
```

**Note:** The Ansible inventory uses public IPs for connection but includes `private_ip` variable for Cassandra inter-node communication.

## Cost Estimation

Approximate monthly costs (as of 2025):
- **t3.xlarge (3 nodes)**: ~$335/month (3 × $111.77 on-demand)
- **100GB gp3 volumes (3×)**: ~$24/month (3 × $8.00)
- **Data transfer**: Variable based on usage
- **Total**: ~$359/month (on-demand pricing)

**Cost Optimization:**
- Use Reserved Instances or Savings Plans for ~40% savings
- Consider t3a instances for ~10% additional savings
- Use Spot Instances for non-production (up to 70% savings)

Check current pricing at [AWS EC2 Pricing](https://aws.amazon.com/ec2/pricing/)

## Instance Types

Recommended instance types for Cassandra:

| Instance Type | vCPUs | RAM   | Network      | Use Case                |
|---------------|-------|-------|--------------|-------------------------|
| t3.xlarge     | 4     | 16GB  | Up to 5 Gbps | Development/Small       |
| t3.2xlarge    | 8     | 32GB  | Up to 5 Gbps | Small Production        |
| m5.xlarge     | 4     | 16GB  | Up to 10 Gbps| Balanced Workloads      |
| m5.2xlarge    | 8     | 32GB  | Up to 10 Gbps| Balanced Production     |
| r5.xlarge     | 4     | 32GB  | Up to 10 Gbps| Memory-Intensive        |
| r5.2xlarge    | 8     | 64GB  | Up to 10 Gbps| Large Memory Workloads  |
| i3.xlarge     | 4     | 30.5GB| Up to 10 Gbps| High I/O (NVMe)         |

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

**Warning**: This will permanently delete all instances, volumes, VPC, and data!

## Files Generated

- `ssh_key`: Private SSH key (keep secure!)
- `ssh_key.pub`: Public SSH key
- `terraform.tfstate`: Terraform state (keep secure!)
- `.terraform/`: Terraform working directory

## Important Notes

- **AMI Selection**: Auto-selects latest Ubuntu 22.04 LTS from Canonical
- **EBS Volumes**: Attached as `/dev/sdf` (appears as `/dev/nvme1n1` on instance)
- **Placement Group**: Spread strategy ensures nodes are on different hardware
- **Private IPs**: Used for inter-node Cassandra communication
- **Public IPs**: Used for external access and Ansible connection
- **Default User**: Ubuntu 22.04 uses `ubuntu` user (not `root`)

## Availability Zones

The configuration automatically:
1. Queries available AZs in your selected region
2. Selects the first 3 available AZs
3. Creates one subnet per AZ
4. Places one Cassandra node in each AZ

You can override by setting `availability_zones` variable:

```hcl
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
```

## Troubleshooting

### "Error creating placement group"
Spread placement groups have capacity limits. Terraform will retry automatically. If it persists, try a different region or instance type.

### Cannot connect via SSH
1. Check security group allows your IP
2. Verify SSH key permissions: `chmod 600 ssh_key`
3. Ensure instance is in "running" state
4. Check public IP is assigned

### EBS volume not attached
Check volume status:
```bash
ssh -i ssh_key ubuntu@<node-ip> "lsblk"
```

The data volume should appear as `/dev/nvme1n1` (not `/dev/sdf` as specified in Terraform).

### "No default VPC available"
This is normal. The configuration creates its own VPC.

### AMI not found
If auto-selection fails, manually specify an AMI:
```hcl
ami_id = "ami-0c55b159cbfafe1f0"  # Ubuntu 22.04 LTS in us-east-1
```

## Next Steps

After deployment:
1. Configure Cassandra using the Ansible playbooks
2. Set up proper monitoring with AxonOps
3. Configure backups (consider AWS Backup)
4. Adjust JVM settings for your workload
5. Set up SSL/TLS for client connections
6. Consider using private subnets with NAT Gateway for production
7. Implement AWS Secrets Manager for credentials
8. Set up CloudWatch monitoring and alarms

## Advanced Configuration

### Using Specific AZs

```hcl
availability_zones = ["us-west-2a", "us-west-2b", "us-west-2c"]
```

### Custom Subnet CIDRs

```hcl
public_subnet_cidrs = ["10.0.10.0/24", "10.0.20.0/24", "10.0.30.0/24"]
```

### Restricting Access

```hcl
allowed_cidrs = ["203.0.113.0/24", "198.51.100.0/24"]
```

### Using a Specific AMI

```hcl
ami_id = "ami-0c55b159cbfafe1f0"
```

## Production Considerations

For production deployments, consider:

1. **Private Subnets**: Deploy Cassandra nodes in private subnets with NAT Gateway
2. **Bastion Host**: Use a bastion/jump host for SSH access
3. **EBS Encryption**: Enable encryption at rest for data volumes
4. **CloudWatch**: Set up monitoring and alerting
5. **Backup Strategy**: Implement automated backups
6. **IAM Roles**: Use instance roles for AWS service access
7. **Reserved Instances**: Commit to 1-3 year terms for cost savings
8. **Multi-Region**: Consider multi-region deployment for disaster recovery
9. **Auto Scaling**: Implement auto-scaling for dynamic workloads (advanced)
10. **VPC Peering**: Set up VPC peering for multi-VPC architectures
