#!/usr/bin/env bash
set -e
BASE="http://localhost:8000"

echo "==> Creating run..."
RUN=$(curl -sf -X POST $BASE/runs -H "Content-Type: application/json" \
  -d '{"name":"smoke-test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "    run_id=$RUN"

echo "==> Seeding embeddings..."
python3 -c "
import json, numpy as np
from pathlib import Path
Path('artifacts/ml').mkdir(parents=True, exist_ok=True)
rows = [{f'dim_{d}': float(v) for d,v in enumerate(np.random.randn(32))} for _ in range(20)]
Path(f'artifacts/ml/$RUN.json').write_text(json.dumps(rows))
"

echo "==> Computing vector..."
curl -sf -X POST "$BASE/runs/$RUN/compute_vector" > /dev/null

echo "==> Checking similarity endpoint..."
curl -sf "$BASE/similarity/$RUN" | python3 -m json.tool

echo "==> All checks passed."