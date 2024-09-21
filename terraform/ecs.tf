resource "aws_ecs_cluster" "cluster" {
  name = local.ecs["cluster_name"]


}
resource "aws_ecs_cluster_capacity_providers" "cp" {
  cluster_name = aws_ecs_cluster.cluster.name

  capacity_providers = ["FARGATE"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}

resource "aws_ecs_task_definition" "task" {
  family = "service"
  
 
  container_definitions = jsonencode([
    {
      name      = local.container.name
      image     = local.container.image
      cpu                = 256
      memory             = 512
      essential = true
      portMappings = [
       for port in local.container.ports :
       {
          containerPort = port
          hostPort      = port
       }
      ]      
    }
  ])
  depends_on = [aws_ecr_repository.repository]
}

resource "aws_ecs_service" "service" {
  name            = local.ecs.service_name
  cluster         = aws_ecs_cluster.cluster.arn
  task_definition = aws_ecs_task_definition.task.arn
  desired_count   = 1

  network_configuration {
    subnets          = [for s in data.aws_subnets.subnets.ids : s]
    assign_public_ip = true
  }

  
  deployment_controller {
    type = "ECS"
  }
  capacity_provider_strategy {
    base              = 0
    capacity_provider = "FARGATE"
    weight            = 100
  }
}
