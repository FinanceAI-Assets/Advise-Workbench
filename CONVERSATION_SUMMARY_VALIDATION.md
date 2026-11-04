# Conversation Summary: Save Sequence Validation

## ✅ FIXED: JSON → Database Save Order

All conversation summary saves now follow the correct sequence:
1. **Save to JSON file FIRST** (source of truth)
2. **Save to database SECOND** (persistent storage)

---

## 🎯 Three Save Scenarios Fixed:

### 1. **Idle Detection Trigger** ✅ FIXED
**File:** `src/workflows/conversation_summary_worker.py`

**Trigger:** 2+ minutes of inactivity detected by background worker

**Sequence:**
```
Idle Detection Worker (every 2 min)
    ↓
[1/2] Load conversation state from JSON
[1/2] Generate 2-3 line summary
[1/2] Update conversation_state.conversation_summary field
[1/2] Save state to JSON file
    ↓ (only if JSON save succeeds)
    ↓
[2/2] Create ConversationSummary database record
[2/2] UPSERT to conversation_summaries table
```

**Verification Points:**
- ✅ `json_saved` flag ensures JSON success before DB attempt
- ✅ Error logged if JSON save fails (DB skipped)
- ✅ Detailed logging: "[1/2] JSON save" and "[2/2] DB save"

---

### 2. **Session Close Trigger** ✅ FIXED
**File:** `src/app/api/projects/conversation.py` (line ~3330)
**Endpoint:** `POST /{pid}/close-engagement-session`

**Trigger:** User navigates away from engagement (if idle > 5 minutes)

**Sequence:**
```
User closes engagement session
    ↓
Session metadata collected
    ↓
IF idle_duration > 300 seconds:
    ↓
    [1/2] Generate summary
    [1/2] Load conversation state from JSON
    [1/2] Update conversation_summary field
    [1/2] Save to JSON file
        ↓ (only if JSON save succeeds)
        ↓
    [2/2] Create ConversationSummary record
    [2/2] UPSERT to conversation_summaries table
    ↓
Return status: "closed_with_summary"
```

**Verification Points:**
- ✅ Conditional: only attempts if JSON save succeeds
- ✅ Error handling for both JSON and DB failures
- ✅ Returns appropriate status code

---

### 3. **User Navigation Away** ✅ FIXED
**File:** `src/app/api/projects/conversation.py` (line ~3150)
**Endpoint:** `POST /{pid}/conversation/close`

**Trigger:** User navigates away from conversation/engagement

**Sequence:**
```
User navigates away
    ↓
Close session & get metadata
    ↓
Query latest conversation
    ↓
[1/2] Generate summary (trigger: "user_navigation_away")
[1/2] Load conversation state from JSON
[1/2] Update conversation_summary field
[1/2] Save to JSON file
    ↓ (only if JSON save succeeds)
    ↓
[2/2] Create ConversationSummary record
[2/2] UPSERT to conversation_summaries table
```

**Verification Points:**
- ✅ JSON saved before database attempt
- ✅ Proper error handling with json_saved flag
- ✅ Logging shows exact sequence: "[1/2]" then "[2/2]"

---

## 📋 Detailed Save Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│        CONVERSATION SUMMARY GENERATION TRIGGERED        │
│  (Idle Detection / Session Close / User Navigation)     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
          ┌──────────────────────┐
          │  Generate Summary    │
          │   (2-3 lines text)   │
          └──────────┬───────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ↓                         ↓
    ┌────────────┐         ┌──────────────┐
    │ STEP 1     │         │ STEP 2       │
    │ JSON FILE  │         │ DATABASE     │
    │ (Source    │         │ (Persistent  │
    │  of Truth) │         │  Storage)    │
    └────────────┘         └──────────────┘
        │                         │
        ├─ Load state            │
        ├─ Set .conversation_    │
        │  summary field         │
        ├─ save_state()          │
        │                         │
        └─ json_saved = true     │
             │                    │
             └────────┬───────────┘
                      │
                      ↓
             (JSON save successful?)
                      │
          ┌───────────┴───────────┐
          │ YES                   │ NO
          ↓                       ↓
    ┌──────────┐          ┌─────────────┐
    │ Proceed  │          │ ABORT DB    │
    │ to DB    │          │ Save (skip) │
    │ Save     │          │ Log ERROR   │
    └────┬─────┘          └─────────────┘
         │
         ↓
    ┌──────────────────────┐
    │ Create Summary       │
    │ Record               │
    │                      │
    │ _upsert_            │
    │ conversation_        │
    │ summary(db, summary) │
    └──────────┬───────────┘
               │
               ↓
         ┌──────────┐
         │ Complete │
         │   ✅     │
         └──────────┘
```

---

## 🔍 Verification Checklist:

- [x] Idle detection saves JSON first, then DB
- [x] Session close saves JSON first, then DB  
- [x] User navigation saves JSON first, then DB
- [x] json_saved flag prevents DB save if JSON fails
- [x] Error logging shows exact sequence
- [x] Logs tagged with [1/2] and [2/2] for clarity
- [x] ConversationState model includes conversation_summary field
- [x] to_json() includes conversation_summary
- [x] to_dict() includes conversation_summary
- [x] from_dict() loads conversation_summary
- [x] default_state() initializes conversation_summary

---

## 📊 Log Output Example:

```
[DEBUG] [1/2] Saved conversation_summary to JSON file for p_12345
[DEBUG] [2/2] Saved summary to database for p_12345
[INFO] Summary saved for engagement p_12345 (idle 120s) - JSON→DB sequence complete
```

---

## ✅ Test Procedure:

1. **Restart application** with new code
2. **Send a conversation message**
3. **Wait 2 minutes** (idle detection)
4. **Check both locations:**

   **JSON File:**
   ```bash
   cat workspace/engagement_p_*/conversation_*.json | grep conversation_summary
   ```
   Should output: `"conversation_summary": "Discovered: ... | Decided: ... | Status: ..."`

   **Database:**
   ```sql
   SELECT summary_text FROM conversation_summaries 
   ORDER BY created_at DESC LIMIT 1;
   ```
   Should match the JSON summary text

---

## 🎉 Validation Complete:

All three save triggers now correctly implement:
1. **JSON file save FIRST** (updates source of truth)
2. **Database save SECOND** (updates persistent storage)
3. **Error handling** (prevents partial saves)
4. **Detailed logging** (shows exact sequence)

