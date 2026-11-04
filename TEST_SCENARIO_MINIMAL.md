# Minimal Test Scenario: Conversation Summary Saving

## Quick Overview
Test that conversation summaries are saved to database and state is restored correctly. Takes **~3-5 minutes**.

---

## Test Steps

### Step 1: Create Conversation (1 min)
1. Open the application UI
2. Login to a project
3. Create a **new conversation** (or open existing one)
4. Send **1 message** (any content, e.g., "Hello" or "What should we build?")
5. Note the conversation ID from URL

### Step 2: Wait for Idle Detection (2 min)
1. **Don't send any more messages**
2. Keep the conversation open or close it
3. Wait for **2 minutes** 
   - This triggers the idle detection worker
   - Summary will be generated automatically
   - Application will call `_generate_engagement_summary()`

### Step 3: Reopen Conversation
1. Close the conversation (go back to project)
2. Reopen the **same conversation**
3. Check if your message is still there

### Step 4: Verify Success
✅ **Test PASSES if:**
- Original message is visible
- Conversation state is preserved
- No errors in application
- Conversation continues normally

❌ **Test FAILS if:**
- Message is missing
- Shows "Starting fresh" message
- Application crashes
- AttributeError or TypeError in logs

---

## What's Being Tested

| Component | What Happens |
|-----------|--------------|
| **to_dict()** | Called when saving state snapshot to database |
| **from_dict()** | Called when restoring state from database |
| **save_state()** | Called with correct 2 arguments (conv, conv_state) |
| **Idle Detection** | Triggers summary after 2 min of inactivity |
| **Database Save** | Conversation summary stored in conversation_summaries table |
| **JSON Restore** | State restored to JSON file on reopening |

---

## Expected Behavior

### Timeline:
```
T+0 sec:   Send 1 message
T+120 sec: Idle detection worker runs
           - Detects engagement is idle
           - Loads state from JSON
           - Generates summary
           - Calls to_dict() to serialize state
           - Saves to database conversation_summaries table
           
T+121 sec: User closes conversation

T+122 sec: User reopens conversation
           - Loads from database (finds saved summary)
           - Calls from_dict() to deserialize state
           - Calls save_state() with (conv, conv_state)
           - Saves back to JSON file
           - Conversation restores with full context
```

---

## How to Verify (Optional Database Check)

After test passes, check database:

```bash
# Login to database
sqlite3 advise_workbench.db

# Check if summary was saved
SELECT id, project_id, summary_trigger, created_at 
FROM conversation_summaries 
ORDER BY created_at DESC LIMIT 1;

# Should show:
# - id: auto-incremented
# - project_id: your project ID
# - summary_trigger: 'idle_10min' 
# - created_at: recent timestamp
```

---

## Common Issues & Solutions

### Issue: "Message disappeared after reopen"
- **Cause**: State not being saved or restored
- **Fix**: Check if `from_dict()` method exists in conversation_state.py
- **Verify**: `grep "def from_dict" src/memory/short_term/conversation_state.py`

### Issue: "Application crashes during idle detection"
- **Cause**: `to_dict()` or `from_dict()` method missing or broken
- **Fix**: Verify both methods are implemented correctly
- **Check logs**: Look for AttributeError

### Issue: "TypeError: save_state() takes 2 positional arguments but 3 were given"
- **Cause**: Line 1658 in conversation.py still has wrong arguments
- **Fix**: Should be `save_state(conv, conv_state)` not `save_state(pid, conv.id, conv_state)`
- **Verify**: `grep "save_state(conv" src/app/api/projects/conversation.py | head -5`

### Issue: "Took longer than 5 minutes, no idle trigger"
- **Check**: Is the idle detection worker running?
- **Verify**: `grep "idle_detection_worker" src/app/main.py`
- **Alternative**: Manually trigger by closing WebSocket connection

---

## Success Criteria

After completing the test:

| Criterion | Status |
|-----------|--------|
| Message sent and stored | ✅ |
| Can reopen conversation after 2 min | ✅ |
| Original message still visible | ✅ |
| No data loss | ✅ |
| No crashes or errors | ✅ |
| Conversation continues normally | ✅ |

---

## Summary

This minimal test validates:
- ✅ `to_dict()` method works (state serialization)
- ✅ `from_dict()` method works (state deserialization)
- ✅ `save_state()` called with correct arguments
- ✅ Database summary saved after idle detection
- ✅ State restored correctly on reopening
- ✅ No data loss in conversation

**If all messages survive the close-and-reopen, the fixes are working correctly.**
