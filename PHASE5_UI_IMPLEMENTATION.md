# Phase 5 HITL UI - Implementation Guide for Developers

**Complete guide to build Phase 5 UI from scratch**

---

## 📋 Quick Overview

Phase 5 is where users approve or reject 7 artifacts:
- **PPTX**: Users select which slides to regenerate (partial)
- **DOCX, XLSX, PDF, SOP, Narrative, DrawIO**: Entire document regenerates (full)

Max 3 rejection attempts. All must be approved to move to Phase 6.

---

## 🏗️ Architecture: 5 Files to Create

```
frontend/components/phase5_hitl/
├── usePhase5API.ts           ← API hook (4 functions)
├── ArtifactCard.tsx          ← Display one artifact
├── SlideSelector.tsx         ← PPTX slide selector (conditional)
├── RejectionForm.tsx         ← Modal form
└── Phase5HITLReview.tsx      ← Main page with polling
```

---

## 📦 Dependencies

```bash
npm install react axios
```

---

## 📁 Step 1: Create Types File

File: `frontend/types/phase5.ts`

```typescript
export interface ArtifactStatus {
  artifact_type: string;
  version: string;
  status: 'pending' | 'regenerating' | 'approved' | 'max_rejections';
  attempt_count: number;
  total_slides?: number;
  approved_slides: number[];
  rejected_slides: number[];
  is_current: boolean;
}

export interface ApprovalStatusResponse {
  run_id: string;
  artifacts: ArtifactStatus[];
}

export interface RejectPayload {
  artifact_type: string;
  rejected_slides: number[] | null;
  approved_slides: number[] | null;
  user_feedback?: string;
}

export interface ApproveResponse {
  status: 'ok' | 'error';
  message: string;
}
```

---

## 🔌 Step 2: Create API Hook

File: `frontend/components/phase5_hitl/usePhase5API.ts`

```typescript
import { useState, useCallback } from 'react';

export function usePhase5API(runId: string) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // GET all artifacts status
  const getApprovalStatus = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/runs/${runId}/phase5/approval-status`);
      const data = await response.json();
      setError(null);
      return data;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [runId]);

  // POST approve all
  const approveAll = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/runs/${runId}/phase5/approve-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await response.json();
      setError(null);
      return data;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [runId]);

  // POST reject artifact
  const rejectArtifact = useCallback(async (payload: RejectPayload) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/runs/${runId}/phase5/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      setError(null);
      return data;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [runId]);

  return { loading, error, getApprovalStatus, approveAll, rejectArtifact };
}
```

---

## 🎨 Step 3: Create ArtifactCard Component

File: `frontend/components/phase5_hitl/ArtifactCard.tsx`

```typescript
import React from 'react';
import { ArtifactStatus } from '../../types/phase5';

interface Props {
  artifact: ArtifactStatus;
  onReject: () => void;
}

export function ArtifactCard({ artifact, onReject }: Props) {
  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    regenerating: 'bg-blue-100 text-blue-800',
    approved: 'bg-green-100 text-green-800',
    max_rejections: 'bg-red-100 text-red-800'
  };

  const canReject = artifact.status === 'pending' && artifact.attempt_count < 3;

  return (
    <div className="border border-gray-300 rounded-lg p-4 mb-4">
      <div className="flex justify-between items-center mb-3">
        <div className="flex items-center gap-3">
          <h3 className="font-bold text-lg">{artifact.artifact_type.toUpperCase()}</h3>
          <span className="bg-gray-200 px-2 py-1 text-sm rounded">{artifact.version}</span>
          <span className={`px-2 py-1 text-sm rounded ${statusColors[artifact.status]}`}>
            {artifact.status}
          </span>
        </div>
        <span className="text-sm text-gray-600">Attempt: {artifact.attempt_count}/3</span>
      </div>

      {artifact.artifact_type === 'pptx' && artifact.total_slides && (
        <div className="text-sm text-gray-700 mb-3">
          <p>Total Slides: {artifact.total_slides}</p>
          {artifact.approved_slides.length > 0 && (
            <p className="text-green-700">✓ Approved: {artifact.approved_slides.join(', ')}</p>
          )}
          {artifact.rejected_slides.length > 0 && (
            <p className="text-red-700">✗ Rejected: {artifact.rejected_slides.join(', ')}</p>
          )}
        </div>
      )}

      {artifact.status === 'regenerating' && (
        <div className="text-blue-600 text-sm mb-3">⏳ Regenerating...</div>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => window.open(`/artifacts/${artifact.artifact_type}_${artifact.version}`)}
          className="px-3 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
        >
          👁️ View
        </button>
        <button
          onClick={onReject}
          disabled={!canReject}
          className="px-3 py-2 bg-red-500 text-white rounded disabled:bg-gray-300 text-sm"
        >
          ❌ Reject
        </button>
      </div>
    </div>
  );
}
```

---

## 🎯 Step 4: Create SlideSelector Component

File: `frontend/components/phase5_hitl/SlideSelector.tsx`

```typescript
import React, { useState } from 'react';

interface Props {
  totalSlides: number;
  initialRejected?: number[];
  onSlidesChange: (rejected: number[], approved: number[]) => void;
}

export function SlideSelector({ totalSlides, initialRejected = [], onSlidesChange }: Props) {
  const [selectedRejected, setSelectedRejected] = useState<Set<number>>(
    new Set(initialRejected)
  );

  const toggleSlide = (slideNum: number) => {
    const newSelected = new Set(selectedRejected);
    if (newSelected.has(slideNum)) {
      newSelected.delete(slideNum);
    } else {
      newSelected.add(slideNum);
    }
    setSelectedRejected(newSelected);

    const approved = Array.from({ length: totalSlides }, (_, i) => i + 1).filter(
      (num) => !newSelected.has(num)
    );
    onSlidesChange(Array.from(newSelected), approved);
  };

  return (
    <div className="p-4 border border-blue-300 rounded-lg bg-blue-50 mb-4">
      <h4 className="font-semibold mb-3">Select slides to regenerate:</h4>
      <div className="grid grid-cols-4 gap-2">
        {Array.from({ length: totalSlides }, (_, i) => i + 1).map((slideNum) => (
          <label key={slideNum} className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={selectedRejected.has(slideNum)}
              onChange={() => toggleSlide(slideNum)}
              className="w-4 h-4"
            />
            <span className="text-sm">
              Slide {slideNum}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}
```

---

## 📝 Step 5: Create RejectionForm Component

File: `frontend/components/phase5_hitl/RejectionForm.tsx`

```typescript
import React, { useState } from 'react';
import { SlideSelector } from './SlideSelector';

interface Props {
  artifactType: string;
  totalSlides?: number;
  onConfirm: (feedback: string, rejectedSlides?: number[] | null, approvedSlides?: number[] | null) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function RejectionForm({ artifactType, totalSlides, onConfirm, onCancel, isLoading }: Props) {
  const [feedback, setFeedback] = useState('');
  const [rejectedSlides, setRejectedSlides] = useState<number[]>([]);
  const [approvedSlides, setApprovedSlides] = useState<number[]>([]);

  const handleConfirm = () => {
    if (artifactType === 'pptx') {
      onConfirm(feedback, rejectedSlides, approvedSlides);
    } else {
      onConfirm(feedback, null, null); // Full rejection
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg max-w-md w-full max-h-96 overflow-y-auto">
        <h2 className="text-xl font-bold mb-4">Reject {artifactType.toUpperCase()}</h2>

        {artifactType === 'pptx' && totalSlides && (
          <SlideSelector
            totalSlides={totalSlides}
            onSlidesChange={(rejected, approved) => {
              setRejectedSlides(rejected);
              setApprovedSlides(approved);
            }}
          />
        )}

        {artifactType !== 'pptx' && (
          <p className="text-sm text-gray-600 mb-4">
            This will regenerate the entire {artifactType.toUpperCase()} from scratch.
          </p>
        )}

        <div className="mb-4">
          <label className="block text-sm font-semibold mb-2">Feedback (optional)</label>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Tell us what to improve..."
            className="w-full p-3 border rounded"
            rows={3}
            maxLength={500}
          />
          <p className="text-xs text-gray-500 mt-1">{feedback.length}/500</p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleConfirm}
            disabled={isLoading}
            className="flex-1 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300 text-sm"
          >
            {isLoading ? '⏳ Submitting...' : 'Confirm Rejection'}
          </button>
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="flex-1 px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400 disabled:bg-gray-200 text-sm"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## 🎪 Step 6: Create Main Phase5 Page

File: `frontend/components/phase5_hitl/Phase5HITLReview.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { usePhase5API } from './usePhase5API';
import { ArtifactCard } from './ArtifactCard';
import { RejectionForm } from './RejectionForm';
import { ArtifactStatus, ApprovalStatusResponse } from '../../types/phase5';

interface Props {
  runId: string;
  onPhase6?: () => void;
}

export function Phase5HITLReview({ runId, onPhase6 }: Props) {
  const [artifacts, setArtifacts] = useState<ArtifactStatus[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null);
  const [showRejectionForm, setShowRejectionForm] = useState(false);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);
  const [isApproving, setIsApproving] = useState(false);

  const { loading, error, getApprovalStatus, approveAll, rejectArtifact } = usePhase5API(runId);

  // Load initial status
  useEffect(() => {
    const loadStatus = async () => {
      const data = await getApprovalStatus();
      if (data?.artifacts) {
        setArtifacts(data.artifacts);
      }
    };
    loadStatus();
  }, [getApprovalStatus]);

  // Polling for regeneration updates
  useEffect(() => {
    const anyRegenerating = artifacts.some((a) => a.status === 'regenerating');

    if (anyRegenerating && !pollingInterval) {
      const interval = setInterval(async () => {
        const data = await getApprovalStatus();
        if (data?.artifacts) {
          setArtifacts(data.artifacts);
        }
      }, 5000);
      setPollingInterval(interval);
    } else if (!anyRegenerating && pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }

    return () => {
      if (pollingInterval) clearInterval(pollingInterval);
    };
  }, [artifacts, pollingInterval, getApprovalStatus]);

  const handleApproveAll = async () => {
    setIsApproving(true);
    const response = await approveAll();
    if (response?.status === 'ok') {
      alert('✅ All artifacts approved! Moving to Phase 6...');
      if (onPhase6) onPhase6();
      // Or redirect: window.location.href = '/runs/' + runId + '/phase6';
    } else {
      alert('❌ Error approving: ' + response?.message);
    }
    setIsApproving(false);
  };

  const handleRejectConfirm = async (feedback: string, rejectedSlides?: number[] | null, approvedSlides?: number[] | null) => {
    const payload = {
      artifact_type: selectedArtifact!,
      rejected_slides: rejectedSlides || null,
      approved_slides: approvedSlides || null,
      user_feedback: feedback || undefined
    };

    const response = await rejectArtifact(payload);
    if (response?.status === 'regenerating' || response?.status === 'max_rejections') {
      setShowRejectionForm(false);
      setSelectedArtifact(null);
      // Refresh status
      const data = await getApprovalStatus();
      if (data?.artifacts) {
        setArtifacts(data.artifacts);
      }
    }
  };

  const approvedCount = artifacts.filter((a) => a.status === 'approved').length;
  const regeneratingCount = artifacts.filter((a) => a.status === 'regenerating').length;
  const pendingCount = artifacts.filter((a) => a.status === 'pending').length;

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      <h1 className="text-3xl font-bold mb-2">🎯 Phase 5: Design Review</h1>
      <p className="text-gray-600 mb-6">Review and approve all artifacts. Reject to regenerate.</p>

      {error && <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">{error}</div>}

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="p-4 bg-yellow-100 rounded">
          <p className="text-sm text-gray-700">Pending</p>
          <p className="text-2xl font-bold text-yellow-700">{pendingCount}</p>
        </div>
        <div className="p-4 bg-blue-100 rounded">
          <p className="text-sm text-gray-700">Regenerating</p>
          <p className="text-2xl font-bold text-blue-700">{regeneratingCount}</p>
        </div>
        <div className="p-4 bg-green-100 rounded">
          <p className="text-sm text-gray-700">Approved</p>
          <p className="text-2xl font-bold text-green-700">{approvedCount}</p>
        </div>
      </div>

      {regeneratingCount > 0 && (
        <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded mb-6">
          ⏳ Polling for regeneration updates every 5 seconds...
        </div>
      )}

      {/* Artifacts */}
      <div className="bg-white p-6 rounded-lg mb-6">
        <h2 className="text-xl font-bold mb-4">Artifacts</h2>
        {artifacts.length === 0 ? (
          <p className="text-gray-500">Loading artifacts...</p>
        ) : (
          artifacts.map((artifact) => (
            <ArtifactCard
              key={artifact.artifact_type}
              artifact={artifact}
              onReject={() => {
                setSelectedArtifact(artifact.artifact_type);
                setShowRejectionForm(true);
              }}
            />
          ))
        )}
      </div>

      {/* Rejection Form Modal */}
      {showRejectionForm && selectedArtifact && (
        <RejectionForm
          artifactType={selectedArtifact}
          totalSlides={artifacts.find((a) => a.artifact_type === selectedArtifact)?.total_slides}
          onConfirm={handleRejectConfirm}
          onCancel={() => {
            setShowRejectionForm(false);
            setSelectedArtifact(null);
          }}
          isLoading={loading}
        />
      )}

      {/* Approve All Button */}
      <div className="bg-white p-6 rounded-lg">
        <button
          onClick={handleApproveAll}
          disabled={regeneratingCount > 0 || approvedCount === 0 || isApproving}
          className="w-full px-6 py-3 bg-green-500 text-white text-lg font-bold rounded hover:bg-green-600 disabled:bg-gray-300 text-center"
        >
          {isApproving ? '⏳ Approving...' : '✅ Approve All & Move to Phase 6'}
        </button>
        <p className="text-sm text-gray-600 mt-2 text-center">
          {approvedCount}/{artifacts.length} artifacts ready
        </p>
      </div>
    </div>
  );
}
```

---

## 🔗 Step 7: Add Route to App

File: `frontend/pages/RunPhase5.tsx`

```typescript
import React from 'react';
import { useParams } from 'react-router-dom';
import { Phase5HITLReview } from '../components/phase5_hitl/Phase5HITLReview';

export function RunPhase5Page() {
  const { runId } = useParams<{ runId: string }>();

  return <Phase5HITLReview runId={runId!} onPhase6={() => window.location.href = `/runs/${runId}/phase6`} />;
}
```

File: `frontend/App.tsx` - Add this route:

```typescript
import { RunPhase5Page } from './pages/RunPhase5';

// In your router:
<Route path="/runs/:runId/phase5" element={<RunPhase5Page />} />
```

---

## 🧪 API Endpoints Reference

### 1. GET Approval Status

```
GET /api/runs/{runId}/phase5/approval-status

Response:
{
  "run_id": "run_fccc13f709",
  "artifacts": [
    {
      "artifact_type": "pptx",
      "version": "v1",
      "status": "pending",
      "attempt_count": 1,
      "total_slides": 7,
      "approved_slides": [],
      "rejected_slides": []
    },
    ...
  ]
}
```

### 2. POST Reject Artifact

```
POST /api/runs/{runId}/phase5/reject

Request:
{
  "artifact_type": "pptx",
  "rejected_slides": [2, 4],          // null for full rejection
  "approved_slides": [1, 3, 5, 6, 7], // null for full rejection
  "user_feedback": "Improve design"
}

Response:
{
  "status": "regenerating",
  "new_version": "v2",
  "attempt": "1/3"
}
```

### 3. POST Approve All

```
POST /api/runs/{runId}/phase5/approve-all

Request: {}

Response:
{
  "status": "ok",
  "message": "All artifacts approved. Moving to Phase 6."
}
```

---

## 📊 Database State Changes

### When User Rejects

```sql
-- Before:
artifact_approvals:
  pptx, v1, status: pending, is_current: true

-- After:
artifact_approvals:
  pptx, v1, status: pending, is_current: false, replaced_by: v2
  pptx, v2, status: regenerating, is_current: true, attempt_count: 2
```

### When Regeneration Completes

```sql
-- After ~30 seconds:
artifact_approvals:
  pptx, v2, status: pending, is_current: true
  
-- UI polling detects: status changed from "regenerating" → "pending"
```

### When User Approves All

```sql
-- After approval:
artifact_approvals:
  pptx, v2, status: approved, is_current: true, is_immutable: true
  docx, v1, status: approved, is_current: true, is_immutable: true
  ...all 7 artifacts with status: approved

runs:
  phase_5_status: "approved"
```

---

## 🧪 Testing Checklist

### Test 1: Basic Load & Display
```
1. Navigate to /runs/{runId}/phase5
2. Verify: See all 7 artifacts (PPTX, DOCX, XLSX, PDF, SOP, Narrative, DrawIO)
3. Verify: Status counts show (0 pending, 0 regenerating, 0 approved initially)
4. Verify: Buttons work ([View], [Reject], [Approve All])
```

### Test 2: PPTX Partial Rejection
```
1. Click [Reject] on PPTX
2. Uncheck slides 2 & 4
3. Add feedback "Improve design"
4. Click [Confirm Rejection]
5. Verify: PPTX shows v2, status: regenerating
6. Wait ~30 seconds
7. Verify: Status auto-updates to pending
8. Click [View] - Should open pptx_v2.pptx with slides 2 & 4 new
```

### Test 3: DOCX Full Rejection
```
1. Click [Reject] on DOCX
2. No slide selector shown
3. Add feedback "Full rewrite"
4. Click [Confirm Rejection]
5. Verify: DOCX shows v2, status: regenerating
6. Wait ~30 seconds
7. Verify: Status auto-updates to pending
```

### Test 4: Max Rejections (3/3)
```
1. Reject PPTX 3 times (v1 → v2 → v3 → v4)
2. On 3rd rejection, attempt shows 3/3
3. Verify: [Reject] button disabled
4. Verify: Can only [Approve All] to proceed
```

### Test 5: Full Approval Flow
```
1. All artifacts pending (no regenerating)
2. Click [Approve All]
3. Verify: Success message shown
4. Verify: Redirected to Phase 6 page
5. Verify in DB: All artifacts status = "approved"
```

---

## ⚠️ Common Errors & Fixes

### Error: "Cannot read property 'artifacts' of null"
```
Cause: API not responding or returning null
Fix: Check if backend is running, check /api/runs/{runId}/phase5/approval-status endpoint
```

### Error: "Status stays 'regenerating' forever"
```
Cause: Backend regeneration stuck or failed
Fix: Check backend logs, check if Phase 3 is running
```

### Error: "PPTX has no SlideSelector"
```
Cause: artifact.artifact_type !== 'pptx'
Fix: Verify artifact_type is lowercase 'pptx', not 'PPTX'
```

### Error: "Polling stops working"
```
Cause: Interval not cleared, new interval created
Fix: Check useEffect cleanup in Phase5HITLReview component
```

---

## 📞 Integration Checklist

- [ ] Create 5 component files
- [ ] Create types file
- [ ] Add types to imports
- [ ] Import components into Phase5HITLReview
- [ ] Add route to App.tsx
- [ ] Test basic load
- [ ] Test rejection flow
- [ ] Test approval flow
- [ ] Test max rejections
- [ ] Verify polling works
- [ ] Check database updates
- [ ] Ready for production!

---

**That's it! Everything is in this guide. Build and test!** 🚀
