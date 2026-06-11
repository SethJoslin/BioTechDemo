# Model Management Guide

Complete guide to ML model versioning, deployment, and rollback in OpenBioOps.

---

## Quick Start

```bash
# 1. Generate the initial model (run once)
make generate-model

# 2. Start MLflow UI to view model registry
make mlflow-ui

# 3. Start API (automatically loads Production model from registry)
make api
```

---

## Problem Statement

**The Issue:** The original codebase had `model.pt` missing, and no documentation on how to create it.

**Production Gap:** No model versioning, no rollback capability, no way to track which model version made which prediction.

**Solution:** Full MLflow Model Registry integration with automated model generation and production-grade versioning.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   MLflow Model Registry                     │
│                   http://localhost:5000                     │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Version 1  │  │  Version 2  │  │  Version 3  │        │
│  │  Archived   │  │  Production │  │  Staging    │        │
│  │  (rollback) │  │  (active)   │  │  (testing)  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│         ▲                 │                 │               │
└─────────┼─────────────────┼─────────────────┼───────────────┘
          │                 │                 │
          │                 ▼                 │
          │         ┌──────────────┐          │
          │         │ ModelServer  │          │
          │         │   (active)   │          │
          │         └──────────────┘          │
          │                 │                 │
          │      Loads from registry          │
          │      on startup / reload          │
          │                 │                 │
          └────── Rollback  │  Hot-swap ─────┘
                            │
                    ┌───────▼────────┐
                    │  FastAPI App   │
                    │  /v1/runs      │
                    │  /v1/batch     │
                    └────────────────┘
```

---

## 1. Initial Model Generation

### Generate ml/model.pt

The `generate_model.py` script:
1. Loads raw PBMC 3k data (`data/pbmc3k_raw.h5ad`)
2. Extracts PCA features (50 PCs, 2000 HVGs)
3. Trains contrastive encoder (20 epochs, NT-Xent loss)
4. Saves `ml/model.pt` checkpoint
5. Registers model in MLflow registry as **v1, Production**

```bash
make generate-model
```

**Output:**
```
==================================================================
  OpenBioOps Model Generation
==================================================================

[1/3] Extracting PCA features from pbmc3k_raw.h5ad...
      ✓ Features saved to artifacts/features/pbmc3k.parquet

[2/3] Training contrastive encoder...
      Features shape: (2638, 50)
      Training for 20 epochs...
      Epoch   5/20  loss=0.3245  lr=0.000951
      Epoch  10/20  loss=0.2134  lr=0.000809
      Epoch  15/20  loss=0.1876  lr=0.000588
      Epoch  20/20  loss=0.1654  lr=0.000309
      ✓ Training complete! Best loss: 0.1654

[3/3] Saving and registering model...
      ✓ Checkpoint saved to ml/model.pt
      ✓ Model registered in MLflow
      Run ID: a7f4e9c2b1d5...

==================================================================
✓ Model generation complete!
==================================================================

Model checkpoint: /path/to/ml/model.pt
MLflow UI: http://localhost:5000
Run ID: a7f4e9c2b1d5...

To use this model:
  1. Start the API: make api
  2. Model will load automatically from ml/model.pt
  3. Check /health endpoint to verify model loaded
```

**What Gets Created:**
- `ml/model.pt` - PyTorch checkpoint (local fallback)
- `artifacts/features/pbmc3k.parquet` - PCA features (2638 cells × 50 PCs)
- MLflow run with full training metrics
- Model registered in MLflow registry as "contrastive_encoder" v1

---

## 2. Model Loading Strategy

The `ModelServer` uses a **smart fallback strategy**:

### Priority 1: MLflow Registry (Production)
```python
# On startup, ModelServer attempts:
1. Connect to MLflow at http://localhost:5000
2. Load model from Production stage
3. Store version metadata (version, run_id, stage)
```

### Priority 2: Local Checkpoint (Fallback)
```python
# If registry unavailable:
1. Fall back to ml/model.pt
2. Log warning about degraded mode
3. Continue serving (no version tracking)
```

### Example Startup Logs

**Success (Registry):**
```
✓ Loaded model from MLflow registry: v2 (Production)
ModelServer initialized: input_dim=50, hidden_dim=256, emb_dim=64
```

**Fallback (Local):**
```
 MLflow registry unavailable (Connection refused), falling back to local checkpoint
✓ Loaded model from ml/model.pt
ModelServer initialized: input_dim=50, hidden_dim=256, emb_dim=64
```

---

## 3. Model Versioning Workflow

### Stage Promotion Flow

```
┌──────────────┐
│ Train Model  │  Run ml/train.py or generate_model.py
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Version N  │  Automatically registered in MLflow
│   Stage=None │  (not in any stage yet)
└──────┬───────┘
       │
       ▼  Promote to Staging for testing
┌──────────────┐
│   Version N  │  Test in staging environment
│ Stage=Staging│  Validate metrics, A/B test
└──────┬───────┘
       │
       ▼  Promote to Production (archives existing)
┌──────────────┐
│   Version N  │  Serving live traffic
│Stage=Production│  Version N-1 archived for rollback
└──────────────┘
```

### Programmatic Version Management

```python
from app.ml.model_registry import ModelRegistry

registry = ModelRegistry()

# List all versions
versions = registry.list_model_versions()
for v in versions:
    print(f"v{v['version']}: {v['stage']} (run={v['run_id'][:8]}...)")

# Promote v3 to staging
registry.promote_to_staging("contrastive_encoder", version="3")

# Promote v3 to production (archives current production)
registry.promote_to_production(
    "contrastive_encoder",
    version="3",
    archive_existing=True  # v2 → Archived
)
```

---

## 4. Production Rollback

### Why Rollback Matters

**Scenario:** You deploy v3 to production. Within 5 minutes, you notice:
- Inference latency increased 3x
- Prediction accuracy dropped 10%
- Users are reporting errors

**Traditional Approach:** Redeploy entire application with previous model checkpoint (10-15 min downtime)

**OpenBioOps Approach:** Hot-swap model in <1 second, zero downtime

### Rollback Command

```python
from app.ml.model_registry import ModelRegistry

registry = ModelRegistry()

# Instant rollback to most recent archived version
rolled_back_version = registry.rollback_production()
print(f"Rolled back to v{rolled_back_version}")
```

**What Happens:**
1. Identifies current Production version (v3)
2. Finds most recent Archived version (v2)
3. Archives v3 (v3 → Archived)
4. Promotes v2 (v2 → Production)
5. Returns v2 version number

**Logs:**
```
INFO Current production: v3
INFO Rolling back to archived v2
INFO Archived v3 (was Production)
INFO Promoted v2 to Production
INFO Rollback complete: v2 is now Production
```

### Hot-Swap Without Restart

```python
from app.ml.model_server import ModelServer

# Existing server instance
model_server = get_model_server()

# Reload production model (picks up v2 after rollback)
success = model_server.reload_from_registry(stage="Production")

if success:
    print(f"Now serving v{model_server.model_version}")
```

**Zero Downtime:** No pod restarts, no connection drops, no 503s.

---

## 5. API Endpoints for Model Management

### GET /v1/models/current

Get currently loaded model version:

```bash
curl http://localhost:8000/v1/models/current
```

```json
{
  "name": "contrastive_encoder",
  "version": "2",
  "stage": "Production",
  "run_id": "a7f4e9c2b1d5...",
  "loaded_from": "registry",
  "input_dim": 50,
  "hidden_dim": 256,
  "emb_dim": 64
}
```

### POST /v1/models/rollback

Trigger production rollback:

```bash
curl -X POST http://localhost:8000/v1/models/rollback /
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "success": true,
  "previous_version": "3",
  "current_version": "2",
  "message": "Rolled back from v3 to v2"
}
```

### POST /v1/models/reload

Hot-swap to specific version:

```bash
curl -X POST http://localhost:8000/v1/models/reload /
  -H "Authorization: Bearer $TOKEN" /
  -H "Content-Type: application/json" /
  -d '{"version": "2"}'
```

```json
{
  "success": true,
  "previous_version": "3",
  "current_version": "2",
  "message": "Model reloaded to v2"
}
```

---

## 6. Model Monitoring

### Prediction Logging

Every prediction is logged to `prediction_logs` table:

```sql
CREATE TABLE prediction_logs (
    id UUID PRIMARY KEY,
    run_id UUID,
    model_version VARCHAR NOT NULL,  -- "2"
    input_features TEXT NOT NULL,
    prediction TEXT NOT NULL,
    confidence FLOAT,
    latency_ms FLOAT NOT NULL,
    endpoint VARCHAR NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
```

### Query Model Performance

```sql
-- Average latency by model version
SELECT
    model_version,
    COUNT(*) as predictions,
    AVG(latency_ms) as avg_latency_ms,
    STDDEV(latency_ms) as stddev_latency
FROM prediction_logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY model_version
ORDER BY model_version DESC;
```

```
 model_version | predictions | avg_latency_ms | stddev_latency
---------------+-------------+----------------+---------------
 3             |       15243 |           45.3 |           12.1
 2             |       89234 |           22.7 |            5.4
```

**Insight:** v3 is 2x slower than v2 → rollback justified

---

## 7. Best Practices

### Development Workflow

```
1. Train new model locally or in notebook
   → python ml/train.py --input features.parquet --out model_v4.pt

2. Register in MLflow (automatic if using train.py)
   → Model appears as v4 with stage=None

3. Promote to Staging
   → registry.promote_to_staging("contrastive_encoder", "4")

4. Test in staging environment
   → Deploy to staging pod, run integration tests

5. Promote to Production
   → registry.promote_to_production("contrastive_encoder", "4", archive_existing=True)

6. Monitor for 24-48 hours
   → Check latency, accuracy, error rates

7. Keep v3 archived for rollback
   → If issues detected, instant rollback to v3
```

### Model Registry Hygiene

**Archive Old Versions:**
```python
# After 30 days, archive old staging versions
for version in registry.list_model_versions():
    if version['stage'] == 'Staging' and age_days(version) > 30:
        registry.archive_version(version['version'])
```

**Tag Models with Metadata:**
```python
# When promoting to production, add deployment tags
client.set_model_version_tag(
    name="contrastive_encoder",
    version="4",
    key="deployed_by",
    value="john@example.com"
)
client.set_model_version_tag(
    name="contrastive_encoder",
    version="4",
    key="deployment_date",
    value="2024-01-15"
)
```

### Disaster Recovery

**Backup ml/model.pt:**
```bash
# Daily backup to S3
aws s3 cp ml/model.pt s3://mybucket/models/$(date +%Y%m%d)_model.pt
```

**Export MLflow Registry:**
```bash
# Backup MLflow database
sqlite3 artifacts/mlflow/mlflow.db ".backup artifacts/mlflow/mlflow_backup_$(date +%Y%m%d).db"
```

---

## 8. Troubleshooting

### Model Not Found Error

**Symptom:**
```
FileNotFoundError: Model checkpoint not found: ml/model.pt
Run 'make generate-model' to create it.
```

**Fix:**
```bash
make generate-model
```

### MLflow Connection Refused

**Symptom:**
```
 MLflow registry unavailable (Connection refused), falling back to local checkpoint
```

**Fix:**
```bash
# Start MLflow UI
make mlflow-ui

# Or start via Docker
docker compose up mlflow
```

### Wrong Model Version Loaded

**Symptom:** API serving v2, but MLflow shows v3 is Production

**Fix:** Reload model from registry
```python
model_server.reload_from_registry(stage="Production")
```

Or restart API pod:
```bash
kubectl rollout restart deployment api -n openbioops
```

---

## 9. Future Enhancements

### A/B Testing
```python
# Route 10% of traffic to v4 (Staging), 90% to v3 (Production)
if random.random() < 0.1:
    model_server.reload_from_registry(stage="Staging")
else:
    model_server.reload_from_registry(stage="Production")
```

### Automated Rollback
```python
# Monitor prediction latency, auto-rollback if degraded
if avg_latency_ms > threshold:
    registry.rollback_production()
    alert_ops_team("Auto-rolled back due to latency spike")
```

### Model Drift Detection
```python
# Compare input feature distributions across model versions
current_features = load_features(model_version="3")
baseline_features = load_features(model_version="2")

drift_score = compute_drift(current_features, baseline_features)
if drift_score > 0.1:
    alert("Model drift detected, retrain recommended")
```

---

## Summary

 **No more missing model.pt** - Automated generation from PBMC data
 **Full version tracking** - Every model has version, run_id, metrics
 **Instant rollback** - <1s hot-swap, zero downtime
 **Production-grade** - Same patterns used at Netflix, Uber, Airbnb
 **Observable** - prediction_logs table tracks every inference

The model management system transforms this from "demo code" to "production-ready ML platform."
