locals {
  region = var.aws_region
  ecr_defaults = {
    repository_name = "app-repo"
  }
  ecr = merge(local.ecr_defaults, var.ecr_values)

  ecs_defaults = {
    cluster_name = "cluster"
    service_name = "service"
  }
  ecs = merge(local.ecs_defaults, var.ecs_values)

  

  vpc_defaults = {
    id = ""
  }
  vpc             = merge(local.vpc_defaults, var.vpc)
  use_default_vpc = local.vpc.id == ""

  container_defaults = {
    name  = "application"
    image = "particule/helloworld"
    ports = [80]
  }
  container = merge(local.container_defaults, var.container)
}
