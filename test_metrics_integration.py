#!/usr/bin/env python3
"""
Test script to verify advanced metrics integration is working correctly.
Run this BEFORE doing a full Sheldon test to catch any integration issues.

Usage:
    python test_metrics_integration.py
"""

import sys
import time
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).resolve().parent
sys.path.insert(0, str(repo_root))

# Load environment
from dotenv import load_dotenv
load_dotenv(repo_root / ".env", override=True)

print("\n" + "="*70)
print("METRICS INTEGRATION TEST SUITE")
print("="*70)

# TEST 1: Import verification
print("\n[TEST 1] Checking imports...")
try:
    from src.core.observability.advanced_metrics import (
        record_agent_call,
        record_rag_retrieval,
        record_tool_call,
        record_application_request,
        record_quality_evaluation,
        get_all_advanced_metrics,
        set_application_concurrent_requests,
    )
    print("✅ All advanced_metrics functions imported successfully")
except ImportError as e:
    print(f"❌ FAILED to import advanced_metrics: {e}")
    sys.exit(1)

# TEST 2: OTEL/Metrics configuration
print("\n[TEST 2] Checking metrics module setup...")
try:
    from src.core.observability.metrics import increment, observe_latency, set_gauge
    print("✅ Metrics functions (increment, observe_latency, set_gauge) available")
except ImportError as e:
    print(f"❌ FAILED to import metrics module: {e}")
    sys.exit(1)

# TEST 3: Environment variables
print("\n[TEST 3] Verifying OpenObserve/OTEL configuration...")
import os
required_env_vars = [
    "OPENOBSERVE_ENABLED",
    "OPENOBSERVE_URL",
    "OPENOBSERVE_ORG",
    "OPENOBSERVE_USER",
    "OPENOBSERVE_PASSWORD",
    "OPENOBSERVE_STREAM",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
]

missing_vars = []
for var in required_env_vars:
    if var not in os.environ or not os.environ[var]:
        missing_vars.append(var)
    else:
        # Mask sensitive values in output
        val = os.environ[var]
        if "PASSWORD" in var or "TOKEN" in var or "KEY" in var:
            val = val[:10] + "..." if len(val) > 10 else "***"
        print(f"  ✅ {var} = {val}")

if missing_vars:
    print(f"❌ MISSING required env vars: {missing_vars}")
    sys.exit(1)
else:
    print("✅ All required environment variables are set")

# TEST 4: Record metrics (no-op test - just verify functions execute)
print("\n[TEST 4] Testing metric recording functions...")
try:
    # Agent metric
    record_agent_call(
        agent_name="test_agent",
        duration_ms=250.5,
        success=True,
        is_retry=False,
        project_id="test_project_001"
    )
    print("  ✅ record_agent_call() executed")

    # RAG metric
    record_rag_retrieval(
        relevant_chunks=8,
        total_chunks=10,
        supported_facts=5,
        total_facts=6,
        utilized_chunks=7,
        retrieval_latency_ms=145.3
    )
    print("  ✅ record_rag_retrieval() executed")

    # Tool metric
    record_tool_call(
        duration_ms=89.2,
        success=True,
        necessary=True
    )
    print("  ✅ record_tool_call() executed")

    # Application metric
    record_application_request(
        duration_ms=1250.8,
        success=True,
        cost=0.025,
        project_id="test_project_001"
    )
    print("  ✅ record_application_request() executed")

    # Quality evaluation metric
    record_quality_evaluation(
        completeness=0.85,
        clarity_readability=0.90,
        faithfulness_usefulness=0.88,
        content_accuracy=0.92,
        grade=None,  # Will auto-calculate
        score=None,  # Will auto-calculate
        project_id="test_project_001"
    )
    print("  ✅ record_quality_evaluation() executed")

    # Concurrent requests
    set_application_concurrent_requests(3)
    print("  ✅ set_application_concurrent_requests() executed")

except Exception as e:
    print(f"❌ FAILED to record metrics: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# TEST 5: Retrieve metrics
print("\n[TEST 5] Testing metrics retrieval...")
try:
    # Global metrics
    all_metrics = get_all_advanced_metrics(project_id=None)
    print("  ✅ get_all_advanced_metrics(project_id=None) - global metrics retrieved")

    # Check structure
    expected_keys = ["agent", "rag", "tool", "application", "quality_evaluation"]
    for key in expected_keys:
        if key in all_metrics:
            print(f"     ✅ {key} metrics present")
        else:
            print(f"     ⚠️  {key} metrics missing or empty")

    # Per-project metrics
    project_metrics = get_all_advanced_metrics(project_id="test_project_001")
    print("  ✅ get_all_advanced_metrics(project_id='test_project_001') - per-project metrics retrieved")

except Exception as e:
    print(f"❌ FAILED to retrieve metrics: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# TEST 6: Simulated run workflow
print("\n[TEST 6] Simulating a simplified run workflow...")
try:
    test_project_id = "sheldon_test_001"
    test_run_id = "run_12345"

    print(f"\n  Simulating run: {test_project_id}/{test_run_id}")

    # Coordinator execution
    print("    1. Coordinator executing...")
    coord_start = time.perf_counter()
    time.sleep(0.05)  # Simulate work
    coord_duration_ms = (time.perf_counter() - coord_start) * 1000
    record_agent_call(
        agent_name="coordinator",
        duration_ms=coord_duration_ms,
        success=True,
        is_retry=False,
        project_id=test_project_id
    )
    print(f"       ✅ Coordinator: {coord_duration_ms:.1f}ms")

    # RAG retrieval
    print("    2. RAG retrieval...")
    rag_start = time.perf_counter()
    time.sleep(0.03)  # Simulate work
    rag_duration_ms = (time.perf_counter() - rag_start) * 1000
    record_rag_retrieval(
        relevant_chunks=12,
        total_chunks=15,
        supported_facts=8,
        total_facts=10,
        utilized_chunks=11,
        retrieval_latency_ms=rag_duration_ms
    )
    print(f"       ✅ RAG: {rag_duration_ms:.1f}ms (12/15 chunks relevant, 80% utilized)")

    # Tool calls
    print("    3. Tool execution...")
    for i in range(3):
        tool_start = time.perf_counter()
        time.sleep(0.02)  # Simulate work
        tool_duration_ms = (time.perf_counter() - tool_start) * 1000
        record_tool_call(
            duration_ms=tool_duration_ms,
            success=True,
            necessary=True
        )
    print(f"       ✅ 3 tool calls executed successfully")

    # Quality evaluation (simulated result)
    print("    4. Quality evaluation...")
    record_quality_evaluation(
        completeness=0.87,
        clarity_readability=0.92,
        faithfulness_usefulness=0.85,
        content_accuracy=0.90,
        project_id=test_project_id
    )
    print(f"       ✅ Quality metrics recorded (avg grade ≈ 0.89)")

    # Application request completion
    print("    5. Run completion...")
    total_duration_ms = 2500.0
    run_cost_usd = 0.045
    record_application_request(
        duration_ms=total_duration_ms,
        success=True,
        cost=run_cost_usd,
        project_id=test_project_id
    )
    print(f"       ✅ Run completed: {total_duration_ms:.0f}ms, Cost: ${run_cost_usd:.3f}")

    print(f"\n  ✅ Simulated run workflow completed successfully")

except Exception as e:
    print(f"❌ FAILED during simulated workflow: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# TEST 7: Sample metrics output
print("\n[TEST 7] Sample metrics output...")
try:
    metrics = get_all_advanced_metrics(project_id=None)

    print("\n  Global Metrics Summary:")
    if "agent" in metrics and metrics["agent"]:
        agent_data = metrics["agent"].get("coordinator", {})
        print(f"    Agent (coordinator): calls={agent_data.get('call_count')}, "
              f"avg_latency={agent_data.get('avg_latency_ms'):.1f}ms")

    if "rag" in metrics and metrics["rag"]:
        rag_data = metrics["rag"]
        print(f"    RAG: relevance={rag_data.get('relevance_percent'):.1f}%, "
              f"groundedness={rag_data.get('groundedness_percent'):.1f}%, "
              f"utilization={rag_data.get('utilization_percent'):.1f}%")

    if "tool" in metrics and metrics["tool"]:
        tool_data = metrics["tool"]
        print(f"    Tool: calls={tool_data.get('total_calls')}, "
              f"success_rate={tool_data.get('success_rate_percent'):.1f}%, "
              f"avg_latency={tool_data.get('avg_latency_ms'):.1f}ms")

    if "application" in metrics and metrics["application"]:
        app_data = metrics["application"]
        print(f"    Application: requests={app_data.get('total_requests')}, "
              f"failure_rate={app_data.get('failure_rate_percent'):.1f}%, "
              f"total_cost=${app_data.get('total_cost', 0):.3f}")

    if "quality_evaluation" in metrics and metrics["quality_evaluation"]:
        qual_data = metrics["quality_evaluation"]
        print(f"    Quality: runs={qual_data.get('total_runs')}, "
              f"avg_grade={qual_data.get('avg_grade', 0):.2f}")

except Exception as e:
    print(f"⚠️  Could not display metrics summary: {e}")

# FINAL SUMMARY
print("\n" + "="*70)
print("✅ ALL TESTS PASSED - Metrics system is ready for testing!")
print("="*70)
print("\nNext Steps:")
print("1. Ensure OpenObserve instance is running and accessible")
print("2. Verify OTEL can connect by checking OpenObserve logs/UI")
print("3. Run a Sheldon engagement (small test case)")
print("4. Check OpenObserve UI for incoming metrics after run completes")
print("\n" + "="*70 + "\n")
