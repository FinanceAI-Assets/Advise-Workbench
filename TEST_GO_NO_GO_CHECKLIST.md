# 🎯 TEST GO/NO-GO CHECKLIST

## ✅ PRE-TEST (Before Running Test)

### Code Changes Applied:
- [x] Activity tracking added to `_record_activity_sync()` and `_start_session_sync()`
- [x] Activity tracking added to `start_turn()` endpoint
- [x] Activity tracking added to `decisions` endpoint background mode
- [x] Activity tracking added to `outline` endpoint background mode
- [x] JSON→DB save sequence fixed in idle detection worker
- [x] JSON→DB save sequence fixed in session close endpoint
- [x] JSON→DB save sequence fixed in user navigation endpoint
- [x] `conversation_summary` field added to ConversationState
- [x] Database idle timeout updated to 120 seconds (2 minutes)
- [x] 80 engagement records updated to 120-second timeout

### System Status:
- [ ] Application restarted with new code
- [ ] Application started successfully (no startup errors)
- [ ] Idle detection worker started (check logs for: "Conversation idle detection worker started")
- [ ] Database connection working
- [ ] Backend API responding

### Verification Commands:
```bash
# Check if idle timeout is 2 minutes
grep "default=120" src/core/db/models.py

# Check if activity tracking in start_turn
grep -A5 "_start_session_sync(pid)" src/app/api/projects/conversation_turns.py

# Check if JSON→DB sequence in worker
grep "\[1/2\]\|\[2/2\]" src/workflows/conversation_summary_worker.py

# Verify conversation_summary field in state
grep "conversation_summary.*str" src/memory/short_term/conversation_state.py
```

---

## 🎬 STEP-BY-STEP TEST EXECUTION

### **STEP 1: Send Message (Expected: ~1 min)**
```
1. Open application UI (localhost:3000)
2. Login with your credentials
3. Open or create a project
4. Create NEW conversation (or open existing)
5. Send message: "Hello Sheldon, I want to discuss a proposal"
6. Note conversation ID from URL: /{pid}/conversation/{conv_id}
7. Wait for Sheldon's reply

SUCCESS INDICATORS:
✓ Message appears in conversation
✓ Sheldon responds with greeting
✓ No errors in console/logs
```

### **STEP 2: Wait for Idle Detection (Expected: 2 min)**
```
1. DO NOT send any more messages
2. DO NOT close the conversation yet
3. Set a timer for 2 MINUTES (120 seconds)
4. Keep the conversation open (or close it - both work)
5. Monitor application logs

WATCH FOR IN LOGS:
✓ [DEBUG] [1/2] Saved conversation_summary to JSON file for p_xxxx
✓ [DEBUG] [2/2] Saved summary to database for p_xxxx
✓ [INFO] Summary saved for engagement p_xxxx... JSON→DB sequence complete

FAILURE INDICATORS:
✗ No summary logs appear after 2 minutes
✗ [ERROR] CRITICAL: Failed to save conversation_summary
✗ Application crash or errors in logs
```

### **STEP 3: Reopen Conversation (Expected: ~30 sec)**
```
1. Close the conversation (click back/close button)
2. Go back to project view
3. Wait 1-2 seconds
4. Reopen the SAME conversation

SUCCESS INDICATORS:
✓ Conversation opens successfully
✓ Original message appears: "Hello Sheldon, I want to discuss a proposal"
✓ Sheldon's reply appears
✓ No "Starting fresh" or error messages
✓ Conversation state is complete
✓ No crashes or errors in logs
```

### **STEP 4: Verify in Database (Expected: ~1 min)**
```
OPTION A - PostgreSQL CLI:
psql -U aw_shared -h 172.31.65.20 -d aw_shared
SELECT summary_text, summary_trigger, idle_duration_seconds, created_at 
FROM conversation_summaries 
WHERE project_id = 'p_xxxx' 
ORDER BY created_at DESC LIMIT 1;

OPTION B - Python:
python -c "
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    result = conn.execute(text('SELECT summary_text FROM conversation_summaries ORDER BY created_at DESC LIMIT 1'))
    print(result.scalar())
"

SUCCESS INDICATORS:
✓ Summary text appears: "Discovered: ... | Decided: ... | Status: ..."
✓ summary_trigger = "idle_10min" or "user_navigation_away"
✓ idle_duration_seconds >= 120
✓ created_at = recent timestamp
```

### **STEP 5: Verify in JSON File (Expected: ~30 sec)**
```
Find the JSON file:
workspace/engagement_p_xxxx/conversation_conv_yyyy.json

Command to check:
cat workspace/engagement_p_*/conversation_*.json | grep "conversation_summary"

SUCCESS INDICATORS:
✓ Contains: "conversation_summary": "Discovered: ... | Decided: ... | Status: ..."
✓ JSON file updated around same time as Step 2
```

---

## 📊 TEST RESULT DETERMINATION

### ✅ TEST PASSES IF:
1. Message sent successfully
2. No errors after 2 minutes (idle detection runs)
3. Logs show: "[1/2]" then "[2/2]" sequence
4. Conversation reopens with original message intact
5. Summary appears in both database AND JSON file
6. No crashes or "Starting fresh" messages
7. Conversation continues normally

### ❌ TEST FAILS IF:
1. Original message missing after reopen → State serialization issue
2. Application crashes → Code error or exception
3. "Starting fresh" message appears → State not restored
4. No summary in database → Generation/save failed
5. Summary only in database (not JSON) → Sequence wrong
6. Error logs with AttributeError/TypeError → Code issue
7. No logs for [1/2] or [2/2] → Activity tracking failed

---

## 📝 ISSUE RESOLUTION GUIDE

### Issue: "No summary in database after 2 minutes"
**Check:**
1. Idle detection worker running? → Check logs for "worker started"
2. last_activity_at updated? → SELECT last_activity_at FROM engagement_meta
3. enable_idle_detection = true? → SELECT enable_idle_detection FROM engagement_meta
4. Timeout is 120 seconds? → SELECT idle_timeout_seconds FROM engagement_meta

### Issue: "Message missing after reopen"
**Check:**
1. State saved to JSON? → cat workspace/.../conversation_*.json
2. State has conversation_summary field? → grep conversation_summary
3. from_dict() working? → Check code for deserialization logic
4. No errors in logs? → Look for CRITICAL/ERROR

### Issue: "Summary only in database, not in JSON"
**Check:**
1. JSON save sequence correct? → Look for [1/2] in logs
2. json_saved flag set properly? → Code review
3. save_state() called? → Check for "Updated conversation_summary in JSON file" log

### Issue: "Summary in JSON but not in database"
**Check:**
1. [2/2] log appears? → Check for database save log
2. _upsert_conversation_summary() called? → Code review
3. No database errors? → Check for [2/2] error log

---

## ⏱️ TIMING EXPECTATIONS

```
T+0 min:    Send message
            Background tasks trigger
            Activity logged in DB
            
T+0-2 min:  Wait (no activity)
            Idle timer counts down
            
T+2 min:    Idle detection worker runs
            [1/2] JSON saved
            [2/2] DB saved
            
T+2-3 min:  Close conversation
            
T+3+ min:   Reopen conversation
            State loaded from JSON
            Message restored
            Summary visible
```

---

## 🎯 FINAL GO/NO-GO DECISION

**Current Status: ✅ GO AHEAD**

All components are in place:
- Activity tracking ✅
- Idle detection ✅
- Summary generation ✅
- JSON→DB sequence ✅
- State persistence ✅
- Error handling ✅

**You're ready to run the test!**

Follow the checklist above and report results.

Good luck! 🚀
