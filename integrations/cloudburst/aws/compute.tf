resource "aws_instance" "anna" {
  count                  = var.anna_instance_count
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.anna_instance_type
  subnet_id              = aws_subnet.public[count.index % length(aws_subnet.public)].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  user_data = templatefile("${path.module}/user_data/anna.sh.tftpl", {
    cloudburst_repo_url = var.cloudburst_repo_url
    cloudburst_repo_ref = var.cloudburst_repo_ref
    enable_auto_start   = var.enable_auto_start
  })

  tags = {
    Name = "${local.name_prefix}-anna-${count.index + 1}"
    Role = "anna"
  }
}

resource "aws_instance" "scheduler" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.scheduler_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  user_data = templatefile("${path.module}/user_data/scheduler.sh.tftpl", {
    cloudburst_repo_url = var.cloudburst_repo_url
    cloudburst_repo_ref = var.cloudburst_repo_ref
    anna_ip             = aws_instance.anna[0].private_ip
    scheduler_ip        = "127.0.0.1"
    enable_auto_start   = var.enable_auto_start
  })

  tags = {
    Name = "${local.name_prefix}-scheduler"
    Role = "scheduler"
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
    cloudburst_repo_url = var.cloudburst_repo_url
    cloudburst_repo_ref = var.cloudburst_repo_ref
    scheduler_ip        = aws_instance.scheduler.private_ip
  })

  tags = {
    Name = "${local.name_prefix}-client"
    Role = "client"
  }
}

resource "aws_launch_template" "executor" {
  name_prefix   = "${local.name_prefix}-executor-"
  image_id      = data.aws_ami.al2023.id
  instance_type = var.executor_instance_type
  key_name      = var.key_pair_name != "" ? var.key_pair_name : null

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2.name
  }

  network_interfaces {
    security_groups             = [aws_security_group.cluster.id]
    associate_public_ip_address = true
  }

  user_data = base64encode(templatefile("${path.module}/user_data/executor.sh.tftpl", {
    cloudburst_repo_url = var.cloudburst_repo_url
    cloudburst_repo_ref = var.cloudburst_repo_ref
    scheduler_ip        = aws_instance.scheduler.private_ip
    anna_ip             = aws_instance.anna[0].private_ip
    enable_auto_start   = var.enable_auto_start
  }))

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${local.name_prefix}-executor"
      Role = "executor"
    }
  }
}

resource "aws_autoscaling_group" "executors" {
  name                = "${local.name_prefix}-executors"
  min_size            = var.executor_min_size
  desired_capacity    = var.executor_desired_capacity
  max_size            = var.executor_max_size
  vpc_zone_identifier = [for s in aws_subnet.public : s.id]
  health_check_type   = "EC2"

  launch_template {
    id      = aws_launch_template.executor.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${local.name_prefix}-executor-asg"
    propagate_at_launch = true
  }
}
