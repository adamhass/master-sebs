# ── Restate Server Cluster (multi-node, standalone handler) ──
#
# Node 0: auto-provision=true, runs handler on port 9080
# Nodes 1+: join via node 0's private IP

resource "aws_instance" "server" {
  count                  = var.server_count
  ami                    = data.aws_ami.ubuntu2204.id
  instance_type          = var.server_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null
  private_ip             = cidrhost(var.public_subnet_cidrs[0], 10 + count.index)

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data/server.sh.tftpl", {
    node_index   = count.index
    node_name    = "node-${count.index}"
    cluster_name = "sebs-benchmark"
    auto_provision = count.index == 0
    bootstrap_ip = cidrhost(var.public_subnet_cidrs[0], 10)
    server_count = var.server_count
    handler_py   = file("${path.module}/handler/handler.py")
  })

  tags = {
    Name = "${local.name_prefix}-server-${count.index}"
    Role = "restate-server"
  }
}

# ── Benchmark Client EC2 ──

resource "aws_instance" "client" {
  count                  = var.deploy_client ? 1 : 0
  ami                    = data.aws_ami.ubuntu2204.id
  instance_type          = var.client_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data/client.sh.tftpl", {
    server_private_ip = aws_instance.server[0].private_ip
  })

  tags = {
    Name = "${local.name_prefix}-client"
    Role = "benchmark-client"
  }

  depends_on = [aws_instance.server]
}
