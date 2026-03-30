variable "project_name" {
  type        = string
  description = "Name prefix for all resources."
  default     = "master-sebs-boki"
}

variable "aws_region" {
  type        = string
  description = "AWS region for deployment."
  default     = "eu-north-1"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block."
  default     = "10.40.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs (at least two recommended)."
  default     = ["10.40.1.0/24", "10.40.2.0/24"]
}

variable "admin_cidr" {
  type        = string
  description = "CIDR allowed for SSH and gateway ingress."
  default     = "0.0.0.0/0"
}

variable "key_pair_name" {
  type        = string
  description = "Optional EC2 key pair name for SSH access."
  default     = ""
}

variable "zookeeper_port" {
  type        = number
  description = "ZooKeeper client port."
  default     = 2181
}

variable "zookeeper_root_path" {
  type        = string
  description = "ZooKeeper root path for Boki metadata."
  default     = "/faas"
}

variable "gateway_http_port" {
  type        = number
  description = "Gateway HTTP port."
  default     = 8080
}

variable "gateway_grpc_port" {
  type        = number
  description = "Gateway gRPC port."
  default     = 50051
}

variable "num_phylogs" {
  type        = number
  description = "Number of physical logs for controller config."
  default     = 1
}

variable "controller_metalog_replicas" {
  type        = number
  description = "Controller metalog replicas. Set 0 to auto-derive from sequencer count."
  default     = 0
}

variable "controller_userlog_replicas" {
  type        = number
  description = "Controller userlog replicas. Set 0 to auto-derive from storage count."
  default     = 0
}

variable "controller_index_replicas" {
  type        = number
  description = "Controller index replicas. Set 0 to auto-derive from engine count."
  default     = 0
}

variable "zookeeper_instance_type" {
  type        = string
  description = "EC2 instance type for ZooKeeper node."
  default     = "t3.small"
}

variable "controller_instance_type" {
  type        = string
  description = "EC2 instance type for Boki controller node."
  default     = "t3.medium"
}

variable "sequencer_instance_count" {
  type        = number
  description = "Number of sequencer nodes."
  default     = 1
}

variable "sequencer_instance_type" {
  type        = string
  description = "EC2 instance type for Boki sequencer nodes."
  default     = "t3.medium"
}

variable "sequencer_node_id_start" {
  type        = number
  description = "Starting node ID for sequencer instances."
  default     = 101
}

variable "storage_instance_count" {
  type        = number
  description = "Number of storage nodes."
  default     = 1
}

variable "storage_instance_type" {
  type        = string
  description = "EC2 instance type for Boki storage nodes."
  default     = "t3.medium"
}

variable "storage_node_id_start" {
  type        = number
  description = "Starting node ID for storage instances."
  default     = 201
}

variable "engine_instance_count" {
  type        = number
  description = "Number of engine nodes."
  default     = 1
}

variable "engine_instance_type" {
  type        = string
  description = "EC2 instance type for Boki engine nodes."
  default     = "t3.large"
}

variable "engine_node_id_start" {
  type        = number
  description = "Starting node ID for engine instances."
  default     = 301
}

variable "gateway_instance_type" {
  type        = string
  description = "EC2 instance type for Boki gateway node."
  default     = "t3.medium"
}

variable "client_instance_type" {
  type        = string
  description = "EC2 instance type for client/driver node."
  default     = "t3.small"
}

variable "boki_repo_url" {
  type        = string
  description = "Boki source repository URL."
  default     = "https://github.com/GeorgZs/master-boki.git"
}

variable "boki_repo_ref" {
  type        = string
  description = "Git branch/tag/commit to checkout."
  default     = "master"
}

variable "root_path_for_ipc" {
  type        = string
  description = "Root path for engine IPC sockets/shared memory."
  default     = "/dev/shm/faas_ipc"
}

variable "enable_auto_build" {
  type        = bool
  description = "If true, user-data runs build_deps.sh and make during boot."
  default     = false
}

variable "enable_auto_start" {
  type        = bool
  description = "If true, user-data starts the role process automatically after bootstrap."
  default     = false
}

variable "func_config_path" {
  type        = string
  description = "Path on instance where function config file should be written."
  default     = "/opt/boki/func_config.json"
}

variable "func_config_content" {
  type        = string
  description = "Optional function config JSON content to write on engine/gateway nodes."
  default     = ""
}
