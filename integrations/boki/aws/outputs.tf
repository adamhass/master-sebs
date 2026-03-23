output "vpc_id" {
  value       = aws_vpc.this.id
  description = "VPC ID."
}

output "public_subnet_ids" {
  value       = [for s in aws_subnet.public : s.id]
  description = "Public subnet IDs."
}

output "zookeeper_public_ip" {
  value       = aws_instance.zookeeper.public_ip
  description = "ZooKeeper public IP."
}

output "zookeeper_private_ip" {
  value       = aws_instance.zookeeper.private_ip
  description = "ZooKeeper private IP."
}

output "controller_public_ip" {
  value       = aws_instance.controller.public_ip
  description = "Controller public IP."
}

output "gateway_public_ip" {
  value       = aws_instance.gateway.public_ip
  description = "Gateway public IP."
}

output "gateway_private_ip" {
  value       = aws_instance.gateway.private_ip
  description = "Gateway private IP."
}

output "sequencer_private_ips" {
  value       = [for n in aws_instance.sequencer : n.private_ip]
  description = "Sequencer node private IPs."
}

output "storage_private_ips" {
  value       = [for n in aws_instance.storage : n.private_ip]
  description = "Storage node private IPs."
}

output "engine_private_ips" {
  value       = [for n in aws_instance.engine : n.private_ip]
  description = "Engine node private IPs."
}

output "client_public_ip" {
  value       = aws_instance.client.public_ip
  description = "Client node public IP."
}

output "zookeeper_host" {
  value       = "${aws_instance.zookeeper.private_ip}:${var.zookeeper_port}"
  description = "ZooKeeper host:port to use for Boki role commands."
}
