## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | ~> 3.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | 3.34.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_ecr_repository.repository](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecr_repository) | resource |
| [aws_ecr_repository_policy.policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecr_repository_policy) | resource |
| [aws_ecs_cluster.cluster](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_cluster) | resource |
| [aws_ecs_service.service](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_service) | resource |
| [aws_ecs_task_definition.task](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_task_definition) | resource |
| [aws_iam_access_key.publisher](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_access_key) | resource |
| [aws_iam_role.fargate](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.fargate](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_user.publisher](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_user) | resource |
| [aws_iam_user_policy.publisher](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_user_policy) | resource |
| [aws_lb.alb](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb) | resource |
| [aws_lb_listener.front_end](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_listener) | resource |
| [aws_lb_target_group.group](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_target_group) | resource |
| [aws_subnet.subnets](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet) | data source |
| [aws_subnet_ids.subnets](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet_ids) | data source |
| [aws_vpc.vpc](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/vpc) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_aws_region"></a> [aws\_region](#input\_aws\_region) | AWS region | `string` | `"eu-west-3"` | no |
| <a name="input_container"></a> [container](#input\_container) | Container configuration to deploy | `any` | `{}` | no |
| <a name="input_ecr_values"></a> [ecr\_values](#input\_ecr\_values) | AWS ECR configuration | `any` | `{}` | no |
| <a name="input_ecs_values"></a> [ecs\_values](#input\_ecs\_values) | AWS ECS configuration | `any` | `{}` | no |
| <a name="input_lb_values"></a> [lb\_values](#input\_lb\_values) | AWS Load Balancer configuration | `any` | `{}` | no |
| <a name="input_vpc"></a> [vpc](#input\_vpc) | AWS VPC configuration | `any` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_app_url"></a> [app\_url](#output\_app\_url) | The public ALB DNS |
| <a name="output_aws_region"></a> [aws\_region](#output\_aws\_region) | The AWS region used |
| <a name="output_container_name"></a> [container\_name](#output\_container\_name) | Container name for the ECS task |
| <a name="output_ecr_repository_name"></a> [ecr\_repository\_name](#output\_ecr\_repository\_name) | The ECR repository name |
| <a name="output_ecr_url"></a> [ecr\_url](#output\_ecr\_url) | The ECR repository URL |
| <a name="output_ecs_cluster"></a> [ecs\_cluster](#output\_ecs\_cluster) | The ECS cluster name |
| <a name="output_ecs_service"></a> [ecs\_service](#output\_ecs\_service) | The ECS service name |
| <a name="output_publisher_access_key"></a> [publisher\_access\_key](#output\_publisher\_access\_key) | AWS\_ACCESS\_KEY to publish to ECR |
| <a name="output_publisher_secret_key"></a> [publisher\_secret\_key](#output\_publisher\_secret\_key) | AWS\_SECRET\_ACCESS\_KEY to upload to the ECR |
