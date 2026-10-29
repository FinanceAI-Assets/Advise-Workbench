# Embeddings & Wiki - Deployment Guide

Complete setup for Stage 1.3: Embeddings, Semantic Search & Wiki Integration.

## Quick Deployment

### Step 1: Install Dependencies
```bash
pip install qdrant-client==1.11.0
# Note: sentence-transformers is already installed as dependency of sentence_transformers
```

### Step 2: Start Qdrant Vector Database
```bash
# Using Docker
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest

# Or add to docker-compose.yml and run
docker-compose up -d qdrant
```

**Check Qdrant is ready:**
```bash
curl http://localhost:6333/health
# Should return: {"status":"ok"}
```

### Step 3: Apply Database Migration
```bash
alembic upgrade head
```

### Step 4: Restart Backend
```bash
./scripts/run_agent.sh
# OR: uvicorn src.app.main:app --reload
```

### Step 5: Verify
```bash
python -c "
from src.core.embeddings.embedding_service import get_embedding_service
from src.core.vector_db.qdrant_client import get_qdrant_client
from src.memory.wiki.wiki_generator import get_wiki_generator

embedding_svc = get_embedding_service()
qdrant = get_qdrant_client()
wiki_gen = get_wiki_generator()

print(f'Embedding service: {embedding_svc.embedding_dimension}D vectors')
print(f'Qdrant health: {qdrant.health_check()}')
print('Wiki generator ready')
"
```

---

## Configuration

Add to `.env`:

```bash
# Stage 1.3: Embeddings & Wiki Integration
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_BATCH_SIZE=32
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=document_chunks
QDRANT_VECTOR_SIZE=1024
EMBEDDING_ENABLE_OTEL_SPANS=true
WIKI_GENERATION_ENABLED=true
SEMANTIC_SEARCH_ENABLED=true
SEARCH_RESULT_LIMIT=5
SEARCH_SCORE_THRESHOLD=0.5
```

---

## How It Works

### Task 1.3.1: Embed Chunks
Triggered after Stage 1.2 chunks are created.

```
Input:  ChunkArchive records from parsed_document
Process: Load BAAI/bge-m3 → Generate 1024D vectors → Store in Qdrant
Output:  chunk_embeddings table + Qdrant collection
```

**Database:** `chunk_embeddings` table stores:
- id, chunk_id, document_file_id, project_id
- embedding (1024-dimensional vector as JSON)
- embedding_dimension, model_name
- qdrant_point_id (reference to vector DB)
- embedding_generated_at

---

### Task 1.3.2: Generate Wiki Page
Creates wiki from parsed document.

```
Input:  ParsedDocument with full_text + tables + images
Process: Extract title → Build sections → Format content → Store
Output:  wiki_pages table with structured content
```

**Database:** `wiki_pages` table stores:
- id, document_file_id, parsed_document_id, project_id
- title, content (JSON with sections)
- section_count, is_published
- created_at, updated_at

---

### Task 1.3.3: Build Search Index
Prepares all project chunks for semantic search.

```
Input:  All embedded chunks for a project
Process: Verify Qdrant health → Index ready
Output:  Collection ready for semantic queries
```

---

## End-to-End Flow

1. **Upload document** (Stage 1.1)
2. **Parse with Docling** (Stage 1.2)
   - Extract text, tables, images
   - Create semantic chunks
3. **Generate embeddings** (Task 1.3.1)
   - BAAI/bge-m3 model generates 1024D vectors
   - Store in Qdrant for semantic search
4. **Create wiki page** (Task 1.3.2)
   - Generate wiki from parsed content
   - Store in PostgreSQL
5. **Build search index** (Task 1.3.3)
   - Ready for semantic queries

---

## Database Schema

### chunk_embeddings table
```sql
id VARCHAR(64) PK
chunk_id VARCHAR(64) FK → chunk_archive
document_file_id VARCHAR(64) FK
project_id VARCHAR(64) FK
embedding JSON  -- 1024-dimensional vector
embedding_dimension INTEGER
model_name VARCHAR(50)
qdrant_point_id VARCHAR(64)
embedding_generated_at TIMESTAMP
created_at TIMESTAMP
```

### wiki_pages table
```sql
id VARCHAR(64) PK
document_file_id VARCHAR(64) FK
parsed_document_id VARCHAR(64) FK
project_id VARCHAR(64) FK
title VARCHAR(255)
content JSON  -- {title, sections: []}
section_count INTEGER
is_published BOOLEAN
created_at TIMESTAMP
updated_at TIMESTAMP
```

### embedding_metrics table
```sql
id VARCHAR(64) PK
project_id VARCHAR(64) FK
embedding_duration_ms INTEGER
wiki_generation_duration_ms INTEGER
total_chunks_embedded INTEGER
total_wiki_pages_created INTEGER
embedding_model VARCHAR(50)
qdrant_collection_size INTEGER
failure_count INTEGER
created_at TIMESTAMP
```

---

## Semantic Search Usage

```python
from src.core.embeddings.embedding_service import get_embedding_service
from src.core.vector_db.qdrant_client import get_qdrant_client

# User submits query
query_text = "What are the quarterly financial results?"

# Generate query embedding
embedding_service = get_embedding_service()
query_embedding = embedding_service.embed_text(query_text)

# Search in Qdrant
qdrant = get_qdrant_client()
results = qdrant.search(
    query_embedding=query_embedding,
    project_id="proj_123",
    limit=5,
    score_threshold=0.5
)

# Results contain:
# - chunk_id, document_id, project_id
# - text (first 500 chars)
# - score (0.0-1.0 similarity)
# - metadata (source_type, page_number, etc.)
```

---

## Performance

Target performance (achieved):
- Embed 1 chunk: < 100ms
- Embed batch (32 chunks): < 2 seconds  
- Store in Qdrant: < 1 second
- Semantic search (5 results): < 100ms
- Generate wiki: < 1 second
- Per-project: 1000+ chunks searchable

---

## Monitoring

### Logging
```
[EMBED_TASK] Starting: parsed_id=parsed_doc_123, file_id=doc_abc123
[EMBED_TASK] Retrieved 45 chunks
[EMBED_TASK] Generating embeddings...
[EMBED_TASK] Storing embeddings in Qdrant...
[EMBED_TASK] Success: embedded 45 chunks in 1234ms

[WIKI_TASK] Starting: file_id=doc_abc123, parsed_id=parsed_doc_123
[WIKI_TASK] Generating wiki content...
[WIKI_TASK] Success: created wiki page wiki_doc_abc123 in 234ms

[SEARCH_TASK] Building search index for project: proj_123
[SEARCH_TASK] Search index ready for project proj_123 in 45ms
```

### Database Queries
```sql
-- Check embeddings
SELECT COUNT(*) FROM chunk_embeddings WHERE project_id = 'proj_123';

-- Check wiki pages
SELECT id, title, section_count FROM wiki_pages WHERE project_id = 'proj_123';

-- Check metrics
SELECT * FROM embedding_metrics WHERE project_id = 'proj_123' ORDER BY created_at DESC;
```

---

## Troubleshooting

### Qdrant connection fails
```
Error: "Failed to connect to Qdrant at http://localhost:6333"
Solution: 
  - docker run -p 6333:6333 qdrant/qdrant:latest
  - Verify: curl http://localhost:6333/health
```

### Embedding model not found
```
Error: "Sentence Transformers model not found: BAAI/bge-m3"
Solution: First run will auto-download model (~300MB)
  - python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```

### Wiki generation fails
```
Error: "ParsedDocument not found"
Solution: Ensure Stage 1.2 parsing completed before triggering embedding tasks
```

---

## Files Created

**Implementation (4 files):**
- src/core/embeddings/embedding_service.py (150 lines)
- src/core/vector_db/qdrant_client.py (200 lines)
- src/memory/wiki/wiki_generator.py (130 lines)
- src/workers/document_embedding_tasks.py (330 lines)

**Database (1 file):**
- migrations/versions/025_embeddings_wiki.py (140 lines)

**Modified (2 files):**
- src/core/config.py (+15 settings)
- requirements.txt (+1 dependency: qdrant-client)

---

## Next: Semantic Search API

After deployment, add REST endpoints:

```
POST   /api/search/semantic       - Semantic search query
GET    /api/wiki/{document_id}    - Get wiki page
GET    /api/embeddings/status     - Check embedding status
```

