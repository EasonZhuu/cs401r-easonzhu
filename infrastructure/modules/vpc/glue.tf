resource "aws_security_group" "glue" {
  name        = "${local.name_prefix}-glue-sg"
  description = "Private communication between Glue Spark workers"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "Allow all TCP between members of this security group"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    self        = true
  }

  egress {
    description = "Allow outbound AWS service access through the private route"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-glue-sg"
  }
}
