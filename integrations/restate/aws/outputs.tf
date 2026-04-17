output "vpc_id" {
  value       = aws_vpc.this.id
  description = "VPC ID."
}

output "server_public_ips" {
  value       = [for s in aws_instance.server : s.public_ip]
  description = "Restate server public IPs (SSH + API access)."
}

output "server_private_ips" {
  value       = [for s in aws_instance.server : s.private_ip]
  description = "Restate server private IPs (for cluster + benchmark client)."
}

output "ingress_url" {
  value       = "http://${aws_instance.server[0].public_ip}:8080"
  description = "Restate ingress URL via node 0 (POST /serviceName/key/handler)."
}

output "admin_url" {
  value       = "http://${aws_instance.server[0].public_ip}:9070"
  description = "Restate admin URL via node 0 (deployment registration)."
}

output "lambda_function_arn" {
  value       = aws_lambda_function.handler.arn
  description = "Restate handler Lambda ARN."
}

output "invoke_role_arn" {
  value       = aws_iam_role.restate_invoke.arn
  description = "IAM role ARN for Restate to invoke Lambda."
}

output "client_public_ip" {
  value       = var.deploy_client ? aws_instance.client[0].public_ip : null
  description = "Benchmark client public IP (SSH access)."
}
