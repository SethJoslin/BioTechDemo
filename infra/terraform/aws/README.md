# OpenBioOps AWS Infrastructure

Terraform configuration for deploying OpenBioOps on AWS with EKS, RDS, S3, and Redis.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                           AWS VPC                           │
│                                                             │
│  ┌───────────────────┐      ┌────────────────────────┐    │
│  │  Public Subnets   │      │   Private Subnets      │    │
│  │                   │      │                        │    │
│  │  - NAT Gateway    │      │  ┌──────────────────┐ │    │
│  │  - ALB            │──────┼─ │  EKS Cluster     │ │    │
│  │  - Bastion        │      │  │  - API Pods      │ │    │
│  └───────────────────┘      │  │  - Worker Pods   │ │    │
│                             │  │  - MLflow        │ │    │
│                             │  └──────────────────┘ │    │
│                             │                        │    │
│                             │  ┌──────────────────┐ │    │
│                             │  │ RDS PostgreSQL   │ │    │
│                             │  └──────────────────┘ │    │
│                             │                        │    │
│                             │  ┌──────────────────┐ │    │
│                             │  │ ElastiCache Redis│ │    │
│                             │  └──────────────────┘ │    │
│                             └────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │    S3 Artifacts       │
                        │  - ML Models          │
                        │  - Embeddings         │
                        │  - Batch Results      │
                        └───────────────────────┘
```

## Prerequisites

1. **AWS CLI** configured with credentials
2. **Terraform** >= 1.5.0
3. **kubectl** for Kubernetes management
4. **aws-iam-authenticator** for EKS access

## Quick Start

### 1. Configure Backend

Create `backend.tfvars`:

```hcl
bucket         = "your-terraform-state-bucket"
key            = "openbioops/prod/terraform.tfstate"
region         = "us-west-2"
dynamodb_table = "terraform-state-lock"
encrypt        = true
```

Initialize Terraform:

```bash
terraform init -backend-config=backend.tfvars
```

### 2. Configure Variables

Copy the example:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` for your environment:

```hcl
environment  = "production"
aws_region   = "us-west-2"
project_name = "openbioops"

# Scale for production
eks_node_desired_size = 3
eks_node_max_size     = 20
rds_instance_class    = "db.r6g.xlarge"
```

### 3. Set Secrets

Export sensitive variables:

```bash
export TF_VAR_rds_password="your-secure-password"
```

Or use AWS Secrets Manager (recommended for production).

### 4. Plan and Apply

Review changes:

```bash
terraform plan -out=tfplan
```

Apply infrastructure:

```bash
terraform apply tfplan
```

### 5. Configure kubectl

```bash
aws eks update-kubeconfig /
  --region us-west-2 /
  --name openbioops-production
```

Verify access:

```bash
kubectl get nodes
```

## Modules

### VPC Module (`modules/vpc`)

Creates VPC with public and private subnets across multiple AZs.

**Features:**
- Public subnets for ALB and NAT gateways
- Private subnets for EKS, RDS, and Redis
- Automatic subnet tagging for EKS
- Optional single NAT gateway for dev/staging

### EKS Module (`modules/eks`)

Provisions EKS cluster with managed node groups.

**Node Groups:**
- **General**: CPU workloads (API, Celery workers)
- **ML Workloads**: GPU instances (g4dn.xlarge) with taints

**Features:**
- IRSA (IAM Roles for Service Accounts)
- Cluster autoscaler support
- CloudWatch logs enabled
- Managed node groups with auto-scaling

### RDS Module (`modules/rds`)

PostgreSQL database for application data.

**Features:**
- Multi-AZ for high availability (production)
- Automated backups
- Performance Insights enabled
- Security group with EKS access only
- Encryption at rest

### S3 Module (`modules/s3`)

Artifact storage with lifecycle policies.

**Features:**
- Versioning enabled
- Lifecycle rules (Glacier after 90 days, Deep Archive after 180)
- CORS configuration for dashboard
- Server-side encryption

### Redis Module (`modules/redis`)

ElastiCache Redis for Celery broker and caching.

**Features:**
- Multi-node for production
- Automatic failover
- Automated snapshots
- In-transit encryption

## Cost Estimates

### Development Environment

```
EKS Control Plane:       $73/month
EC2 Nodes (2x t3.large): $120/month
RDS (db.t3.medium):      $60/month
Redis (cache.t3.medium): $45/month
S3 Storage:              ~$10/month
NAT Gateway:             $32/month
Total:                   ~$340/month
```

### Production Environment

```
EKS Control Plane:         $73/month
EC2 Nodes (3x t3.large):   $180/month
GPU Nodes (2x g4dn.xlarge):$1000/month
RDS (db.r6g.xlarge):       $350/month
Redis (cache.r6g.large):   $200/month
S3 Storage:                ~$50/month
NAT Gateway (3x AZ):       $96/month
Total:                     ~$1,950/month
```

**Cost Optimization:**
- Use Spot instances for ML workloads (-70%)
- Enable cluster autoscaler (scale to zero when idle)
- Use S3 lifecycle policies (Glacier)
- Single NAT gateway for dev/staging

## Post-Deployment

### 1. Deploy Application

```bash
# Update kubeconfig
aws eks update-kubeconfig --name openbioops-production

# Deploy Kubernetes manifests
kubectl apply -f ../../k8s/base/
kubectl apply -f ../../k8s/overlays/production/

# Verify deployment
kubectl get pods -n openbioops
```

### 2. Configure Secrets

```bash
# Create database secret
kubectl create secret generic db-credentials /
  --from-literal=url="postgresql://user:pass@${RDS_ENDPOINT}/openbioops" /
  -n openbioops

# Create JWT secret
kubectl create secret generic jwt-secret /
  --from-literal=secret=$(openssl rand -base64 32) /
  -n openbioops
```

### 3. Configure Ingress

Update DNS to point to ALB:

```bash
# Get ALB hostname
kubectl get ingress -n openbioops

# Create Route53 record
aws route53 change-resource-record-sets /
  --hosted-zone-id YOUR_ZONE_ID /
  --change-batch file://dns-update.json
```

## Maintenance

### Updating Infrastructure

```bash
# Pull latest changes
git pull

# Review changes
terraform plan

# Apply updates
terraform apply
```

### Backup and Recovery

RDS automated backups:
- Retention: 7 days (production), 1 day (dev)
- Backup window: 03:00-04:00 UTC
- Point-in-time recovery enabled

Redis snapshots:
- Snapshot window: 02:00-03:00 UTC
- Retention: 7 days (production), 1 day (dev)

### Monitoring

Access CloudWatch dashboards:

```bash
aws cloudwatch list-dashboards --region us-west-2
```

View EKS cluster logs:

```bash
aws logs tail /aws/eks/openbioops-production/cluster --follow
```

## Troubleshooting

### Cannot connect to EKS cluster

```bash
# Update kubeconfig
aws eks update-kubeconfig --name openbioops-production --region us-west-2

# Verify IAM permissions
aws eks describe-cluster --name openbioops-production
```

### RDS connection issues

```bash
# Test from EKS pod
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- /
  psql -h ${RDS_ENDPOINT} -U openbioops -d openbioops
```

### High costs

```bash
# Check EC2 instances
aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,State.Name]'

# Check RDS instances
aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,DBInstanceClass,DBInstanceStatus]'

# Review S3 storage classes
aws s3api list-objects-v2 --bucket openbioops-production-artifacts /
  --query 'Contents[*].[Key,StorageClass,Size]'
```

## Security Best Practices

1. **Use AWS Secrets Manager** for sensitive values
2. **Enable MFA** for AWS console access
3. **Restrict security groups** to minimum required access
4. **Enable VPC Flow Logs** for network monitoring
5. **Use IAM roles** instead of access keys
6. **Enable CloudTrail** for audit logging
7. **Regular security scanning** with AWS Security Hub

## Cleanup

To destroy all infrastructure:

```bash
# WARNING: This will delete all resources including data!
terraform destroy

# Confirm by typing 'yes'
```

**Note**: RDS deletion protection is enabled in production. Disable before destroying:

```bash
aws rds modify-db-instance /
  --db-instance-identifier openbioops-production /
  --no-deletion-protection
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/openbioops/issues
- Terraform docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- AWS EKS docs: https://docs.aws.amazon.com/eks/
