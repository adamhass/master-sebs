resource "aws_instance" "zookeeper" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.zookeeper_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  user_data = templatefile("${path.module}/user_data/zookeeper.sh.tftpl", {
    zookeeper_port = var.zookeeper_port
  })

  tags = {
    Name = "${local.name_prefix}-zookeeper"
    Role = "zookeeper"
  }
}

resource "aws_instance" "controller" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.controller_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  user_data = templatefile("${path.module}/user_data/controller.sh.tftpl", {
    boki_repo_url     = var.boki_repo_url
    boki_repo_ref     = var.boki_repo_ref
    zookeeper_host    = "${aws_instance.zookeeper.private_ip}:${var.zookeeper_port}"
    zookeeper_root    = var.zookeeper_root_path
    metalog_replicas  = local.metalog_replicas
    userlog_replicas  = local.userlog_replicas
    index_replicas    = local.index_replicas
    num_phylogs       = var.num_phylogs
    enable_auto_build = var.enable_auto_build
    enable_auto_start = var.enable_auto_start
  })

  depends_on = [aws_instance.zookeeper]

  tags = {
    Name = "${local.name_prefix}-controller"
    Role = "controller"
  }
}

resource "aws_instance" "sequencer" {
  count                  = var.sequencer_instance_count
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.sequencer_instance_type
  subnet_id              = aws_subnet.public[count.index % length(aws_subnet.public)].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  user_data = templatefile("${path.module}/user_data/sequencer.sh.tftpl", {
    boki_repo_url     = var.boki_repo_url
    boki_repo_ref     = var.boki_repo_ref
    zookeeper_host    = "${aws_instance.zookeeper.private_ip}:${var.zookeeper_port}"
    zookeeper_root    = var.zookeeper_root_path
    listen_addr       = "0.0.0.0"
    node_id           = var.sequencer_node_id_start + count.index
    enable_auto_build = var.enable_auto_build
    enable_auto_start = var.enable_auto_start
  })

  depends_on = [aws_instance.zookeeper]

  tags = {
    Name = "${local.name_prefix}-sequencer-${count.index + 1}"
    Role = "sequencer"
  }
}

resource "aws_instance" "storage" {
  count                  = var.storage_instance_count
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.storage_instance_type
  subnet_id              = aws_subnet.public[count.index % length(aws_subnet.public)].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  user_data = templatefile("${path.module}/user_data/storage.sh.tftpl", {
    boki_repo_url     = var.boki_repo_url
    boki_repo_ref     = var.boki_repo_ref
    zookeeper_host    = "${aws_instance.zookeeper.private_ip}:${var.zookeeper_port}"
    zookeeper_root    = var.zookeeper_root_path
    listen_addr       = "0.0.0.0"
    node_id           = var.storage_node_id_start + count.index
    db_path           = "/opt/boki/data/storage-${var.storage_node_id_start + count.index}"
    enable_auto_build = var.enable_auto_build
    enable_auto_start = var.enable_auto_start
  })

  depends_on = [aws_instance.zookeeper]

  tags = {
    Name = "${local.name_prefix}-storage-${count.index + 1}"
    Role = "storage"
  }
}

resource "aws_instance" "engine" {
  count                  = var.engine_instance_count
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.engine_instance_type
  subnet_id              = aws_subnet.public[count.index % length(aws_subnet.public)].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  user_data = templatefile("${path.module}/user_data/engine.sh.tftpl", {
    boki_repo_url       = var.boki_repo_url
    boki_repo_ref       = var.boki_repo_ref
    zookeeper_host      = "${aws_instance.zookeeper.private_ip}:${var.zookeeper_port}"
    zookeeper_root      = var.zookeeper_root_path
    listen_addr         = "0.0.0.0"
    node_id             = var.engine_node_id_start + count.index
    root_path_for_ipc   = var.root_path_for_ipc
    func_config_path    = var.func_config_path
    func_config_content = var.func_config_content
    enable_auto_build   = var.enable_auto_build
    enable_auto_start   = var.enable_auto_start
  })

  depends_on = [aws_instance.zookeeper]

  tags = {
    Name = "${local.name_prefix}-engine-${count.index + 1}"
    Role = "engine"
  }
}

resource "aws_instance" "gateway" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.gateway_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  user_data = templatefile("${path.module}/user_data/gateway.sh.tftpl", {
    boki_repo_url       = var.boki_repo_url
    boki_repo_ref       = var.boki_repo_ref
    zookeeper_host      = "${aws_instance.zookeeper.private_ip}:${var.zookeeper_port}"
    zookeeper_root      = var.zookeeper_root_path
    listen_addr         = "0.0.0.0"
    gateway_http_port   = var.gateway_http_port
    gateway_grpc_port   = var.gateway_grpc_port
    func_config_path    = var.func_config_path
    func_config_content = var.func_config_content
    enable_auto_build   = var.enable_auto_build
    enable_auto_start   = var.enable_auto_start
  })

  depends_on = [aws_instance.zookeeper]

  tags = {
    Name = "${local.name_prefix}-gateway"
    Role = "gateway"
  }
}

resource "aws_instance" "client" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.client_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  user_data = templatefile("${path.module}/user_data/client.sh.tftpl", {
    boki_repo_url      = var.boki_repo_url
    boki_repo_ref      = var.boki_repo_ref
    gateway_private_ip = aws_instance.gateway.private_ip
    gateway_public_ip  = aws_instance.gateway.public_ip
    gateway_http_port  = var.gateway_http_port
    gateway_grpc_port  = var.gateway_grpc_port
  })

  depends_on = [aws_instance.gateway]

  tags = {
    Name = "${local.name_prefix}-client"
    Role = "client"
  }
}
