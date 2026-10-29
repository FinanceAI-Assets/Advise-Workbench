# Ingestion Pipeline - Production Ready Setup Guide

**Status:** ✅ Complete & Optimized  
**Date:** 2026-10-22  
**Version:** 1.0.0

---

## Quick Start for Docker Deployment

### Prerequisites
```bash
# Install Docker & Docker Compose
docker --version    # v24.0+
docker-compose --version  # v2.0+

# Verify Python packages
pip list | grep -E "docling|qdrant|anthropic"
```

### Step 1: Environment Configuration

Create `.env` with all required settings:
```bash
# Copy template
cp .env.example .env

# Set critical values:
JWT_SECRET=<generate-strong-secret>        # Run: make dev.secret
ANTHROPIC_API_KEY=sk-ant-...
SEAWEEDFS_MASTER_URL=http://seaweedfs-master:9333
QDRANT_URL=http://qdrant:6333
DATABASE_URL=postgresql://user:pass@postgres:5432/advise_db
REDIS_URL=redis://redis:6379/0
```

### Step 2: Build & Start Services

```bash
# Build all services
docker-compose build

# Start all services in order
docker-compose up -d

# Wait for services to be ready
sleep 30

# Verify services
docker-compose ps    # All containers should be Running
```

### Step 3: Initialize Database

```bash
# Apply migrations
docker-compose exec backend alembic upgrade head

# Verify migrations
docker-compose exec backend python -c "
from src.core.db.models import (
    TaskFailure, InAppNotification,
    DocumentJob, ParsedDocument, ChunkArchive
)
print('OK: All models imported')
"
```

### Step 4: Verify Pipeline

```bash
# Check Celery workers
docker-compose logs worker | grep "worker ready"

# Check API health
curl http://localhost:8000/health

# Check failure tracking endpoints
curl http://localhost:8000/api/failure-tracking/project/test/summary

# Check all Celery tasks discoverable
docker-compose exec worker celery -A src.workers.celery_app inspect active_queues
```

### Step 5: Test End-to-End

```bash
# 1. Upload a document
curl -X POST http://localhost:8000/api/documents/upload-async \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "project_id=test_project" \
  -F "files=@sample.pdf"

# Response: {"job_ids": ["job_123"]}

# 2. Monitor processing
watch -n 2 'curl -s http://localhost:8000/api/failure-tracking/project/test_project/summary | jq .'

# 3. Check results
curl http://localhost:8000/api/failure-tracking/document/doc_123/failures
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND (React)                            │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTPS
        ┌──────────────▼──────────────┐
        │   FastAPI Backend           │
        │   :8000                     │
        ├─ /api/documents/upload      │
        ├─ /api/failure-tracking/*    │
        └──────┬───────────────────┬──┘
               │                   │
       ┌───────▼────┐      ┌──────▼─────┐
       │ PostgreSQL │      │  Redis     │
       │ :5432      │      │  :6379     │
       └────────────┘      └────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼──┐   ┌───▼──┐   ┌──▼────┐
│Celery│   │Celery│   │Celery │
│Worker│   │Worker│   │Worker │
│  #1  │   │  #2  │   │  #N  │
└───┬──┘   └───┬──┘   └──┬────┘
    │          │         │
    └──────────┼─────────┘
               │
    ┌──────────▼──────────┐
    │  Task Pipeline      │
    ├─ Stage 1.1: Intake  │
    ├─ Stage 1.2: Parse   │
    ├─ Stage 1.3.1: Embed │
    ├─ Stage 1.3.3: Facts │
    └─ Stage 1.3.5: Error │
               │
    ┌──────────┼──────────────┐
    │          │              │
┌───▼──┐  ┌───▼────┐    ┌────▼──┐
│Seaweed│ │ Qdrant │    │Claude │
│  FS   │ │ :6333  │    │  API  │
│       │ │(Vectors│    │       │
└───────┘ │)       │    └───────┘
          └────────┘
```

---

## Database Schema

### 6 Main Tables for Ingestion

```sql
-- Stage 1.1: Document Intake
document_files              -- Original file metadata + SeaweedFS pointers
document_jobs               -- Job tracking (pending/processing/completed/failed)

-- Stage 1.2: Content Extraction
parsed_documents            -- Docling parser output
chunk_archive               -- Semantic chunks (1024 chars, 20% overlap)

-- Stage 1.3.3-5: Knowledge Building & Error Handling
extracted_facts             -- LLM-extracted facts with confidence scores
wiki_pages_final            -- Deduplicated wiki pages (canonical versions)
task_failures               -- Centralized failure tracking
in_app_notifications        -- User notification queue
```

---

## Core Modules (Production-Ready)

### Parsing Pipeline (550 lines)
```
src/core/parsing/
├── docling_parser.py        # Docling extraction service
└── chunking_service.py      # Semantic chunking algorithm
```

### Embeddings & Vector Search (350 lines)
```
src/core/embeddings/
└── embedding_service.py     # BAAI/bge-m3 embeddings (1024D)

src/core/vector_db/
└── qdrant_client.py         # Qdrant vector DB integration
```

### Knowledge Building (650 lines)
```
src/memory/facts/
└── fact_extraction.py       # Claude API fact extraction

src/memory/wiki/
├── wiki_page_generator.py   # Claude API wiki generation
└── deduplication.py         # Embedding-based deduplication
```

### Error Handling (1,070 lines)
```
src/core/error_handling/
└── error_handler.py         # Centralized failure tracking

src/core/notifications/
└── notification_service.py  # User alerts

src/core/observability/
└── openobserve_logger.py    # OpenObserve integration

src/workers/
└── task_orchestration.py    # Failure callbacks
```

### Storage (360 lines)
```
src/core/storage/
├── seaweedfs_client.py      # SeaweedFS file storage
└── document_validator.py    # File validation
```

### Celery Tasks (1,450 lines)
```
src/workers/
├── document_intake_tasks.py        # Stage 1.1 (150 lines)
├── document_parsing_tasks.py       # Stage 1.2 (370 lines)
├── document_embedding_tasks.py     # Stage 1.3.1-2 (330 lines)
└── knowledge_building_tasks.py     # Stage 1.3.3-5 (600 lines)
```

### REST API (650 lines)
```
src/app/api/
├── documents_async.py              # Document upload & status
└── failure_tracking.py             # Failure monitoring dashboard
```

**Total Production Code: ~5,600 lines**

---

## Configuration Settings

### .env Template

```bash
# Core Infrastructure
DATABASE_URL=postgresql://user:pass@postgres:5432/advise_db
REDIS_URL=redis://redis:6379/0
JWT_SECRET=<strong-random-string-min-32-chars>

# Document Storage (Stage 1.1)
SEAWEEDFS_MASTER_URL=http://seaweedfs-master:9333
SEAWEEDFS_FILER_URL=http://seaweedfs-filer:8888
SEAWEEDFS_COLLECTION=advise_workbench
SEAWEEDFS_RETRY_MAX=3

# Document Parsing (Stage 1.2)
DOCLING_PARSER_ENABLED=true
CHUNK_SIZE_CHARACTERS=1024
CHUNK_OVERLAP_CHARACTERS=204
OCR_ENABLED=true

# Embeddings & Vector Search (Stage 1.3.1-2)
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_BATCH_SIZE=32
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=document_chunks
QDRANT_VECTOR_SIZE=1024

# Knowledge Building (Stage 1.3.3-4)
ANTHROPIC_API_KEY=sk-ant-...
FACT_EXTRACTION_ENABLED=true
WIKI_DEDUPLICATION_THRESHOLD=0.85

# Error Handling (Stage 1.3.5)
ERROR_HANDLER_ENABLED=true
ERROR_HANDLER_MAX_RETRIES=3
NOTIFICATION_ENABLED=true

# Observability
OPENOBSERVE_ENABLED=false
OPENOBSERVE_URL=http://openobserve:5080
OTEL_SDK_ENABLED=false
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] All __init__.py files present (8 modules)
- [ ] All imports resolvable
- [ ] Database migrations ready (6 files)
- [ ] .env configured with all values
- [ ] Docker images built successfully
- [ ] Services starting without errors

### During Docker Startup
- [ ] PostgreSQL initializes schema
- [ ] Redis cache ready
- [ ] SeaweedFS cluster healthy
- [ ] Qdrant vector DB ready
- [ ] Celery workers discover all tasks
- [ ] FastAPI health check passes

### Post-Deployment
- [ ] All 4 Celery workers running
- [ ] Failure tracking APIs responding
- [ ] OpenTelemetry tracing (if enabled)
- [ ] Test document upload succeeds
- [ ] Task execution logs appear
- [ ] Embeddings stored in Qdrant

---

## Deployment Guides

See individual deployment docs for each stage:

1. **PARSING_DEPLOYMENT.md** - Stage 1.2 (Docling + Chunking)
2. **EMBEDDINGS_DEPLOYMENT.md** - Stage 1.3.1-2 (BAAI + Qdrant)
3. **KNOWLEDGE_BUILDING_DEPLOYMENT.md** - Stage 1.3.3-4 (Claude API)
4. **ERROR_HANDLING_DEPLOYMENT.md** - Stage 1.3.5 (Error Tracking)
5. **ERROR_HANDLER_INTEGRATION_GUIDE.md** - Wiring error handlers into tasks

---

## Docker Compose Services

```yaml
services:
  # Database
  postgres:
    image: postgres:15-alpine
    ports: [5432:5432]
    volumes: [postgres_data:/var/lib/postgresql/data]

  # Cache & Job Queue
  redis:
    image: redis:7-alpine
    ports: [6379:6379]

  # Distributed File Storage
  seaweedfs-master:
    image: chrislusf/seaweedfs:latest
    command: master -ip=seaweedfs-master
    ports: [9333:9333]

  seaweedfs-volume:
    image: chrislusf/seaweedfs:latest
    command: volume -mserver=seaweedfs-master:9333 -ip=seaweedfs-volume
    ports: [8080:8080]
    depends_on: [seaweedfs-master]

  seaweedfs-filer:
    image: chrislusf/seaweedfs:latest
    command: filer -master=seaweedfs-master:9333
    ports: [8888:8888]
    depends_on: [seaweedfs-master]

  # Vector Database
  qdrant:
    image: qdrant/qdrant:latest
    ports: [6333:6333]
    volumes: [qdrant_data:/qdrant/storage]

  # FastAPI Backend
  backend:
    build: .
    command: uvicorn src.app.main:app --host 0.0.0.0 --port 8000
    ports: [8000:8000]
    depends_on: [postgres, redis, qdrant]
    environment: [DATABASE_URL, REDIS_URL, QDRANT_URL, ...]

  # Celery Workers
  worker:
    build: .
    command: celery -A src.workers.celery_app worker --loglevel=info
    environment: [DATABASE_URL, REDIS_URL, QDRANT_URL, ...]
    depends_on: [postgres, redis]
```

---

## Monitoring

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health
# Response: {"status": "ok"}

# Database readiness
curl http://localhost:8000/health/ready
# Response: {"db": true, "redis": true, "ready": true}

# Celery tasks
docker-compose exec worker celery -A src.workers.celery_app inspect active

# Vector DB health
curl http://localhost:6333/health
# Response: {"ok": true}
```

### Logs

```bash
# Backend logs
docker-compose logs -f backend | grep -E "ERROR|WARN|SUCCESS"

# Worker logs
docker-compose logs -f worker | grep -E "\[TASK\]|\[ERROR\]"

# Database logs
docker-compose logs -f postgres | head -20

# All errors
docker-compose logs | grep ERROR | tail -50
```

### Metrics

```bash
# Task execution times
SELECT task_name, AVG(duration_ms), COUNT(*) 
FROM task_failures 
GROUP BY task_name;

# Failure rates
SELECT error_type, COUNT(*) 
FROM task_failures 
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY error_type;

# Document processing progress
SELECT status, COUNT(*) 
FROM document_jobs 
GROUP BY status;
```

---

## Troubleshooting

### Issue: "No module named 'docling'"
```bash
# Install missing dependencies
pip install -r requirements.txt
docker-compose build --no-cache backend
docker-compose restart backend
```

### Issue: "Qdrant connection refused"
```bash
# Verify Qdrant is running
docker-compose ps | grep qdrant

# Check logs
docker-compose logs qdrant

# Restart
docker-compose restart qdrant
sleep 5
```

### Issue: "Task failed - Anthropic API error"
```bash
# Verify API key
echo $ANTHROPIC_API_KEY

# Update .env
ANTHROPIC_API_KEY=sk-ant-<correct-key>

# Restart workers
docker-compose restart worker
```

### Issue: "Database migrations failed"
```bash
# Check current migration state
docker-compose exec backend alembic current

# Reset to clean state (WARNING: data loss)
docker-compose exec backend alembic downgrade base
docker-compose exec backend alembic upgrade head
```

---

## Success Criteria

After deployment, verify:

- [ ] All Celery workers running: `docker-compose ps | grep worker`
- [ ] All tasks discoverable: `celery inspect active_queues`
- [ ] Database schema complete: `psql -c '\dt'` shows all tables
- [ ] Test document upload succeeds
- [ ] Failure tracking endpoints respond
- [ ] No import errors in logs
- [ ] No database connection errors
- [ ] Qdrant storing embeddings correctly

---

## Next Steps

### Immediate
1. Deploy to Docker
2. Run end-to-end test
3. Monitor for 24 hours
4. Check error tracking dashboard

### Week 1
1. Configure monitoring alerts
2. Set up OpenObserve dashboards
3. Load test (100 docs/hour)
4. Optimize performance if needed

### Ongoing
1. Monitor failure rates
2. Review error logs daily
3. Optimize Celery worker count
4. Scale infrastructure as needed

---

**Production deployment is ready. Follow Docker setup steps above and monitor logs for any issues.**
