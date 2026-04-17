resource "aws_security_group" "cluster" {
  name        = "${local.name_prefix}-cluster-sg"
  description = "Restate server + client cluster security group"
  vpc_id      = aws_vpc.this.id

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
    description = "SSH access"
  }

  # Restate ingress (HTTP API)
  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
    description = "Restate ingress API"
  }

  # Restate admin
  ingress {
    from_port   = 9070
    to_port     = 9070
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
    description = "Restate admin API"
  }

  # Restate handler (standalone HTTP server)
  ingress {
    from_port   = 9080
    to_port     = 9080
    protocol    = "tcp"
    self        = true
    description = "Restate handler endpoint"
  }

  # Restate fabric (inter-node cluster communication)
  ingress {
    from_port   = 5122
    to_port     = 5122
    protocol    = "tcp"
    self        = true
    description = "Restate fabric (inter-node)"
  }

  # Intra-cluster
  ingress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true
    description = "Intra-cluster traffic"
  }

  # All egress
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-cluster-sg"
  }
}
