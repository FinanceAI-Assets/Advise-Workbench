#!/usr/bin/env bash
# Automated grounding demo — validates audit acceptance criteria without a live UI session.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "=== Grounding demo (pytest) ==="
pytest \
  tests/unit/test_source_chunks_grounding.py \
  tests/unit/test_evaluator_pipeline_integrity.py \
  tests/unit/test_evidence_soft_block.py \
  tests/unit/test_phase3_reviewer_trust.py \
  tests/unit/test_remaining_hardening.py \
  -q --tb=line
echo "=== Grounding demo passed ==="
