# ECS Module for Tesseract Relayer

variable "environment" {}
variable "cluster_name" {}
variable "vpc_id" {}
variable "private_subnets" {}
variable "public_subnets" {}
variable "relayer_image" {}
variable "relayer_cpu" {}
variable "relayer_memory" {}
variable "relayer_min_count" {}
variable "relayer_max_count" {}
variable "database_url_secret_arn" {}
variable "secrets_arns" {}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = var.cluster_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}

# Task Execution Role
resource "aws_iam_role" "ecs_execution" {
  name = "tesseract-${var.environment}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "secrets-access"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = var.secrets_arns
    }]
  })
}

# Task Role
resource "aws_iam_role" "ecs_task" {
  name = "tesseract-${var.environment}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "relayer" {
  name              = "/ecs/tesseract-${var.environment}-relayer"
  retention_in_days = 30
}

# Task Definition
resource "aws_ecs_task_definition" "relayer" {
  family                   = "tesseract-${var.environment}-relayer"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.relayer_cpu
  memory                   = var.relayer_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "relayer"
    image = var.relayer_image

    portMappings = [
      {
        containerPort = 8080
        protocol      = "tcp"
      },
      {
        containerPort = 9090
        protocol      = "tcp"
      }
    ]

    environment = [
      {
        name  = "RUST_LOG"
        value = "info,tesseract_relayer=debug"
      },
      {
        name  = "TESSERACT_CONFIG"
        value = "/app/config/production.toml"
      }
    ]

    secrets = [
      {
        name      = "DATABASE_URL"
        valueFrom = var.database_url_secret_arn
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.relayer.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "relayer"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

data "aws_region" "current" {}

# Security Group
resource "aws_security_group" "relayer" {
  name        = "tesseract-${var.environment}-relayer"
  description = "Security group for Tesseract relayer"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    from_port       = 9090
    to_port         = 9090
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "tesseract-${var.environment}-relayer"
  }
}

# ALB Security Group
resource "aws_security_group" "alb" {
  name        = "tesseract-${var.environment}-alb"
  description = "Security group for ALB"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "tesseract-${var.environment}-alb"
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "tesseract-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnets

  enable_deletion_protection = var.environment == "production"
}

resource "aws_lb_target_group" "api" {
  name        = "tesseract-${var.environment}-api"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# ECS Service
resource "aws_ecs_service" "relayer" {
  name            = "tesseract-${var.environment}-relayer"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.relayer.arn
  desired_count   = var.relayer_min_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnets
    security_groups  = [aws_security_group.relayer.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "relayer"
    container_port   = 8080
  }

  lifecycle {
    ignore_changes = [desired_count]
  }
}

# Auto Scaling
resource "aws_appautoscaling_target" "relayer" {
  max_capacity       = var.relayer_max_count
  min_capacity       = var.relayer_min_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.relayer.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "relayer_cpu" {
  name               = "tesseract-${var.environment}-relayer-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.relayer.resource_id
  scalable_dimension = aws_appautoscaling_target.relayer.scalable_dimension
  service_namespace  = aws_appautoscaling_target.relayer.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# Outputs
output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "relayer_service_name" {
  value = aws_ecs_service.relayer.name
}

output "relayer_security_group_id" {
  value = aws_security_group.relayer.id
}

output "api_endpoint" {
  value = "http://${aws_lb.main.dns_name}"
}
