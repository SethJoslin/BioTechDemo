terraform {
  required_version = ">= 1.5"

  backend "s3" {}   # values supplied via -backend-config at init time
}

provider "aws" {
  region = var.aws_region
}