variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "location" {
  description = "Hetzner Cloud location (e.g., nbg1, fsn1, hel1, ash, hil)"
  type        = string
  default     = "hel1"
}

variable "server_type" {
  description = "Hetzner Cloud server type (e.g., cx22, cx32, cx42, ccx13, ccx23, ccx33)"
  type        = string
  default     = "cx32"
}

variable "disk_size" {
  description = "Size of data volume in GB per node"
  type        = number
  default     = 100
}

variable "image" {
  description = "OS image to use"
  type        = string
  default     = "ubuntu-24.04"
}

variable "allowed_cidrs" {
  description = "CIDR blocks allowed to access CQL and JMX ports"
  type        = list(string)
  default     = ["0.0.0.0/0", "::/0"]
}

variable "ssh_keys" {
  description = "List of existing SSH key names in Hetzner Cloud to attach to servers. Leave empty to auto-generate a new SSH key."
  type        = list(string)
  default     = []
}
