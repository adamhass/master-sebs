resource "aws_security_group" "cluster" {
  name        = "${local.name_prefix}-cluster-sg"
  description = "Boki cluster security group"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "SSH admin access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description = "Gateway HTTP"
    from_port   = var.gateway_http_port
    to_port     = var.gateway_http_port
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description = "Gateway gRPC"
    from_port   = var.gateway_grpc_port
    to_port     = var.gateway_grpc_port
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description = "ZooKeeper"
    from_port   = var.zookeeper_port
    to_port     = var.zookeeper_port
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "All traffic inside cluster SG"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    description = "Allow all egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-cluster-sg"
  }
}
