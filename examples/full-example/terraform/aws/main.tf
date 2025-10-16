locals {
  name_prefix    = "cassandra-${var.environment}"
  create_ssh_key = var.ssh_public_key == ""

  # Auto-select availability zones if not provided
  availability_zones = length(var.availability_zones) > 0 ? var.availability_zones : slice(data.aws_availability_zones.available.names, 0, 3)

  # Auto-calculate subnet CIDRs if not provided
  subnet_cidrs = length(var.public_subnet_cidrs) > 0 ? var.public_subnet_cidrs : [
    cidrsubnet(var.vpc_cidr, 8, 1),
    cidrsubnet(var.vpc_cidr, 8, 2),
    cidrsubnet(var.vpc_cidr, 8, 3)
  ]
}

# Get available AZs in the region
data "aws_availability_zones" "available" {
  state = "available"
}

# Get latest Ubuntu 22.04 AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Generate SSH key for instances (only if no existing key provided)
resource "tls_private_key" "ssh" {
  count = local.create_ssh_key ? 1 : 0

  algorithm = "RSA"
  rsa_bits  = 4096
}

# Save private key locally (only if generated)
resource "local_file" "ssh_private_key" {
  count = local.create_ssh_key ? 1 : 0

  content         = tls_private_key.ssh[0].private_key_pem
  filename        = "${path.module}/ssh_key"
  file_permission = "0600"
}

# Create AWS key pair
resource "aws_key_pair" "cassandra" {
  key_name   = "${local.name_prefix}-key"
  public_key = local.create_ssh_key ? tls_private_key.ssh[0].public_key_openssh : var.ssh_public_key

  tags = {
    Name        = "${local.name_prefix}-key"
    Environment = var.environment
  }
}

# VPC
resource "aws_vpc" "cassandra" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${local.name_prefix}-vpc"
    Environment = var.environment
  }
}

# Internet Gateway
resource "aws_internet_gateway" "cassandra" {
  vpc_id = aws_vpc.cassandra.id

  tags = {
    Name        = "${local.name_prefix}-igw"
    Environment = var.environment
  }
}

# Public subnets (one per AZ)
resource "aws_subnet" "public" {
  count = 3

  vpc_id                  = aws_vpc.cassandra.id
  cidr_block              = local.subnet_cidrs[count.index]
  availability_zone       = local.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name        = "${local.name_prefix}-subnet-${count.index + 1}"
    Environment = var.environment
  }
}

# Route table for public subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.cassandra.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.cassandra.id
  }

  tags = {
    Name        = "${local.name_prefix}-rt"
    Environment = var.environment
  }
}

# Associate route table with subnets
resource "aws_route_table_association" "public" {
  count = 3

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Security group for Cassandra cluster
resource "aws_security_group" "cassandra" {
  name        = "${local.name_prefix}-sg"
  description = "Security group for Cassandra cluster"
  vpc_id      = aws_vpc.cassandra.id

  # SSH access
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Cassandra CQL port
  ingress {
    description = "Cassandra CQL"
    from_port   = 9042
    to_port     = 9042
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  # Cassandra inter-node communication (gossip)
  ingress {
    description = "Cassandra gossip"
    from_port   = 7000
    to_port     = 7000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Cassandra SSL inter-node communication
  ingress {
    description = "Cassandra SSL gossip"
    from_port   = 7001
    to_port     = 7001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # JMX port
  ingress {
    description = "JMX"
    from_port   = 7199
    to_port     = 7199
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  # ICMP for ping
  ingress {
    description = "ICMP"
    from_port   = -1
    to_port     = -1
    protocol    = "icmp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow all outbound traffic
  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${local.name_prefix}-sg"
    Environment = var.environment
  }
}

# Placement group for spreading instances
resource "aws_placement_group" "cassandra" {
  name     = "${local.name_prefix}-placement"
  strategy = "spread"

  tags = {
    Name        = "${local.name_prefix}-placement"
    Environment = var.environment
  }
}

# EBS volumes for Cassandra data
resource "aws_ebs_volume" "cassandra" {
  count = 3

  availability_zone = local.availability_zones[count.index]
  size              = var.disk_size
  type              = "gp3"
  iops              = 3000
  throughput        = 125

  tags = {
    Name        = "${local.name_prefix}-volume-${count.index + 1}"
    Environment = var.environment
    NodeNumber  = count.index + 1
  }
}

# Cassandra EC2 instances
resource "aws_instance" "cassandra" {
  count = 3

  ami                    = var.ami_id != "" ? var.ami_id : data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[count.index].id
  vpc_security_group_ids = [aws_security_group.cassandra.id]
  key_name               = aws_key_pair.cassandra.key_name
  placement_group        = aws_placement_group.cassandra.id

  root_block_device {
    volume_size           = var.root_volume_size
    volume_type           = "gp3"
    delete_on_termination = true
  }

  tags = {
    Name        = "${local.name_prefix}-node-${count.index + 1}"
    Environment = var.environment
    Role        = "cassandra"
    NodeNumber  = count.index + 1
  }

  lifecycle {
    ignore_changes = [user_data]
  }
}

# Attach EBS volumes to instances
resource "aws_volume_attachment" "cassandra" {
  count = 3

  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.cassandra[count.index].id
  instance_id = aws_instance.cassandra[count.index].id
}
