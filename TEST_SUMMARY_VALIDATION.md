# Test: LLM-Based Conversation Summary Validation

## Goal
Validate that conversation summaries are generated using actual LLM summarization (not metadata extraction) and that they are used when Sheldon continues the conversation after an idle period.

---

## Test Scenario: Build a Dashboard Project

### Phase 1: Create and Develop Conversation (5 min)

1. **Start Application**
   ```bash
   ./scripts/run_agent.sh
   ```
   - Open http://localhost:8000 in browser
   - Login to your project (or create test project)

2. **Create Conversation with Sheldon**
   - Click "New Conversation"
   - Start with message: "I want to build an interactive financial dashboard for my team"
   - Wait for Sheldon's response

3. **Send Development Messages** (at least 5-10 messages over 2-3 minutes)
   ```
   User: "We need real-time stock price updates"
   Sheldon: [responds with options]
   
   User: "Should we use React or Vue?"
   Sheldon: [recommends React with D3]
   
   User: "How do we handle data refresh?"
   Sheldon: [suggests WebSocket or polling]
   
   User: "Let's go with WebSocket for real-time"
   Sheldon: [confirms, suggests architecture]
   
   User: "What about authentication?"
   Sheldon: [proposes JWT-based approach]
   ```

4. **Note the Conversation ID**
   - Look at URL: `http://localhost:8000/projects/{pid}/conversation/{conv_id}`
   - Save both `pid` and `conv_id`

---

### Phase 2: Wait for Idle Summary Generation (2 min)

5. **Leave Conversation Idle**
   - Keep the page open OR close it
   - Do NOT send any more messages
   - Wait exactly 2 minutes

6. **What's Happening in Background**
   - Background worker detects idle engagement
   - `check_idle_engagements_and_summarize()` runs
   - `_generate_conversation_summary_llm()` is called
   - LLM summarizes all 5-10 messages into 2-4 lines
   - Summary saved to database and JSON state file

---

### Phase 3: Verify Summary in Database (1 min)

7. **Check Database for Generated Summary**
   ```bash
   # Connect to PostgreSQL (using DATABASE_URL from .env)
   psql $DATABASE_URL
   # Or if you have alias: psql aw_shared
   ```

   ```sql
   SELECT 
     id, 
     project_id, 
     summary_text, 
     summary_trigger, 
     created_at
   FROM conversation_summaries 
   WHERE project_id = '{pid}'
   ORDER BY created_at DESC 
   LIMIT 1;
   ```

   **Expected Output:**
   ```
   id: summary_{pid}
   project_id: {pid}
   summary_text: "User wants to build a financial dashboard with real-time stock updates.
                   Selected React with D3 for frontend and WebSocket for real-time data.
                   Decided on JWT authentication. Next: design architecture and APIs."
   summary_trigger: idle_10min
   created_at: 2026-11-04 14:35:22
   ```

   ⚠️ **IMPORTANT**: Summary should be 2-4 lines of **natural language**, NOT metadata like:
   - ❌ "Discovered: client, outcome | Status: exploring"
   - ✅ "User wants to build a dashboard. Decided on React/D3 and WebSocket. Next: define APIs."

8. **Check State Snapshot**
   ```sql
   -- PostgreSQL: use ->> for JSON access
   SELECT 
     (state_snapshot_json::jsonb ->> 'conversation_summary') AS summary
   FROM conversation_summaries 
   WHERE project_id = '{pid}' 
   LIMIT 1;
   ```

   Should return the same summary text.

---

### Phase 4: Reopen Conversation and Test Usage (3 min)

9. **Reopen the Conversation**
   - Go back to: `http://localhost:8000/projects/{pid}/conversation/{conv_id}`
   - Original messages should still be visible
   - Check browser console for any errors

10. **Send Follow-Up Message**
    ```
    User: "Can we add user preferences for customization?"
    ```

11. **Monitor What Happens**
    - Check backend logs:
      ```
      grep "Session summary (auto-generated" logs/*.log
      grep "Route decision" logs/*.log
      ```
    - Look for evidence that router saw and used the summary

---

### Phase 5: Verify Summary is Being Used (2 min)

12. **Check Sheldon's Response**
    - Sheldon's response should reference the previous discussion
    - Should mention: dashboard, React, D3, WebSocket, JWT, preferences
    - Should NOT say "Starting fresh" or "Let me understand what you need"
    - Should continue building on prior decisions

13. **Check Application Logs for Router Context**
    ```
    # Look for:
    # "Session summary (auto-generated on idle/checkpoint): ..."
    # This proves summary was passed to router
    
    tail -100 logs/conversation.log | grep -A5 "Session summary"
    ```

14. **Expected Log Output** (in conversation.log or stderr):
    ```
    [DEBUG] Route decision made considering:
    - Session summary: "User wants to build a financial dashboard..."
    - Current state: exploring/discovering
    - Conversation history: 10 messages
    - Result: intent=discovery_answer, confidence=0.92
    ```

---

## Success Criteria

✅ **Test PASSES if:**
- [ ] Summary in database is 2-4 lines of natural language (not metadata)
- [ ] Summary captures main topics: dashboard, React, D3, WebSocket, JWT
- [ ] Summary restored when conversation reopened
- [ ] Logs show "Session summary (auto-generated...)" in router context
- [ ] Sheldon's follow-up response is contextual (mentions prior decisions)
- [ ] No errors in application logs

❌ **Test FAILS if:**
- [ ] Summary is empty or metadata-like ("Discovered: X | Status: Y")
- [ ] Summary not found in database (maybe idle detection didn't run)
- [ ] Logs don't show summary being passed to router
- [ ] Sheldon responds as if conversation is new
- [ ] Application crashes or errors during restoration

---

## Debugging

### If Summary is Empty
```bash
# Check if idle detection ran
grep -i "idle_engagement" logs/*.log

# Check if summary generation was attempted
grep -i "_generate_engagement_summary" logs/*.log

# Check for LLM errors
grep -i "gateway\|llm\|claude" logs/*.log | tail -20
```

### If Summary Not Passed to Router
```bash
# Check router function signature
grep -A10 "def route_turn" src/workflows/task_router/conversation_router.py

# Verify parameter is being passed
grep "conversation_summary=" src/app/api/projects/conversation.py
```

### If Summary Not Restored
```bash
# Check state file
cat workspace/{pid}/conversation_state/{conv_id}.json | jq '.conversation_summary'

# Should see the actual summary text, not empty string
```

---

## Files to Monitor

- **Database**: PostgreSQL `aw_shared` - `conversation_summaries` table
  ```bash
  psql $DATABASE_URL
  SELECT COUNT(*) FROM conversation_summaries;
  SELECT * FROM conversation_summaries WHERE project_id = '{pid}';
  ```
- **State File**: `workspace/{pid}/conversation_state/{conv_id}.json` - `conversation_summary` field
  ```bash
  cat workspace/{pid}/conversation_state/{conv_id}.json | jq '.conversation_summary'
  ```
- **Logs**: `logs/conversation.log`, `logs/worker.log`, `logs/router.log`
- **Code**: 
  - `src/workflows/conversation_summary_worker.py` - summary generation
  - `src/workflows/task_router/conversation_router.py` - router context
  - `src/app/api/projects/conversation.py` - integration point

---

## Optional: Manual LLM Test

To verify the LLM summarization works before running full test:

```python
# In Python shell
import asyncio
from src.workflows.conversation_summary_worker import _generate_conversation_summary_llm

transcript = """
USER: I want to build an interactive financial dashboard
ASSISTANT: Great! What features are most important?
USER: Real-time stock prices and portfolio tracking
ASSISTANT: I recommend React with D3.js for visualization and WebSocket for real-time updates
USER: Sounds good. What about authentication?
ASSISTANT: JWT tokens stored in httpOnly cookies is the standard approach
"""

result = asyncio.run(_generate_conversation_summary_llm(transcript))
print("Generated Summary:")
print(result)
```

Expected output:
```
User wants to build a financial dashboard with real-time stock prices and portfolio tracking.
Selected React with D3.js for visualization and WebSocket for real-time updates.
Decided on JWT-based authentication. Next: design system architecture.
```

---

## Timeline Summary

```
T+0 sec:    Send first message, start conversation
T+30 sec:   Send 4-9 more messages
T+120 sec:  Idle detection triggers
            ↓ LLM summarizes conversation
            ↓ Summary saved to database
T+121 sec:  Close conversation (or leave it)
T+150 sec:  Reopen conversation
            ↓ Summary restored from database
            ↓ State file updated with summary
T+151 sec:  Send follow-up message
            ↓ Router includes summary in context
            ↓ Sheldon responds contextually
```

---

## Next Steps After Validation

If this test passes:
1. ✅ LLM-based summarization is working
2. ✅ Summary is persisted correctly
3. ✅ Summary is being used by router
4. ✅ Sheldon has context across sessions

If any test fails:
1. Check logs for error messages
2. Review the debugging section above
3. Verify all code changes were applied correctly
4. Check LLM gateway connectivity
