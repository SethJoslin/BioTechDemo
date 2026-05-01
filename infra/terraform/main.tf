module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = ">= 18.0.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.27"
  subnets         = module.vpc.private_subnets
  vpc_id          = module.vpc.vpc_id

  node_groups = {
    openbioops_nodes = {
      desired_capacity = var.node_group_desired
      min_capacity     = var.node_group_min
      max_capacity     = var.node_group_max
      instance_type    = "m5.large"
    }
  }

  tags = {
    Project = "openbioops"
  }
}

resource "aws_iam_role" "nextflow_irsa_role" {
  name = "openbioops-nextflow-irsa"
  assume_role_policy = data.aws_iam_policy_document.irsa_assume_role.json
}

data "aws_iam_policy_document" "irsa_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }
    actions = ["sts:AssumeRoleWithWebIdentity"]
    condition {
      test     = "StringEquals"
      values   = ["system:serviceaccount:default:nextflow-runner"]
      variable = "${replace(module.eks.oidc_provider_url, "https://", "")}:sub"
    }
  }
}