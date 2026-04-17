variable "project_name" {
  type        = string
  description = "Name prefix for all resources."
  default     = "master-sebs-restate"
}

variable "aws_region" {
  type        = string
  description = "AWS region for deployment."
  default     = "eu-north-1"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block."
  default     = "10.70.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs."
  default     = ["10.70.1.0/24", "10.70.2.0/24"]
}

variable "server_instance_type" {
  type        = string
  description = "EC2 instance type for the Restate server."
  default     = "t3.medium"
}

variable "client_instance_type" {
  type        = string
  description = "EC2 instance type for the benchmark client."
  default     = "t3.small"
}

variable "key_pair_name" {
  type        = string
  description = "EC2 key pair name for SSH access."
  default     = ""
}

variable "admin_cidr" {
  type        = string
  description = "CIDR allowed for SSH and Restate admin ingress."
  default     = "0.0.0.0/0"
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Lambda timeout for Restate handler."
  default     = 30
}

variable "lambda_memory_mb" {
  type        = number
  description = "Lambda memory size (MB) for Restate handler."
  default     = 256
}

variable "server_count" {
  type        = number
  description = "Number of Restate server nodes (3 for replication factor 2)."
  default     = 3
}

variable "deploy_client" {
  type        = bool
  description = "Deploy benchmark client EC2 in the VPC."
  default     = true
}
