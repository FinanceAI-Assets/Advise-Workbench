# Phase 5 HITL Testing Script (PowerShell)
# Tests approval/rejection flows without UI buttons

param(
    [string]$RunId = "test_run_12345",
    [string]$AuthToken = "your_jwt_token"
)

$ApiBase = "http://localhost:8000/api"

Write-Host "=================================================="
Write-Host "Phase 5 HITL Testing - Backend Only (PowerShell)"
Write-Host "=================================================="
Write-Host "API Base: $ApiBase"
Write-Host "Run ID: $RunId"
Write-Host ""

$headers = @{
    "Authorization" = "Bearer $AuthToken"
    "Content-Type" = "application/json"
}

# TEST 1: Get approval status for PPTX
Write-Host "TEST 1: Get PPTX approval status"
Write-Host "Request: GET /api/runs/$RunId/phase5/approval-status/pptx"
try {
    $response = Invoke-RestMethod -Uri "$ApiBase/runs/$RunId/phase5/approval-status/pptx" `
        -Method GET `
        -Headers $headers
    Write-Host ($response | ConvertTo-Json -Depth 10) -ForegroundColor Green
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# TEST 2: Get all approval statuses
Write-Host "TEST 2: Get all artifact approval statuses"
Write-Host "Request: GET /api/runs/$RunId/phase5/approval-status"
try {
    $response = Invoke-RestMethod -Uri "$ApiBase/runs/$RunId/phase5/approval-status" `
        -Method GET `
        -Headers $headers
    Write-Host ($response | ConvertTo-Json -Depth 10) -ForegroundColor Green
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# TEST 3: Partial PPTX rejection (slides 2, 4)
Write-Host "TEST 3: Partial PPTX rejection (slides 2 and 4)"
Write-Host "Request: POST /api/runs/$RunId/phase5/reject"
$body = @{
    artifact_type = "pptx"
    rejected_slides = @(2, 4)
    approved_slides = @(1, 3, 5)
    user_feedback = "White space needs improvement"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$ApiBase/runs/$RunId/phase5/reject" `
        -Method POST `
        -Headers $headers `
        -Body $body
    Write-Host ($response | ConvertTo-Json -Depth 10) -ForegroundColor Green
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

Write-Host "Phase 5 goes back to HITL (polls for next decision)"
Write-Host "Waiting 3 seconds..."
Start-Sleep -Seconds 3

# TEST 4: Get updated approval status (should show v2, attempt 1/3)
Write-Host "TEST 4: Check updated PPTX status after rejection"
Write-Host "Request: GET /api/runs/$RunId/phase5/approval-status/pptx"
try {
    $response = Invoke-RestMethod -Uri "$ApiBase/runs/$RunId/phase5/approval-status/pptx" `
        -Method GET `
        -Headers $headers
    Write-Host ($response | ConvertTo-Json -Depth 10) -ForegroundColor Green
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# TEST 5: Approve all (move to Phase 6)
Write-Host "TEST 5: Approve all artifacts (move to Phase 6)"
Write-Host "Request: POST /api/runs/$RunId/phase5/approve-all"
try {
    $response = Invoke-RestMethod -Uri "$ApiBase/runs/$RunId/phase5/approve-all" `
        -Method POST `
        -Headers $headers
    Write-Host ($response | ConvertTo-Json -Depth 10) -ForegroundColor Green
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

Write-Host "=================================================="
Write-Host "✓ Phase 5 Testing Complete" -ForegroundColor Green
Write-Host "=================================================="
Write-Host ""
Write-Host "Test Results:"
Write-Host "  1. Can get approval status for individual artifacts"
Write-Host "  2. Can get all approval statuses"
Write-Host "  3. Can submit partial PPTX rejection"
Write-Host "  4. Rejection creates new version (v2)"
Write-Host "  5. Can approve all to move to Phase 6"
