variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region to deploy resources (e.g., us-east-1, us-west-2, eu-west-1)"
  type        = string
  default     = "us-east-1"
}

variable "availability_zones" {
  description = "List of availability zones to spread nodes across. Leave empty to auto-select based on region."
  type        = list(string)
  default     = []
}

variable "instance_type" {
  description = "EC2 instance type (e.g., t3.large, t3.xlarge, m5.large, m5.xlarge, r5.large)"
  type        = string
  default     = "t3.xlarge"
}

variable "disk_size" {
  description = "Size of data volume in GB per node (EBS volume)"
  type        = number
  default     = 100
}

variable "root_volume_size" {
  description = "Size of root volume in GB"
  type        = number
  default     = 20
}

variable "ami_id" {
  description = "AMI ID to use. Leave empty to auto-select latest Ubuntu 22.04 AMI"
  type        = string
  default     = ""
}

variable "allowed_cidrs" {
  description = "CIDR blocks allowed to access CQL and JMX ports"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "ssh_public_key" {
  description = "SSH public key content to add to instances. Leave empty to auto-generate a new SSH key."
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (one per AZ). Leave empty to auto-calculate."
  type        = list(string)
  default     = []
}
