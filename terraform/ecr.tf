resource "aws_ecr_repository" "repository" {
  name                 = local.ecr["repository_name"]
  image_tag_mutability = "MUTABLE"
}


