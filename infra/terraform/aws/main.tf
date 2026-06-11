# OpenBioOps AWS Infrastructure
# Provisions complete infrastructure for running OpenBioOps on AWS EKS

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }

  backend "s3" {
    # Configure backend in backend.tfvars:
    # bucket = "openbioops-terraform-state"
    # key    = "prod/terraform.tfstate"
    # region = "us-west-2"
    # dynamodb_table = "terraform-state-lock"
    # encrypt = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "OpenBioOps"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ── Networking ────────────────────────────────────────────────────────────────

module "vpc" {
  source = "./modules/vpc"

  environment         = var.environment
  vpc_cidr            = var.vpc_cidr
  availability_zones  = var.availability_zones
  enable_nat_gateway  = true
  single_nat_gateway  = var.environment != "production"
}

# ── EKS Cluster ───────────────────────────────────────────────────────────────

module "eks" {
  source = "./modules/eks"

  cluster_name    = "${var.project_name}-${var.environment}"
  cluster_version = var.eks_cluster_version
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnet_ids

  # Node groups
  node_groups = {
    general = {
      desired_size   = var.eks_node_desired_size
      max_size       = var.eks_node_max_size
      min_size       = var.eks_node_min_size
      instance_types = ["t3.large"]
      capacity_type  = "ON_DEMAND"
      labels = {
        workload = "general"
      }
    }

    ml_workloads = {
      desired_size   = 1
      max_size       = 5
      min_size       = 0
      instance_types = ["g4dn.xlarge"]  # GPU instances for ML inference
      capacity_type  = "ON_DEMAND"
      labels = {
        workload = "ml"
      }
      taints = [{
        key    = "workload"
        value  = "ml"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  # Enable cluster logging
  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}

# ── RDS Database ──────────────────────────────────────────────────────────────

module "rds" {
  source = "./modules/rds"

  identifier        = "${var.project_name}-${var.environment}"
  engine            = "postgres"
  engine_version    = "15.3"
  instance_class    = var.rds_instance_class
  allocated_storage = var.rds_allocated_storage

  database_name = "openbioops"
  username      = var.rds_username
  password      = var.rds_password  # Use AWS Secrets Manager in production

  vpc_id         = module.vpc.vpc_id
  subnet_ids     = module.vpc.private_subnet_ids
  allowed_sg_ids = [module.eks.cluster_security_group_id]

  # Backup configuration
  backup_retention_period = var.environment == "production" ? 7 : 1
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  # High availability for production
  multi_az               = var.environment == "production"
  deletion_protection    = var.environment == "production"
  skip_final_snapshot    = var.environment != "production"

  # Performance insights
  performance_insights_enabled = true

  tags = {
    Name = "${var.project_name}-${var.environment}-db"
  }
}

# ── S3 Artifacts Bucket ───────────────────────────────────────────────────────

module "s3_artifacts" {
  source = "./modules/s3"

  bucket_name = "${var.project_name}-${var.environment}-artifacts"
  environment = var.environment

  # Versioning for artifact history
  enable_versioning = true

  # Lifecycle rules to manage costs
  lifecycle_rules = [
    {
      id     = "archive_old_runs"
      status = "Enabled"
      transitions = [
        {
          days          = 90
          storage_class = "GLACIER"
        },
        {
          days          = 180
          storage_class = "DEEP_ARCHIVE"
        }
      ]
      expiration = {
        days = 365
      }
    }
  ]

  # CORS for dashboard access
  cors_rules = [
    {
      allowed_headers = ["*"]
      allowed_methods = ["GET", "HEAD"]
      allowed_origins = ["https://${var.dashboard_domain}"]
      expose_headers  = ["ETag"]
      max_age_seconds = 3600
    }
  ]
}

# ── ElastiCache Redis ─────────────────────────────────────────────────────────

module "redis" {
  source = "./modules/redis"

  cluster_id         = "${var.project_name}-${var.environment}"
  engine_version     = "7.0"
  node_type          = var.redis_node_type
  num_cache_nodes    = var.environment == "production" ? 2 : 1
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnet_ids
  allowed_sg_ids     = [module.eks.cluster_security_group_id]

  # Automatic failover for production
  automatic_failover_enabled = var.environment == "production"

  # Maintenance
  maintenance_window = "sun:05:00-sun:06:00"
  snapshot_window    = "02:00-03:00"
  snapshot_retention_limit = var.environment == "production" ? 7 : 1
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "rds_connection_string" {
  description = "RDS connection string for application"
  value       = "postgresql://${var.rds_username}:${var.rds_password}@${module.rds.endpoint}/${module.rds.database_name}"
  sensitive   = true
}

output "s3_artifacts_bucket" {
  description = "S3 bucket for artifacts"
  value       = module.s3_artifacts.bucket_name
}

output "s3_artifacts_bucket_arn" {
  description = "S3 bucket ARN for IAM policies"
  value       = module.s3_artifacts.bucket_arn
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = module.redis.endpoint
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = "redis://${module.redis.endpoint}"
  sensitive   = true
}
