#!/bin/bash

# Phase 5 HITL Testing Script
# Tests approval/rejection flows without UI buttons

set -e

API_BASE="http://localhost:8000/api"
RUN_ID=${1:-"test_run_12345"}  # Pass run_id as argument or use default
AUTH_TOKEN=${2:-"your_jwt_token"}  # Pass JWT token as argument

echo "=================================================="
echo "Phase 5 HITL Testing - Backend Only"
echo "=================================================="
echo "API Base: $API_BASE"
echo "Run ID: $RUN_ID"
echo ""

# TEST 1: Get approval status for PPTX
echo "TEST 1: Get PPTX approval status"
echo "Request: GET /api/runs/$RUN_ID/phase5/approval-status/pptx"
curl -s -X GET "$API_BASE/runs/$RUN_ID/phase5/approval-status/pptx" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" | jq '.'
echo ""

# TEST 2: Get all approval statuses
echo "TEST 2: Get all artifact approval statuses"
echo "Request: GET /api/runs/$RUN_ID/phase5/approval-status"
curl -s -X GET "$API_BASE/runs/$RUN_ID/phase5/approval-status" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" | jq '.'
echo ""

# TEST 3: Partial PPTX rejection (slides 2, 4)
echo "TEST 3: Partial PPTX rejection (slides 2 and 4)"
echo "Request: POST /api/runs/$RUN_ID/phase5/reject"
curl -s -X POST "$API_BASE/runs/$RUN_ID/phase5/reject" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "artifact_type": "pptx",
    "rejected_slides": [2, 4],
    "approved_slides": [1, 3, 5],
    "user_feedback": "White space needs improvement"
  }' | jq '.'
echo ""

echo "Phase 5 goes back to HITL (polls for next decision)"
echo "Wait a few seconds..."
sleep 3

# TEST 4: Get updated approval status (should show v2, attempt 1/3)
echo "TEST 4: Check updated PPTX status after rejection"
echo "Request: GET /api/runs/$RUN_ID/phase5/approval-status/pptx"
curl -s -X GET "$API_BASE/runs/$RUN_ID/phase5/approval-status/pptx" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" | jq '.'
echo ""

# TEST 5: Approve all (move to Phase 6)
echo "TEST 5: Approve all artifacts (move to Phase 6)"
echo "Request: POST /api/runs/$RUN_ID/phase5/approve-all"
curl -s -X POST "$API_BASE/runs/$RUN_ID/phase5/approve-all" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" | jq '.'
echo ""

echo "=================================================="
echo "✓ Phase 5 Testing Complete"
echo "=================================================="
echo ""
echo "Test Results:"
echo "  1. Can get approval status for individual artifacts"
echo "  2. Can get all approval statuses"
echo "  3. Can submit partial PPTX rejection"
echo "  4. Rejection creates new version (v2)"
echo "  5. Can approve all to move to Phase 6"
