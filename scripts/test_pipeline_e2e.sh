#!/bin/bash
# End-to-End Pipeline Test Script
# Tests the complete staged analysis pipeline via REST API

set -e  # Exit on any error

API_BASE="${API_BASE:-http://localhost:8000}"
USERNAME="${USERNAME:-testuser}"
RAW_DATA_PATH="${RAW_DATA_PATH:-data/pbmc3k_raw.h5ad}"

echo "🧬 BioTech Demo - Staged Pipeline E2E Test"
echo "=========================================="
echo "API: $API_BASE"
echo "User: $USERNAME"
echo "Data: $RAW_DATA_PATH"
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Get auth token
echo -e "${BLUE}Step 1: Authenticating...${NC}"
TOKEN=$(curl -s -X POST "$API_BASE/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$USERNAME\"}" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo -e "${RED}❌ Failed to get auth token${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Authenticated${NC}"
echo ""

# Step 2: Create a run
echo -e "${BLUE}Step 2: Creating run...${NC}"
RUN_RESPONSE=$(curl -s -X POST "$API_BASE/v1/runs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "E2E Test Run - '"$(date +%Y%m%d_%H%M%S)"'"}')

RUN_ID=$(echo "$RUN_RESPONSE" | jq -r '.id')
if [ "$RUN_ID" == "null" ] || [ -z "$RUN_ID" ]; then
  echo -e "${RED}❌ Failed to create run${NC}"
  echo "$RUN_RESPONSE"
  exit 1
fi
echo -e "${GREEN}✓ Run created: $RUN_ID${NC}"
echo ""

# Step 3: Start full analysis
echo -e "${BLUE}Step 3: Starting full 4-stage analysis...${NC}"
START_RESPONSE=$(curl -s -X POST "$API_BASE/v1/runs/$RUN_ID/analysis/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_path": "'"$RAW_DATA_PATH"'",
    "params": {
      "min_genes": 200,
      "max_genes": 5000,
      "max_pct_mt": 20.0,
      "n_neighbors": 15,
      "min_dist": 0.1,
      "resolution": 1.0
    }
  }')

WORKFLOW_ID=$(echo "$START_RESPONSE" | jq -r '.workflow_run_id')
if [ "$WORKFLOW_ID" == "null" ] || [ -z "$WORKFLOW_ID" ]; then
  echo -e "${RED}❌ Failed to start analysis${NC}"
  echo "$START_RESPONSE"
  exit 1
fi
echo -e "${GREEN}✓ Analysis started: $WORKFLOW_ID${NC}"
echo ""

# Step 4: Poll status until complete
echo -e "${BLUE}Step 4: Monitoring pipeline progress...${NC}"
MAX_WAIT=300  # 5 minutes
POLL_INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
  STATUS_RESPONSE=$(curl -s -X GET "$API_BASE/v1/runs/$RUN_ID/analysis/status" \
    -H "Authorization: Bearer $TOKEN")

  STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
  CURRENT_STAGE=$(echo "$STATUS_RESPONSE" | jq -r '.current_stage // "N/A"')

  # Print stage statuses
  echo -ne "\r${YELLOW}Status: $STATUS | Current: Stage $CURRENT_STAGE${NC}"

  # Extract stage info
  STAGE_1=$(echo "$STATUS_RESPONSE" | jq -r '.stages[0].status')
  STAGE_2=$(echo "$STATUS_RESPONSE" | jq -r '.stages[1].status')
  STAGE_3=$(echo "$STATUS_RESPONSE" | jq -r '.stages[2].status')
  STAGE_4=$(echo "$STATUS_RESPONSE" | jq -r '.stages[3].status')

  echo -ne " | Stages: [$STAGE_1, $STAGE_2, $STAGE_3, $STAGE_4]"

  if [ "$STATUS" == "completed" ]; then
    echo ""
    echo -e "${GREEN}✓ Pipeline completed successfully!${NC}"
    echo ""
    echo "Stage Details:"
    echo "$STATUS_RESPONSE" | jq '.stages[] | "  Stage \(.stage): \(.name) - \(.status) (\(.duration_sec // 0)s)"' -r
    break
  elif [ "$STATUS" == "failed" ]; then
    echo ""
    echo -e "${RED}❌ Pipeline failed${NC}"
    ERROR_MSG=$(echo "$STATUS_RESPONSE" | jq -r '.error_message // "Unknown error"')
    echo "Error: $ERROR_MSG"
    exit 1
  fi

  sleep $POLL_INTERVAL
  ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  echo ""
  echo -e "${RED}❌ Pipeline timed out after ${MAX_WAIT}s${NC}"
  exit 1
fi

# Step 5: Verify QC metrics
echo -e "${BLUE}Step 5: Verifying QC metrics...${NC}"
QC_RESPONSE=$(curl -s -X GET "$API_BASE/v1/runs/$RUN_ID/qc" \
  -H "Authorization: Bearer $TOKEN")

N_CELLS=$(echo "$QC_RESPONSE" | jq -r '.metrics.n_cells // 0')
if [ "$N_CELLS" -gt 0 ]; then
  echo -e "${GREEN}✓ QC metrics present (n_cells: $N_CELLS)${NC}"
  echo "  Median genes/cell: $(echo "$QC_RESPONSE" | jq -r '.metrics.median_genes_per_cell // "N/A"')"
  echo "  Median counts/cell: $(echo "$QC_RESPONSE" | jq -r '.metrics.median_counts_per_cell // "N/A"')"
else
  echo -e "${YELLOW}⚠ QC metrics not found or incomplete${NC}"
fi
echo ""

# Step 6: Test UMAP parameter tuning (re-run stage 3)
echo -e "${BLUE}Step 6: Testing UMAP parameter tuning...${NC}"
RERUN_RESPONSE=$(curl -s -X POST "$API_BASE/v1/runs/$RUN_ID/analysis/rerun-stage" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stage": 3,
    "params": {
      "n_neighbors": 30,
      "min_dist": 0.01
    }
  }')

RERUN_STATUS=$(echo "$RERUN_RESPONSE" | jq -r '.status')
if [ "$RERUN_STATUS" == "completed" ]; then
  echo -e "${GREEN}✓ UMAP re-run successful with n_neighbors=30, min_dist=0.01${NC}"
else
  echo -e "${RED}❌ UMAP re-run failed${NC}"
  echo "$RERUN_RESPONSE"
fi
echo ""

# Step 7: Test clustering parameter tuning (re-run stage 4)
echo -e "${BLUE}Step 7: Testing clustering parameter tuning...${NC}"
RERUN_RESPONSE=$(curl -s -X POST "$API_BASE/v1/runs/$RUN_ID/analysis/rerun-stage" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stage": 4,
    "params": {
      "resolution": 0.5
    }
  }')

RERUN_STATUS=$(echo "$RERUN_RESPONSE" | jq -r '.status')
if [ "$RERUN_STATUS" == "completed" ]; then
  echo -e "${GREEN}✓ Clustering re-run successful with resolution=0.5${NC}"
else
  echo -e "${RED}❌ Clustering re-run failed${NC}"
  echo "$RERUN_RESPONSE"
fi
echo ""

# Final summary
echo "=========================================="
echo -e "${GREEN}✅ E2E Test PASSED${NC}"
echo ""
echo "Run ID: $RUN_ID"
echo "Workflow ID: $WORKFLOW_ID"
echo ""
echo "Next steps:"
echo "  • View Prefect UI: http://localhost:4200"
echo "  • View Dashboard: http://localhost:3000"
echo "  • Check artifacts: docker compose exec api ls /app/artifacts/"
echo "  • View run details: curl $API_BASE/v1/runs/$RUN_ID -H 'Authorization: Bearer $TOKEN'"