# Quick Start - Verify All Fixes Are Working ✅

**Time to completion**: ~15 minutes

---

## 🚀 Step 1: Run Database Migration (2 min)

```bash
cd D:\Users\ChiragJain\My_Project

# Run the migration
alembic upgrade head

# You should see:
# INFO  [alembic.runtime.migration] Running upgrade 023_workbench_ui -> 024_evaluation_passed
# INFO  [alembic.runtime.migration] Running raw SQL statement
```

✅ **Verify**: No errors in migration output

---

## 🔄 Step 2: Restart Server (3 min)

**Terminal A**: Stop old server
```bash
# If running: Press Ctrl+C in the terminal running uvicorn
```

**Terminal A**: Start fresh server
```bash
uvicorn src.app.main:app --reload

# Wait for this message:
# INFO:     Application startup complete
```

✅ **Verify**: Server starts without errors

---

## 📊 Step 3: Watch Logs (10 min)

**Terminal B**: Watch for key log messages
```bash
tail -f logs/app.log | grep -E "\[VQA-ERROR\]|\[PHASE-EVALUATE\]|\[INVESTIGATOR\]|error_details|external_service"
```

---

## 🧪 Step 4: Trigger Test (30 sec)

**Browser**: Go to Sheldon UI and:
1. Create a new request
2. Ask for something that will take a while (like "Generate 10-slide presentation with metrics")
3. Request multiple artifacts to increase chance of hitting rate limit

---

## 📋 Step 5: Check Each Fix

### Fix #1: visual_qa.py Error Capture ✅

**Look for in logs**:
```
[VQA-ERROR] Claude API error during PPTX evaluation
[VQA-ERROR]   Error type: RateLimitError
[VQA-ERROR]   Error message: Rate limit exceeded
```

**Status**: 
- [ ] See all 3 lines above
- [ ] Error type is NOT "Exception" (means actual error captured)

### Fix #2: investigator_agent.py Detection ✅

**Look for in logs**:
```
[INVESTIGATOR-NODE] Attempt 1: Extracted error_details - RateLimitError
[INVESTIGATOR-NODE] 🎯 NODE 2: CLASSIFY ROOT CAUSE
[INVESTIGATOR-NODE]   Root Cause: external_service_error
[INVESTIGATOR-NODE]   Confidence: 95.0%
```

**Status**:
- [ ] See "Extracted error_details - RateLimitError" (means error_details dict extracted)
- [ ] Root Cause is "external_service_error" NOT "llm_problem" (means classification works)
- [ ] Confidence is 0.95+ (means API error rule worked)

### Fix #3: evaluation_passed Flag ✅

**Look for in logs**:
```
[PHASE-EVALUATE] 📊 Set evaluation_passed=False in database
```

**Status**:
- [ ] See this line in logs (means flag is being set)

**Check database**:
```bash
sqlite3 advise_workbench.db "SELECT id, status, evaluation_passed FROM runs WHERE status='approved' LIMIT 5;"
```

**Status**:
- [ ] See evaluation_passed column in output
- [ ] Values are 0 (False) or 1 (True)

### Fix #4: View Artifacts Button ✅

**In Sheldon UI**:
1. Look at the run card for your test run
2. If evaluation FAILED: "View artifacts" button should NOT show
3. If evaluation PASSED: "View artifacts" button SHOULD show

**Status**:
- [ ] Button hidden when evaluation failed
- [ ] Button shown when evaluation passed

---

## 📝 Log Checklist

Copy and paste commands to verify each component:

### Check Fix #1: Error details captured
```bash
grep "\[VQA-ERROR\]" logs/app.log | tail -5
```
**Expected**: 3 lines per error (type, message, details)

### Check Fix #2: Error classification
```bash
grep "external_service_error" logs/app.log
```
**Expected**: At least one match when evaluation fails with API error

### Check Fix #3: Evaluation flag set
```bash
grep "evaluation_passed" logs/app.log | head -10
```
**Expected**: Multiple entries showing flag being set to True or False

### Check Fix #4: Database column exists
```bash
sqlite3 advise_workbench.db "PRAGMA table_info(runs);" | grep evaluation_passed
```
**Expected**: One line showing evaluation_passed column definition

---

## 🎯 Success Criteria

All 4 fixes are working if you see:

1. ✅ `[VQA-ERROR]` logs with actual error type
2. ✅ `external_service_error` classification (not llm_problem)
3. ✅ `evaluation_passed=False` in logs
4. ✅ Button hidden when evaluation fails
5. ✅ evaluation_passed column in database

---

## 🚨 Troubleshooting

### Issue: No [VQA-ERROR] logs appear
**Cause**: Visual QA didn't hit an error, or logs not appearing  
**Fix**: 
- Try requesting larger files (increases chance of rate limit)
- Check if server is actually running (`lsof -i :8000`)
- Try request that definitely will fail

### Issue: Root cause shows "llm_problem" instead of "external_service_error"
**Cause**: Classification prompt didn't detect API error keywords  
**Fix**:
- Check investigator_agent.py line 173-182 has API error rule
- Check logs show "Extracted error_details - RateLimitError"
- Manually test classification with error message

### Issue: evaluation_passed column not found in database
**Cause**: Migration didn't run  
**Fix**:
```bash
alembic current    # Check current revision
alembic upgrade head  # Run migration again
```

### Issue: Button still shows on failed evaluation
**Cause**: evaluation_passed not set or frontend not updated  
**Fix**:
- Check `orchestrator.py line 2430-2447` sets `run.evaluation_passed = False`
- Check `RunProgressCard.tsx line 72` has new condition
- Clear browser cache and reload page

---

## 📞 Quick Reference

| Component | File | What to check |
|-----------|------|---------------|
| Error capture | visual_qa.py:301-318 | Prints [VQA-ERROR] |
| Error extraction | investigator_agent.py:68-97 | Extracts error_details dict |
| API error rule | investigator_agent.py:173-182 | Mentions RateLimitError |
| Flag setting | orchestrator.py:2423-2447 | Sets evaluation_passed |
| Button check | RunProgressCard.tsx:72 | Checks evaluation_passed |
| Database | models.py:131 | Has evaluation_passed field |
| Migration | 024_evaluation_passed.py | Creates column |

---

## 🎓 What Each Fix Does

1. **visual_qa.py**: When Claude API errors occur, captures real error type (RateLimitError, APIConnectionError, etc.) instead of generic message
   
2. **investigator_agent.py**: When analyzing failures, extracts error_details dict and uses Claude prompt to classify API errors as external_service_error

3. **models.py + orchestrator.py**: Sets evaluation_passed flag (True/False) in database based on evaluation result

4. **RunProgressCard.tsx**: Only shows "View artifacts" button when evaluation actually passed

---

**Ready to test?** Follow the 5 steps above (15 min total)  
**Questions?** See VISUAL_QA_ERROR_ANALYSIS.md or IMPLEMENTATION_SUMMARY.md
