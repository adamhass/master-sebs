data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name_prefix = var.project_name
  azs         = slice(data.aws_availability_zones.available.names, 0, length(var.public_subnet_cidrs))

  metalog_replicas = var.controller_metalog_replicas > 0 ? var.controller_metalog_replicas : var.sequencer_instance_count
  userlog_replicas = var.controller_userlog_replicas > 0 ? var.controller_userlog_replicas : var.storage_instance_count
  index_replicas   = var.controller_index_replicas > 0 ? var.controller_index_replicas : var.engine_instance_count
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
