variable "project_name" {
  type        = string
  description = "Name prefix for all resources."
  default     = "master-sebs-cloudburst"
}

variable "aws_region" {
  type        = string
  description = "AWS region for deployment."
  default     = "eu-north-1"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block."
  default     = "10.30.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs (at least two recommended)."
  default     = ["10.30.1.0/24", "10.30.2.0/24"]
}

variable "admin_cidr" {
  type        = string
  description = "CIDR allowed for SSH access."
  default     = "0.0.0.0/0"
}

variable "key_pair_name" {
  type        = string
  description = "Optional EC2 key pair name for SSH access."
  default     = ""
}

variable "anna_instance_count" {
  type        = number
  description = "Number of Anna nodes."
  default     = 1
}

variable "anna_instance_type" {
  type        = string
  description = "EC2 instance type for Anna nodes."
  default     = "t3.medium"
}

variable "scheduler_instance_type" {
  type        = string
  description = "EC2 instance type for Cloudburst scheduler."
  default     = "t3.medium"
}

variable "client_instance_type" {
  type        = string
  description = "EC2 instance type for benchmark client node."
  default     = "t3.small"
}

variable "executor_instance_type" {
  type        = string
  description = "EC2 instance type for executor ASG."
  default     = "t3.medium"
}

variable "executor_min_size" {
  type        = number
  description = "Executor ASG minimum size."
  default     = 1
}

variable "executor_desired_capacity" {
  type        = number
  description = "Executor ASG desired capacity."
  default     = 2
}

variable "executor_max_size" {
  type        = number
  description = "Executor ASG maximum size."
  default     = 4
}

variable "cloudburst_repo_url" {
  type        = string
  description = "Cloudburst source repository URL."
  default     = "https://github.com/GeorgZs/master-cloudburst.git"
}

variable "cloudburst_repo_ref" {
  type        = string
  description = "Git branch/tag/commit to checkout."
  default     = "master"
}

variable "enable_auto_start" {
  type        = bool
  description = "If true, node bootstrap attempts to start role process automatically."
  default     = false
}
