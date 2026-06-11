# Kubernetes Configuration for OpenBioOps

This directory contains Kubernetes manifests for deploying and scaling OpenBioOps.

## Directory Structure

```
k8s/
├── hpa.yaml                    # Horizontal Pod Autoscalers (CPU/memory-based)
├── keda-scaledobjects.yaml     # KEDA ScaledObjects (queue/metric-based)
├── README.md                   # This file
└── base/                       # Base Kubernetes manifests (if using Kustomize)
```

## Auto-Scaling Strategy

OpenBioOps uses a **two-tier auto-scaling strategy**:

### Tier 1: Standard HPA (Horizontal Pod Autoscaler)

For basic resource-based scaling:
- **API Pods**: Scale 2-20 replicas based on CPU (70%), memory (80%), HTTP req/s (1000)
- **Celery Workers**: Scale 1-10 replicas based on CPU (75%), memory (85%)

### Tier 2: KEDA (Kubernetes Event-Driven Autoscaling)

For advanced, event-driven scaling:
- **Celery Workers**: Scale 1-50 replicas based on Redis queue length
- **API Pods**: Scale 2-30 replicas based on Prometheus metrics (latency, request rate)
- **Batch Processors**: Scale 0-10 replicas based on pending batch jobs (scale to zero!)
- **MLflow Server**: Scale 1-5 replicas based on request rate

## Prerequisites

### 1. Install Metrics Server

Required for HPA to access CPU/memory metrics:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

Verify:

```bash
kubectl top nodes
kubectl top pods -n openbioops
```

### 2. Install KEDA

Required for advanced auto-scaling:

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace
```

Verify:

```bash
kubectl get pods -n keda
```

### 3. Install Prometheus (Optional)

For custom metric-based scaling:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/prometheus --namespace monitoring --create-namespace
```

## Quick Start

### 1. Apply HPA Configuration

Basic CPU/memory-based auto-scaling:

```bash
kubectl apply -f hpa.yaml
```

Verify:

```bash
kubectl get hpa -n openbioops
kubectl describe hpa api-hpa -n openbioops
```

### 2. Apply KEDA ScaledObjects

Advanced event-driven auto-scaling:

```bash
# Create secrets first
kubectl create secret generic redis-password /
  --from-literal=password=your-redis-password /
  -n openbioops

kubectl create secret generic postgres-credentials /
  --from-literal=password=your-postgres-password /
  -n openbioops

# Apply KEDA configuration
kubectl apply -f keda-scaledobjects.yaml
```

Verify:

```bash
kubectl get scaledobjects -n openbioops
kubectl describe scaledobject celery-worker-scaler -n openbioops
```

## Monitoring Auto-Scaling

### View Current Replica Counts

```bash
kubectl get deployments -n openbioops
```

### Watch HPA in Real-Time

```bash
kubectl get hpa -n openbioops --watch
```

### View KEDA Metrics

```bash
# Get current metrics from KEDA
kubectl get scaledobject celery-worker-scaler -n openbioops -o jsonpath='{.status.externalMetricNames}'

# View detailed status
kubectl describe scaledobject celery-worker-scaler -n openbioops
```

### View Scaling Events

```bash
# HPA events
kubectl describe hpa api-hpa -n openbioops | tail -20

# KEDA events
kubectl describe scaledobject celery-worker-scaler -n openbioops | tail -20

# All events in namespace
kubectl get events -n openbioops --sort-by='.lastTimestamp'
```

## Load Testing

### Test API Auto-Scaling

```bash
# Install hey (HTTP load generator)
go install github.com/rakyll/hey@latest

# Generate load
hey -z 5m -c 50 -q 10 https://api.openbioops.com/health

# Watch scaling in another terminal
kubectl get hpa api-hpa -n openbioops --watch
```

### Test Celery Worker Auto-Scaling

```bash
# Queue 1000 jobs
for i in {1..1000}; do
  curl -X POST https://api.openbioops.com/v1/batch /
    -H "Authorization: Bearer $TOKEN" /
    -d '{"run_ids":["..."]}'
done

# Watch scaling
kubectl get scaledobject celery-worker-scaler -n openbioops --watch
```

## Configuration Tuning

### Adjust Scale-Up Speed

For faster scale-up during traffic spikes:

```yaml
behavior:
  scaleUp:
    stabilizationWindowSeconds: 0  # Scale immediately
    policies:
    - type: Percent
      value: 200  # Triple pods instead of double
      periodSeconds: 15  # Check every 15 seconds
```

### Adjust Scale-Down Speed

For more conservative scale-down:

```yaml
behavior:
  scaleDown:
    stabilizationWindowSeconds: 600  # Wait 10 minutes
    policies:
    - type: Percent
      value: 25  # Scale down max 25% at a time
      periodSeconds: 180  # Check every 3 minutes
```

### Adjust Thresholds

For more aggressive scaling:

```yaml
# HPA: Scale at lower CPU usage
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 50  # Was 70

# KEDA: Scale at lower queue length
- type: redis
  metadata:
    listLength: "5"  # Was 10
```

## Cost Optimization

### Scale to Zero with KEDA

For non-critical workloads:

```yaml
spec:
  minReplicaCount: 0  # Scale to zero when idle
  cooldownPeriod: 600  # Keep scaled up for 10 minutes after last event
```

**Workloads suitable for scale-to-zero:**
- Batch processors (only needed when jobs are queued)
- Dev/staging environments (during off-hours)
- ML training jobs (on-demand)

### Use Spot Instances

For ML workloads (configured in Terraform):

```hcl
node_groups = {
  ml_workloads = {
    capacity_type = "SPOT"  # Use spot instances
    instance_types = ["g4dn.xlarge", "g4dn.2xlarge"]  # Multiple types for availability
  }
}
```

### Set Resource Limits

Prevent over-provisioning:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

## Troubleshooting

### HPA shows "unknown" metrics

```bash
# Check metrics server
kubectl get apiservice v1beta1.metrics.k8s.io -o yaml

# Restart metrics server
kubectl rollout restart deployment metrics-server -n kube-system
```

### KEDA not scaling

```bash
# Check KEDA operator logs
kubectl logs -n keda -l app=keda-operator

# Check scaledobject status
kubectl get scaledobject celery-worker-scaler -n openbioops -o yaml

# Verify trigger authentication
kubectl get triggerauthentication -n openbioops
```

### Pods not scaling down

```bash
# Check PodDisruptionBudget
kubectl get pdb -n openbioops

# Check if pods have active connections
kubectl exec -it api-xxxx -n openbioops -- netstat -an | grep ESTABLISHED
```

### High costs

```bash
# Review current replica counts
kubectl get deployments -n openbioops

# Check resource utilization
kubectl top pods -n openbioops

# Adjust min replicas if over-provisioned
kubectl patch hpa api-hpa -n openbioops -p '{"spec":{"minReplicas":1}}'
```

## Best Practices

1. **Start conservative**: Begin with higher thresholds and adjust based on metrics
2. **Monitor first**: Collect metrics for 1-2 weeks before enabling auto-scaling
3. **Test under load**: Use load testing to validate scaling behavior
4. **Set PodDisruptionBudgets**: Ensure availability during scale-down
5. **Use resource requests**: HPA requires resource requests to calculate utilization
6. **Combine HPA + KEDA**: Use HPA for basic scaling, KEDA for specialized workloads
7. **Enable cluster autoscaler**: Allow K8s to provision nodes as needed

## Further Reading

- [Kubernetes HPA Documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [KEDA Documentation](https://keda.sh/docs/)
- [KEDA Scalers](https://keda.sh/docs/scalers/)
- [EKS Cluster Autoscaler](https://docs.aws.amazon.com/eks/latest/userguide/autoscaling.html)
