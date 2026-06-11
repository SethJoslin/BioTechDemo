#!/bin/bash
# Smoke tests for OpenBioOps API
# Usage: ./smoke-test.sh <base-url>

set -e

BASE_URL="${1:-http://localhost:8000}"
echo "Running smoke tests against: $BASE_URL"

# Colors for output
GREEN='/033[0;32m'
RED='/033[0;31m'
NC='/033[0m' # No Color

pass() {
    echo -e "${GREEN}✓${NC} $1"
}

fail() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

# Test 1: Health check (liveness)
echo "Test 1: Health check (liveness)..."
if curl -f -s "${BASE_URL}/health/live" > /dev/null; then
    pass "Liveness probe is healthy"
else
    fail "Liveness probe failed"
fi

# Test 2: Readiness probe
echo "Test 2: Readiness probe..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health/ready")
if [ "$RESPONSE" = "200" ]; then
    pass "Readiness probe is healthy"
else
    fail "Readiness probe failed (HTTP $RESPONSE)"
fi

# Test 3: Metrics endpoint
echo "Test 3: Metrics endpoint..."
if curl -f -s "${BASE_URL}/metrics" | grep -q "api_request_count"; then
    pass "Metrics endpoint is working"
else
    fail "Metrics endpoint failed"
fi

# Test 4: OpenAPI docs
echo "Test 4: OpenAPI docs..."
if curl -f -s "${BASE_URL}/docs" > /dev/null; then
    pass "API documentation is accessible"
else
    fail "API documentation failed"
fi

# Test 5: Authentication endpoint
echo "Test 5: Authentication endpoint..."
RESPONSE=$(curl -s -X POST "${BASE_URL}/v1/auth/token" /
    -H "Content-Type: application/json" /
    -d '{"username":"test","password":"wrong"}')

if echo "$RESPONSE" | grep -q "detail"; then
    pass "Authentication endpoint is responding"
else
    fail "Authentication endpoint failed"
fi

# Test 6: Response time check
echo "Test 6: Response time check..."
START=$(date +%s%N)
curl -f -s "${BASE_URL}/health/live" > /dev/null
END=$(date +%s%N)
ELAPSED=$(((END - START) / 1000000))  # Convert to milliseconds

if [ $ELAPSED -lt 1000 ]; then
    pass "Response time is acceptable (${ELAPSED}ms)"
else
    fail "Response time is too slow (${ELAPSED}ms)"
fi

echo ""
echo "All smoke tests passed! 🎉"
echo "Deployment is healthy and ready to serve traffic."
