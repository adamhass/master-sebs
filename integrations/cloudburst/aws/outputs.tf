output "vpc_id" {
  value       = aws_vpc.this.id
  description = "VPC ID."
}

output "public_subnet_ids" {
  value       = [for s in aws_subnet.public : s.id]
  description = "Public subnet IDs."
}

output "scheduler_public_ip" {
  value       = aws_instance.scheduler.public_ip
  description = "Scheduler public IP."
}

output "scheduler_private_ip" {
  value       = aws_instance.scheduler.private_ip
  description = "Scheduler private IP."
}

output "client_public_ip" {
  value       = aws_instance.client.public_ip
  description = "Benchmark client public IP."
}

output "anna_private_ips" {
  value       = [for n in aws_instance.anna : n.private_ip]
  description = "Anna node private IPs."
}

output "executor_asg_name" {
  value       = aws_autoscaling_group.executors.name
  description = "Executor Auto Scaling Group name."
}
