variable "aws_region" {
  type        = string
  default     = "eu-west-3"
  description = "AWS region"
}

variable "ecr_values" {
  type        = any
  default     = {}
  description = "AWS ECR configuration"
}

variable "ecs_values" {
  type        = any
  default     = {}
  description = "AWS ECS configuration"
}


variable "vpc" {
  type        = any
  default     = {}
  description = "AWS VPC configuration"
}

variable "container" {
  type        = any
  default     = {}
  description = "Container configuration to deploy"
}
