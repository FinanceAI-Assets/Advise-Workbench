# Knowledge Building - Complete Deployment Guide

Full implementation of Stage 1.3: LLM-powered fact extraction, wiki generation, and deduplication.

## Complete Workflow

```
Chunks (from Stage 1.2)
  ↓
Task 1.3.1: Extract Facts (Claude API)
  - Extract: roles, activities, risks, metrics, dependencies
  - Store with confidence scores in extracted_facts table
  ↓
Task 1.3.2: Generate Wiki Pages (Claude API)
  - Group facts by entity
  - Generate wiki for each entity
  - Store drafts in wiki_pages_draft table
  ↓
Task 1.3.3: Deduplicate Wiki (Embeddings)
  - Embed wiki pages (BAAI/bge-m3)
  - Find similar pages (cosine > 0.85)
  - Merge duplicates → canonical versions
  - Store finals in wiki_pages_final table
  ↓
Task 1.3.4: Embed for Search (Embeddings)
  - Generate embeddings for final wiki pages
  - Store in Qdrant "wiki_pages" collection
  - Mark wiki as published
  ↓
Complete Knowledge Base Ready for Semantic Search
```

---

## Quick Deployment

### Step 1: Install Dependencies
```bash
pip install scikit-learn==1.6.0 qdrant-client==1.11.0
```

### Step 2: Configure Claude API
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# Or add to .env:
# ANTHROPIC_API_KEY=sk-ant-...
```

### Step 3: Start Qdrant (if not running)
```bash
docker run -p 6333:6333 qdrant/qdrant:latest &
```

### Step 4: Apply Database Migration
```bash
alembic upgrade head
```

### Step 5: Restart Backend
```bash
./scripts/run_agent.sh
```

### Step 6: Verify
```bash
python -c "
from src.memory.facts.fact_extraction import get_fact_extraction_service
from src.memory.wiki.wiki_page_generator import get_wiki_generator_service
from src.memory.wiki.deduplication import get_deduplication_service

print('✓ Fact extraction ready')
print('✓ Wiki generation ready')
print('✓ Deduplication ready')
"
```

---

## Configuration

Add to `.env`:

```bash
# Stage 1.3: Knowledge Building
ANTHROPIC_API_KEY=sk-ant-...
FACT_EXTRACTION_ENABLED=true
WIKI_DEDUPLICATION_THRESHOLD=0.85
KNOWLEDGE_EXTRACTION_MAX_RETRIES=2
KNOWLEDGE_GENERATION_BATCH_SIZE=10
```

---

## Task Details

### Task 1.3.1: Extract Facts

**Input:** Chunks from chunk_archive
**Process:** 
1. For each chunk, call Claude API
2. Extract: roles, activities, risks, metrics, dependencies
3. Store each with confidence score (0-1)

**Output:** extracted_facts table
```sql
id, parsed_document_id, project_id, fact_type, fact_name, confidence_score, source_context
```

**Retry:** 2x on LLM failure

---

### Task 1.3.2: Generate Wiki Pages

**Input:** extracted_facts from previous task
**Process:**
1. Group facts by type and name
2. For each entity, call Claude API: "Write wiki page"
3. Store drafts with source citations

**Output:** wiki_pages_draft table
```sql
id, parsed_document_id, project_id, entity_name, entity_type, content, source_facts
```

**Retry:** 2x on LLM failure

---

### Task 1.3.3: Deduplicate Wiki

**Input:** wiki_pages_draft
**Process:**
1. Generate 1024D embeddings for each wiki page
2. Compute cosine similarity between all pairs
3. Find groups with similarity > 0.85
4. Merge each group → keep first as canonical
5. Store final versions

**Output:** wiki_pages_final table
```sql
id, project_id, entity_name, entity_type, content, aliases, merge_info, is_published
```

---

### Task 1.3.4: Embed for Search

**Input:** wiki_pages_final (unpublished)
**Process:**
1. Generate 1024D embeddings for wiki pages
2. Store in Qdrant "wiki_pages" collection
3. Store metadata in embeddings_metadata table
4. Mark wikis as published

**Output:** 
- Qdrant collection: "wiki_pages" with 1024D vectors
- embeddings_metadata table with tracking info
- wiki_pages_final.is_published = true

---

## Database Schema

### extracted_facts
```sql
id VARCHAR(64) PK
parsed_document_id FK
project_id FK
fact_type VARCHAR(50)  -- role, activity, risk, metric, dependency
fact_name VARCHAR(255)  -- Extracted name
fact_value JSON  -- Full structure
confidence_score FLOAT  -- 0.0-1.0
source_context VARCHAR(500)  -- Where found
created_at TIMESTAMP
```

### wiki_pages_draft
```sql
id VARCHAR(64) PK
parsed_document_id FK
project_id FK
entity_name VARCHAR(255)
entity_type VARCHAR(50)
content TEXT  -- Markdown
source_facts JSON  -- Facts used
is_deduplicated BOOLEAN
created_at TIMESTAMP
```

### wiki_pages_final
```sql
id VARCHAR(64) PK
project_id FK
entity_name VARCHAR(255)  -- Canonical
entity_type VARCHAR(50)
content TEXT
aliases JSON  -- Alternative names
source_facts JSON
merge_info JSON  -- {is_canonical, merged_from[], merge_count}
is_published BOOLEAN
created_at TIMESTAMP
updated_at TIMESTAMP
```

### embeddings_metadata
```sql
id VARCHAR(64) PK
wiki_id FK → wiki_pages_final
project_id FK
embedding_model VARCHAR(50)  -- BAAI/bge-m3
embedding_dimension INTEGER  -- 1024
qdrant_collection VARCHAR(50)  -- wiki_pages
qdrant_point_id VARCHAR(64)
created_at TIMESTAMP
```

### knowledge_metrics
```sql
id VARCHAR(64) PK
project_id FK
extraction_duration_ms INTEGER
wiki_generation_duration_ms INTEGER
deduplication_duration_ms INTEGER
total_facts_extracted INTEGER
total_wiki_generated INTEGER
total_wiki_final INTEGER
duplicates_removed INTEGER
failure_count INTEGER
created_at TIMESTAMP
```

---

## Monitoring

### Logging
```
[EXTRACT_FACTS] Starting: parsed_id=..., project=...
[EXTRACT_FACTS] Retrieved X chunks
[EXTRACT_FACTS] Extracting facts with Claude API...
[EXTRACT_FACTS] Success: extracted Y facts in Zms

[WIKI_GENERATE] Starting: parsed_id=..., project=...
[WIKI_GENERATE] Retrieved X facts
[WIKI_GENERATE] Grouped into Y entities
[WIKI_GENERATE] Generating wiki pages with Claude...
[WIKI_GENERATE] Success: created Y wiki pages in Zms

[DEDUP_WIKI] Starting: project=...
[DEDUP_WIKI] Processing X wiki pages
[DEDUP_WIKI] Generating embeddings...
[DEDUP_WIKI] Finding duplicates...
[DEDUP_WIKI] Success: X original → Y final (Z removed) in Wms

[WIKI_EMBED] Starting: project=...
[WIKI_EMBED] Processing X wiki pages
[WIKI_EMBED] Generating embeddings...
[WIKI_EMBED] Storing in Qdrant...
[WIKI_EMBED] Success: embedded X wiki pages in Ems
```

### Database Queries
```sql
-- Check extracted facts
SELECT fact_type, COUNT(*) FROM extracted_facts 
WHERE project_id = 'proj_123' 
GROUP BY fact_type;

-- Check wiki drafts
SELECT COUNT(*) FROM wiki_pages_draft 
WHERE project_id = 'proj_123' AND is_deduplicated = false;

-- Check final wiki
SELECT entity_type, COUNT(*) FROM wiki_pages_final 
WHERE project_id = 'proj_123' AND is_published = true 
GROUP BY entity_type;

-- Check metrics
SELECT * FROM knowledge_metrics 
WHERE project_id = 'proj_123' 
ORDER BY created_at DESC;
```

---

## Search Usage

```python
from src.core.vector_db.qdrant_client import get_qdrant_client
from src.core.embeddings.embedding_service import get_embedding_service

# User query
query = "What are the main risks?"

# Generate embedding
embedder = get_embedding_service()
query_embedding = embedder.embed_text(query)

# Search in Qdrant (wiki_pages collection)
qdrant = get_qdrant_client(collection_name="wiki_pages")
results = qdrant.search(
    query_embedding=query_embedding,
    project_id="proj_123",
    limit=5,
    score_threshold=0.5
)

# Results contain: wiki_id, entity_name, content, score, etc.
```

---

## Files Created

**Implementation (4 files):**
- src/memory/facts/fact_extraction.py (250 lines)
- src/memory/wiki/wiki_page_generator.py (180 lines)
- src/memory/wiki/deduplication.py (220 lines)
- src/workers/knowledge_building_tasks.py (600 lines)

**Database (1 file):**
- migrations/versions/026_knowledge_building.py (180 lines)

**Modified (2 files):**
- src/core/config.py (+8 settings)
- requirements.txt (+1 dependency: scikit-learn)

---

## Complete Stage 1.3 Workflow

All 4 tasks are fully implemented, tested, and production-ready:
- ✅ Extract facts with confidence scores
- ✅ Generate wiki pages with Claude
- ✅ Deduplicate using embeddings
- ✅ Store final wiki + embeddings in Qdrant

