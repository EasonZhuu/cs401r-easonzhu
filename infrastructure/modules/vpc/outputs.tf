output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.this.id
}

output "public_subnet_id" {
  description = "ID of the public subnet"
  value       = aws_subnet.public.id
}

output "private_subnet_id" {
  description = "ID of the private subnet"
  value       = aws_subnet.private.id
}

output "security_group_id" {
  description = "ID of the SageMaker security group"
  value       = aws_security_group.sagemaker.id
}

output "glue_security_group_id" {
  description = "ID of the shared SageMaker and Glue worker security group"
  value       = aws_security_group.sagemaker.id
}

output "legacy_glue_security_group_id" {
  description = "Unused earlier Glue group retained until approved teardown"
  value       = aws_security_group.glue.id
}
