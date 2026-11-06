# Phase 5 UI - Complete Developer Guide
## Comprehensive Implementation & Integration Guide

---

## 📚 Table of Contents
1. [What is Phase 5?](#what-is-phase-5)
2. [User Flow & Workflow](#user-flow--workflow)
3. [File Structure & Where to Put Code](#file-structure--where-to-put-code)
4. [Code Overview: What's Written & Why](#code-overview-whats-written--why)
5. [Complete React Implementation](#complete-react-implementation)
6. [Integration Steps](#integration-steps)
7. [Testing Guide](#testing-guide)
8. [Troubleshooting](#troubleshooting)

---

## What is Phase 5?

### The Pipeline Context
```
Phase 3: Generate artifacts (PPTX, DOCX, XLSX, PDF, SOP, Narrative, DrawIO)
         ↓
Phase 4: Evaluate quality & guardrails
         ↓
Phase 5: HUMAN-IN-THE-LOOP DESIGN REVIEW ← YOU ARE HERE
         (User approves or rejects for regeneration)
         ↓
Phase 6: Remember & finalize
```

### What Phase 5 Does
- **Blocks the pipeline** and waits for user approval
- **User reviews** 7 artifact types
- **User decides**: Approve all or reject to regenerate
- **For PPTX**: User can select WHICH slides to regenerate (partial)
- **For others**: Entire artifact regenerates (full)
- **Max 3 attempts**: If user rejects 3 times, they must approve
- **Regeneration**: Happens in background (Phase 3 again) with special parameters

### Why Phase 5 Exists
Before Phase 5, artifacts were auto-approved even if bad quality. Now users have control:
- ✅ Approve good artifacts
- ❌ Reject bad ones for regeneration
- 🎯 Iterate until satisfied (max 3 times)

---

## User Flow & Workflow

### Complete User Journey

#### STEP 1: User Navigates to Phase 5
```
User: Generates artifacts → System completes Phase 3 & 4
       ↓
URL: /runs/{runId}/phase5
       ↓
UI Page: "Phase 5: Design Review"
```

#### STEP 2: User Sees the Dashboard
```
┌─────────────────────────────────────────┐
│ Phase 5: Design Review                  │
│                                         │
│ Status Summary (Top):                   │
│ ⏳ Pending: 5    🔄 Regenerating: 0    ✅ Approved: 2
│                                         │
│ 7 Artifact Cards (Middle):              │
│ ├─ 📊 PPTX v1    [View] [Reject]       │
│ ├─ 📄 DOCX v1    [View] [Reject]       │
│ ├─ 📋 XLSX v1    [View] [Reject]       │
│ └─ ... (4 more)                         │
│                                         │
│ Action Button (Bottom):                 │
│ [✅ Approve All & Move to Phase 6]      │
│                                         │
└─────────────────────────────────────────┘
```

#### STEP 3A: User APPROVES ALL (Happy Path)
```
User clicks: [Approve All & Move to Phase 6]
       ↓
Backend marks all artifacts: status = "approved", is_immutable = true
       ↓
Phase 5 completes → Phase 6 starts
       ↓
UI redirects to Phase 6 page
```

#### STEP 3B: User REJECTS (PPTX - Partial)
```
User clicks: [Reject] on PPTX card
       ↓
Rejection Form Opens:
       ┌─────────────────────────────┐
       │ Reject PPTX Presentation    │
       │                             │
       │ Select slides to regenerate:|
       │ ☑ Slide 1 (Keep)           │
       │ ☐ Slide 2 (Regenerate)     │
       │ ☑ Slide 3 (Keep)           │
       │ ☐ Slide 4 (Regenerate)     │
       │ ☑ Slide 5 (Keep)           │
       │ ☑ Slide 6 (Keep)           │
       │ ☑ Slide 7 (Keep)           │
       │                             │
       │ Feedback (optional):        │
       │ [Improve design on ...]     │
       │                             │
       │ [Confirm] [Cancel]          │
       └─────────────────────────────┘

User Action Sequence:
1. Click [Reject] button
2. Uncheck slides 2 & 4 (mark for regeneration)
3. Type feedback: "Improve design"
4. Click [Confirm Rejection]
```

#### STEP 3C: User REJECTS (DOCX - Full)
```
User clicks: [Reject] on DOCX card
       ↓
Rejection Form Opens (Simplified - No Slides):
       ┌──────────────────────────────┐
       │ Reject DOCX Document         │
       │                              │
       │ This regenerates the ENTIRE  │
       │ document from scratch        │
       │                              │
       │ Feedback (optional):         │
       │ [Need better structure...]   │
       │                              │
       │ [Confirm] [Cancel]           │
       └──────────────────────────────┘

User Action Sequence:
1. Click [Reject] button
2. Type feedback: "Need better structure"
3. Click [Confirm Rejection]
```

#### STEP 4: System Regenerates (Automatic)
```
After user clicks [Confirm Rejection]:
       ↓
Backend (Instant):
   - Creates new version (v2)
   - Marks old v1 as replaced
   - Sets status = "regenerating"
       ↓
UI (Instant):
   - Shows PPTX v2, status=regenerating
   - Starts polling every 5 seconds
   - Shows spinner: "⏳ Regenerating..."
       ↓
Backend (Background, 30-60 seconds):
   - Phase 3 runs with special parameters
   - For PPTX: Regenerates slides 2 & 4 only, keeps 1,3,5,6,7
   - For DOCX: Regenerates entire document from scratch
   - Creates new files
       ↓
Backend (After regen):
   - Updates database: status = "pending"
       ↓
UI (Polls every 5 seconds):
   - Detects: status changed from "regenerating" → "pending"
   - Removes spinner
   - Shows: "PPTX v2 ✅ Ready for approval"
   - User can now [View] v2 or [Reject] again
```

#### STEP 5: User Reviews Regenerated Version
```
User can:
Option A: Click [View] to open pptx_v2.pptx
         ✓ For PPTX: See slides 1,3,5,6,7 unchanged, slides 2 & 4 NEW
         ✓ For DOCX: See completely new document

Option B: Click [Reject] again (2nd time)
         → New rejection form for v2
         → Creates v3
         → Same process repeats

Option C: Click [Approve All] to approve
         → All artifacts (including v2) approved
         → Phase 6 starts
```

#### STEP 6: Max Attempts Reached
```
If user rejects 3 times:
       ↓
After 3rd rejection attempt:
   - Button [Reject] becomes DISABLED ❌
   - Message shows: "Max attempts reached (3/3)"
   - User MUST click [Approve All] to proceed
       ↓
User clicks [Approve All]
   → v4 (or whatever latest) approved as-is
   → Phase 6 starts
```

---

## File Structure & Where to Put Code

### Frontend Folder Structure
```
frontend/
├── components/
│   ├── phase5_hitl/                    ← CREATE THIS FOLDER
│   │   ├── usePhase5API.ts            ← Custom hook for API calls
│   │   ├── ArtifactCard.tsx           ← Display one artifact
│   │   ├── SlideSelector.tsx          ← PPTX slide checkboxes
│   │   ├── RejectionForm.tsx          ← Modal form for rejection
│   │   └── Phase5HITLReview.tsx       ← Main page (all together)
│   │
│   └── types/
│       └── phase5.ts                  ← TypeScript types
│
├── pages/
│   └── RunPhase5.tsx                  ← Route page
│
└── App.tsx                             ← Add route here
```

### What Goes in Each File

| File | Purpose | Responsibility |
|------|---------|-----------------|
| `usePhase5API.ts` | API integration | Calls backend endpoints |
| `ArtifactCard.tsx` | Display | Shows one artifact + buttons |
| `SlideSelector.tsx` | Selection | PPTX slide checkbox UI |
| `RejectionForm.tsx` | Modal | Rejection form + logic |
| `Phase5HITLReview.tsx` | Container | State + polling + layout |
| `phase5.ts` | Types | TypeScript interfaces |
| `RunPhase5.tsx` | Route | Wraps Phase5HITLReview |
| `App.tsx` | Router | Maps URL to component |

---

## Code Overview: What's Written & Why

### Backend (Already Built - No Changes Needed)

#### 1. API Endpoints (`src/app/api/phase5_hitl.py`)
```python
# GET /api/runs/{runId}/phase5/approval-status
# Returns: All 7 artifacts with their current status, version, attempt count

# GET /api/runs/{runId}/phase5/approval-status/{type}
# Returns: Single artifact status (for specific lookup)

# POST /api/runs/{runId}/phase5/approve-all
# Marks all artifacts as approved, moves to Phase 6

# POST /api/runs/{runId}/phase5/reject
# Rejects one artifact, queues Phase 3 regeneration, creates new version
```

#### 2. Phase 5 Orchestrator (`src/workflows/phase5_hitl_review.py`)
```python
_phase_hitl_review(job):
  1. Initialize approval records for all 7 artifacts
  2. Set status = "pending"
  3. Poll API every 5 seconds for user decision
  4. When user calls /approve-all → Move to Phase 6
  5. When user calls /reject → Queue Phase 3, create new version
  6. Handle max rejections (3 attempts)
```

#### 3. Rejection Handler (`src/workflows/phase5_rejection_handler.py`)
```python
queue_phase3_regeneration(job):
  - For PPTX: Pass rejected_slides + approved_slides
  - For others: Pass null (full regeneration)
  - Queue Phase 3 with special "regeneration mode" parameters
  - Phase 3 knows NOT to re-run evaluation, just regenerate artifacts
```

#### 4. Database (`migrations/025_phase5_hitl_approval.py`)
```sql
artifact_approvals table:
  - Tracks each artifact version (v1, v2, v3, ...)
  - Stores: version, status, attempt_count, approved_slides, rejected_slides
  - Links: replaced_by (v1 → v2), is_current (only latest is current)
  
runs table additions:
  - phase_5_status: Current state of Phase 5
  - phase_5_approval_data: JSON with all approval metadata
```

### Frontend (You Need to Build)

#### Why Each Component Exists

**usePhase5API Hook**
- ✅ Encapsulates all HTTP calls
- ✅ Handles loading/error states
- ✅ Reusable across components
- ✅ Centralizes API logic

**ArtifactCard**
- ✅ Reusable for all 7 artifacts
- ✅ Shows version, status, attempt counter
- ✅ Displays slides info (PPTX only)
- ✅ Has action buttons

**SlideSelector**
- ✅ Only for PPTX rejection
- ✅ Let's user check/uncheck slides
- ✅ Calculates approved/rejected lists
- ✅ Conditional rendering (PPTX only)

**RejectionForm**
- ✅ Modal popup for rejection
- ✅ Shows SlideSelector (PPTX) or simple form (others)
- ✅ Feedback textarea
- ✅ [Confirm] and [Cancel] buttons

**Phase5HITLReview** (Main Container)
- ✅ Manages all state
- ✅ Orchestrates polling (every 5 seconds)
- ✅ Detects status changes
- ✅ Renders summary, artifact list, main button
- ✅ Handles user interactions

---

## Complete React Implementation

### File 1: Types (`frontend/types/phase5.ts`)

```typescript
// Data structure for one artifact
export interface ArtifactStatus {
  artifact_type: 'pptx' | 'docx' | 'xlsx' | 'pdf' | 'sop' | 'narrative' | 'drawio';
  version: string;  // "v1", "v2", "v3"
  status: 'pending' | 'regenerating' | 'approved' | 'max_rejections';
  attempt_count: number;  // 1, 2, or 3
  total_slides?: number;  // Only for PPTX
  approved_slides: number[];  // [1, 3, 5, 6, 7] for PPTX
  rejected_slides: number[];  // [2, 4] for PPTX
  is_current: boolean;
}

// Response from approval-status API
export interface ApprovalStatusResponse {
  run_id: string;
  artifacts: ArtifactStatus[];
}

// Payload for reject API
export interface RejectPayload {
  artifact_type: string;
  rejected_slides: number[] | null;  // null = full rejection
  approved_slides: number[] | null;  // null = full rejection
  user_feedback?: string;
}

// Response from approve-all API
export interface ApproveResponse {
  status: 'ok' | 'error';
  message: string;
}
```

### File 2: API Hook (`frontend/components/phase5_hitl/usePhase5API.ts`)

```typescript
import { useState, useCallback } from 'react';

export function usePhase5API(runId: string) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // GET approval status for all artifacts
  const getApprovalStatus = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `/api/runs/${runId}/phase5/approval-status`
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setError(null);
      return data;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, [runId]);

  // POST approve all artifacts
  const approveAll = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/runs/${runId}/phase5/approve-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setError(null);
      return data;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, [runId]);

  // POST reject one artifact
  const rejectArtifact = useCallback(async (payload: RejectPayload) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/runs/${runId}/phase5/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setError(null);
      return data;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, [runId]);

  return { loading, error, getApprovalStatus, approveAll, rejectArtifact };
}
```

### File 3: Artifact Card (`frontend/components/phase5_hitl/ArtifactCard.tsx`)

```typescript
import React from 'react';
import { ArtifactStatus } from '../../types/phase5';

interface ArtifactCardProps {
  artifact: ArtifactStatus;
  onReject: () => void;
  isSelected?: boolean;
}

export function ArtifactCard({
  artifact,
  onReject,
  isSelected = false
}: ArtifactCardProps) {
  // Color for status badge
  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    regenerating: 'bg-blue-100 text-blue-800',
    approved: 'bg-green-100 text-green-800',
    max_rejections: 'bg-red-100 text-red-800'
  };

  // Determine if user can reject
  const canReject = artifact.status === 'pending' && artifact.attempt_count < 3;

  // Icons for each artifact type
  const iconMap: Record<string, string> = {
    pptx: '📊',
    docx: '📄',
    xlsx: '📋',
    pdf: '📑',
    sop: '📖',
    narrative: '📝',
    drawio: '🎨'
  };

  const icon = iconMap[artifact.artifact_type] || '📄';

  return (
    <div
      className={`border-2 rounded-lg p-4 mb-4 transition ${
        isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'
      }`}
    >
      {/* Header Row */}
      <div className="flex justify-between items-center mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{icon}</span>
          <h3 className="font-bold text-lg">
            {artifact.artifact_type.toUpperCase()}
          </h3>
          <span className="px-2 py-1 bg-gray-200 text-sm rounded">
            {artifact.version}
          </span>
          <span className={`px-2 py-1 text-sm rounded ${statusColors[artifact.status]}`}>
            {artifact.status === 'regenerating' && '🔄 '}
            {artifact.status === 'approved' && '✅ '}
            {artifact.status === 'max_rejections' && '⛔ '}
            {artifact.status}
          </span>
        </div>
        <span className="text-sm text-gray-600 font-mono">
          Attempt {artifact.attempt_count}/3
        </span>
      </div>

      {/* PPTX Specific Info */}
      {artifact.artifact_type === 'pptx' && artifact.total_slides && (
        <div className="mb-3 text-sm text-gray-700 bg-gray-50 p-2 rounded">
          <p>📑 Total Slides: {artifact.total_slides}</p>
          {artifact.approved_slides.length > 0 && (
            <p className="text-green-700">
              ✓ Approved slides: {artifact.approved_slides.join(', ')}
            </p>
          )}
          {artifact.rejected_slides.length > 0 && (
            <p className="text-red-700">
              ✗ Regenerated slides: {artifact.rejected_slides.join(', ')}
            </p>
          )}
        </div>
      )}

      {/* Regenerating Indicator */}
      {artifact.status === 'regenerating' && (
        <div className="mb-3 flex items-center gap-2">
          <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
          <span className="text-sm text-blue-600">
            Regenerating... (30-60 seconds)
          </span>
        </div>
      )}

      {/* Max Attempts Message */}
      {artifact.status === 'max_rejections' && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded">
          <p className="text-sm text-red-700">
            ⚠️ Maximum rejection attempts reached (3/3). You must approve this version.
          </p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => {
            // Open artifact file
            window.open(
              `/api/runs/${artifact.artifact_type}/${artifact.version}`,
              '_blank'
            );
          }}
          className="px-3 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm font-medium"
        >
          👁️ View
        </button>
        <button
          onClick={onReject}
          disabled={!canReject}
          className={`px-3 py-2 rounded text-sm font-medium ${
            canReject
              ? 'bg-red-500 text-white hover:bg-red-600 cursor-pointer'
              : 'bg-gray-300 text-gray-600 cursor-not-allowed'
          }`}
        >
          ❌ Reject
        </button>
      </div>
    </div>
  );
}
```

### File 4: Slide Selector (`frontend/components/phase5_hitl/SlideSelector.tsx`)

```typescript
import React, { useState } from 'react';

interface SlideSelectorProps {
  totalSlides: number;
  initialRejected?: number[];
  onSlidesChange: (rejected: number[], approved: number[]) => void;
}

export function SlideSelector({
  totalSlides,
  initialRejected = [],
  onSlidesChange
}: SlideSelectorProps) {
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

    // Calculate approved slides (all slides except rejected)
    const approved = Array.from({ length: totalSlides }, (_, i) => i + 1).filter(
      num => !newSelected.has(num)
    );
    
    onSlidesChange(Array.from(newSelected), approved);
  };

  return (
    <div className="p-4 border-2 border-blue-300 rounded-lg bg-blue-50 mb-4">
      <h4 className="font-bold text-sm mb-3">
        🎯 Select which slides to regenerate:
      </h4>
      
      <div className="grid grid-cols-2 gap-3 mb-3">
        {Array.from({ length: totalSlides }, (_, i) => i + 1).map(slideNum => (
          <label
            key={slideNum}
            className="flex items-center gap-2 cursor-pointer hover:bg-blue-100 p-2 rounded"
          >
            <input
              type="checkbox"
              checked={selectedRejected.has(slideNum)}
              onChange={() => toggleSlide(slideNum)}
              className="w-4 h-4 cursor-pointer"
            />
            <span className="text-sm">
              {selectedRejected.has(slideNum) ? '❌' : '✅'} Slide {slideNum}
            </span>
          </label>
        ))}
      </div>

      <p className="text-xs text-gray-600">
        💡 Checked = regenerate (new), Unchecked = keep from v1
      </p>
    </div>
  );
}
```

### File 5: Rejection Form (`frontend/components/phase5_hitl/RejectionForm.tsx`)

```typescript
import React, { useState } from 'react';
import { SlideSelector } from './SlideSelector';

interface RejectionFormProps {
  artifactType: string;
  totalSlides?: number;
  onConfirm: (
    feedback: string,
    rejectedSlides?: number[] | null,
    approvedSlides?: number[] | null
  ) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function RejectionForm({
  artifactType,
  totalSlides,
  onConfirm,
  onCancel,
  isLoading = false
}: RejectionFormProps) {
  const [feedback, setFeedback] = useState('');
  const [rejectedSlides, setRejectedSlides] = useState<number[]>([]);
  const [approvedSlides, setApprovedSlides] = useState<number[]>([]);

  const handleConfirm = () => {
    // For PPTX: send slide lists
    // For others: send null (full rejection)
    if (artifactType === 'pptx') {
      onConfirm(feedback, rejectedSlides, approvedSlides);
    } else {
      onConfirm(feedback, null, null);
    }
  };

  const isPPTX = artifactType === 'pptx';

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg max-w-md w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <h2 className="text-xl font-bold mb-4">
          Reject {artifactType.toUpperCase()}?
        </h2>

        {/* PPTX Slide Selector (Conditional) */}
        {isPPTX && totalSlides && (
          <>
            <SlideSelector
              totalSlides={totalSlides}
              onSlidesChange={(rejected, approved) => {
                setRejectedSlides(rejected);
                setApprovedSlides(approved);
              }}
            />
            <p className="text-xs text-gray-600 mb-4">
              ℹ️ Checked slides will be regenerated. Unchecked slides are kept from the previous version.
            </p>
          </>
        )}

        {/* Non-PPTX Message */}
        {!isPPTX && (
          <div className="p-3 bg-orange-50 border border-orange-200 rounded mb-4">
            <p className="text-sm text-orange-800">
              📌 This will regenerate the <strong>entire {artifactType.toUpperCase()}</strong> from scratch.
              All content will be recreated (unlike PPTX, which can be partial).
            </p>
          </div>
        )}

        {/* Feedback Textarea */}
        <div className="mb-4">
          <label className="block text-sm font-bold mb-2">
            💬 Feedback (optional):
          </label>
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder="Tell us what to improve... (max 500 chars)"
            maxLength={500}
            className="w-full p-3 border border-gray-300 rounded text-sm resize-none"
            rows={3}
          />
          <p className="text-xs text-gray-500 mt-1">
            {feedback.length}/500 characters
          </p>
        </div>

        {/* Error Message (if any) */}
        {isLoading && (
          <div className="p-2 bg-blue-50 border border-blue-200 rounded mb-4">
            <p className="text-sm text-blue-700">⏳ Submitting...</p>
          </div>
        )}

        {/* Buttons */}
        <div className="flex gap-2">
          <button
            onClick={handleConfirm}
            disabled={isLoading}
            className={`flex-1 px-4 py-2 rounded font-medium text-sm ${
              isLoading
                ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                : 'bg-blue-500 text-white hover:bg-blue-600'
            }`}
          >
            {isLoading ? '⏳ Submitting...' : '✅ Confirm Rejection'}
          </button>
          <button
            onClick={onCancel}
            disabled={isLoading}
            className={`flex-1 px-4 py-2 rounded font-medium text-sm ${
              isLoading
                ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                : 'bg-gray-300 text-gray-700 hover:bg-gray-400'
            }`}
          >
            ❌ Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
```

### File 6: Main Page (`frontend/components/phase5_hitl/Phase5HITLReview.tsx`)

```typescript
import React, { useEffect, useState } from 'react';
import { usePhase5API } from './usePhase5API';
import { ArtifactCard } from './ArtifactCard';
import { RejectionForm } from './RejectionForm';
import { ArtifactStatus, ApprovalStatusResponse } from '../../types/phase5';

interface Phase5HITLReviewProps {
  runId: string;
  onPhase6Complete?: () => void;  // Called when approved & moving to Phase 6
}

export function Phase5HITLReview({
  runId,
  onPhase6Complete
}: Phase5HITLReviewProps) {
  // State
  const [artifacts, setArtifacts] = useState<ArtifactStatus[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null);
  const [showRejectionForm, setShowRejectionForm] = useState(false);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);
  const [isApproving, setIsApproving] = useState(false);
  const [initialLoad, setInitialLoad] = useState(true);

  const { loading, error, getApprovalStatus, approveAll, rejectArtifact } =
    usePhase5API(runId);

  // Load initial status on mount
  useEffect(() => {
    const loadInitial = async () => {
      const data: ApprovalStatusResponse | null = await getApprovalStatus();
      if (data?.artifacts) {
        setArtifacts(data.artifacts);
      }
      setInitialLoad(false);
    };

    loadInitial();
  }, [getApprovalStatus]);

  // Polling logic
  useEffect(() => {
    if (initialLoad) return;

    const anyRegenerating = artifacts.some(a => a.status === 'regenerating');

    if (anyRegenerating && !pollingInterval) {
      // Start polling every 5 seconds
      const interval = setInterval(async () => {
        const data: ApprovalStatusResponse | null = await getApprovalStatus();
        if (data?.artifacts) {
          setArtifacts(data.artifacts);
        }
      }, 5000);
      setPollingInterval(interval);
    } else if (!anyRegenerating && pollingInterval) {
      // Stop polling
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }

    return () => {
      if (pollingInterval) clearInterval(pollingInterval);
    };
  }, [artifacts, pollingInterval, getApprovalStatus, initialLoad]);

  // Handle approve all
  const handleApproveAll = async () => {
    setIsApproving(true);
    const response = await approveAll();

    if (response?.status === 'ok') {
      alert('✅ All artifacts approved! Moving to Phase 6...');
      if (onPhase6Complete) {
        onPhase6Complete();
      } else {
        // Redirect to Phase 6
        window.location.href = `/runs/${runId}/phase6`;
      }
    } else {
      alert('❌ Error approving artifacts: ' + (response?.message || 'Unknown error'));
    }

    setIsApproving(false);
  };

  // Handle rejection confirm
  const handleRejectConfirm = async (
    feedback: string,
    rejectedSlides?: number[] | null,
    approvedSlides?: number[] | null
  ) => {
    const payload = {
      artifact_type: selectedArtifact!,
      rejected_slides: rejectedSlides || null,
      approved_slides: approvedSlides || null,
      user_feedback: feedback || undefined
    };

    const response = await rejectArtifact(payload);

    if (response?.status === 'regenerating' || response?.status === 'max_rejections') {
      // Close form
      setShowRejectionForm(false);
      setSelectedArtifact(null);

      // Refresh status
      const data: ApprovalStatusResponse | null = await getApprovalStatus();
      if (data?.artifacts) {
        setArtifacts(data.artifacts);
      }
    } else {
      alert('❌ Error rejecting artifact: ' + (response?.message || 'Unknown error'));
    }
  };

  // Counters
  const approvedCount = artifacts.filter(a => a.status === 'approved').length;
  const regeneratingCount = artifacts.filter(a => a.status === 'regenerating').length;
  const pendingCount = artifacts.filter(a => a.status === 'pending').length;

  if (initialLoad) {
    return (
      <div className="p-6 bg-gray-50 min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">Loading artifacts...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">🎯 Phase 5: Design Review</h1>
        <p className="text-gray-600">
          Review your artifacts and approve them or reject for regeneration.
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
          ❌ Error: {error}
        </div>
      )}

      {/* Status Summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {/* Pending */}
        <div className="p-4 bg-yellow-50 border-l-4 border-yellow-400 rounded">
          <p className="text-sm text-gray-700">⏳ Pending</p>
          <p className="text-3xl font-bold text-yellow-700">{pendingCount}</p>
          <p className="text-xs text-gray-600 mt-1">Waiting for approval</p>
        </div>

        {/* Regenerating */}
        <div className="p-4 bg-blue-50 border-l-4 border-blue-400 rounded">
          <p className="text-sm text-gray-700">🔄 Regenerating</p>
          <p className="text-3xl font-bold text-blue-700">{regeneratingCount}</p>
          <p className="text-xs text-gray-600 mt-1">30-60 seconds remaining</p>
        </div>

        {/* Approved */}
        <div className="p-4 bg-green-50 border-l-4 border-green-400 rounded">
          <p className="text-sm text-gray-700">✅ Approved</p>
          <p className="text-3xl font-bold text-green-700">{approvedCount}</p>
          <p className="text-xs text-gray-600 mt-1">Ready for Phase 6</p>
        </div>
      </div>

      {/* Polling Indicator */}
      {regeneratingCount > 0 && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded flex items-center gap-2">
          <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
          <span className="text-sm text-blue-700">
            Polling for regeneration updates every 5 seconds...
          </span>
        </div>
      )}

      {/* Artifacts List */}
      <div className="bg-white rounded-lg p-6 mb-6">
        <h2 className="text-xl font-bold mb-4">Artifacts for Review</h2>

        {artifacts.length === 0 ? (
          <p className="text-gray-500 text-center py-8">Loading artifacts...</p>
        ) : (
          <div className="space-y-3">
            {artifacts.map(artifact => (
              <ArtifactCard
                key={artifact.artifact_type}
                artifact={artifact}
                isSelected={selectedArtifact === artifact.artifact_type}
                onReject={() => {
                  setSelectedArtifact(artifact.artifact_type);
                  setShowRejectionForm(true);
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Rejection Form Modal */}
      {showRejectionForm && selectedArtifact && (
        <RejectionForm
          artifactType={selectedArtifact}
          totalSlides={
            artifacts.find(a => a.artifact_type === selectedArtifact)?.total_slides
          }
          onConfirm={handleRejectConfirm}
          onCancel={() => {
            setShowRejectionForm(false);
            setSelectedArtifact(null);
          }}
          isLoading={loading}
        />
      )}

      {/* Approve All Button */}
      <div className="bg-white rounded-lg p-6">
        <button
          onClick={handleApproveAll}
          disabled={regeneratingCount > 0 || isApproving}
          className={`w-full px-6 py-4 rounded-lg text-lg font-bold transition ${
            regeneratingCount > 0 || isApproving
              ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
              : 'bg-green-500 text-white hover:bg-green-600'
          }`}
        >
          {isApproving ? '⏳ Approving...' : '✅ Approve All & Move to Phase 6'}
        </button>
        <p className="text-sm text-gray-600 mt-3 text-center">
          {approvedCount}/{artifacts.length} artifacts ready •{' '}
          {regeneratingCount > 0 && 'Waiting for regeneration to complete...'}
          {regeneratingCount === 0 && pendingCount > 0 && 'Review pending artifacts'}
          {regeneratingCount === 0 && pendingCount === 0 && 'All artifacts approved!'}
        </p>
      </div>
    </div>
  );
}
```

### File 7: Route Page (`frontend/pages/RunPhase5.tsx`)

```typescript
import React from 'react';
import { useParams } from 'react-router-dom';
import { Phase5HITLReview } from '../components/phase5_hitl/Phase5HITLReview';

export function RunPhase5Page() {
  const { runId } = useParams<{ runId: string }>();

  if (!runId) {
    return <div className="p-6">Error: runId not found</div>;
  }

  return (
    <Phase5HITLReview
      runId={runId}
      onPhase6Complete={() => {
        // Redirect to Phase 6
        window.location.href = `/runs/${runId}/phase6`;
      }}
    />
  );
}
```

### File 8: Router (`frontend/App.tsx` - Add This Route)

```typescript
// In your router setup, add this route:

import { RunPhase5Page } from './pages/RunPhase5';

const routes = [
  // ... other routes ...
  {
    path: '/runs/:runId/phase5',
    element: <RunPhase5Page />
  }
  // ... other routes ...
];
```

---

## Integration Steps

### Step 1: Create Folder Structure
```bash
mkdir -p frontend/components/phase5_hitl
mkdir -p frontend/types
```

### Step 2: Create All Files
Copy-paste each code section above into the respective file:
- `frontend/types/phase5.ts`
- `frontend/components/phase5_hitl/usePhase5API.ts`
- `frontend/components/phase5_hitl/ArtifactCard.tsx`
- `frontend/components/phase5_hitl/SlideSelector.tsx`
- `frontend/components/phase5_hitl/RejectionForm.tsx`
- `frontend/components/phase5_hitl/Phase5HITLReview.tsx`
- `frontend/pages/RunPhase5.tsx`

### Step 3: Add Route
In `frontend/App.tsx`, add:
```typescript
import { RunPhase5Page } from './pages/RunPhase5';

// In router config:
{
  path: '/runs/:runId/phase5',
  element: <RunPhase5Page />
}
```

### Step 4: Verify Imports
Make sure all imports work:
```bash
cd frontend
npm install  # If any new dependencies needed
npm start     # Start dev server
```

### Step 5: Test URL
Navigate to: `http://localhost:3000/runs/{any_run_id}/phase5`

You should see the Phase 5 page load with artifacts!

---

## Testing Guide

### Test 1: Initial Load
```
1. Navigate to /runs/{runId}/phase5
   Expected: Page loads with 7 artifact cards
   Expected: Status shows correct counts (pending/regenerating/approved)
   Expected: All [View] and [Reject] buttons visible
```

### Test 2: View Artifact
```
1. Click [View] on any artifact
   Expected: New tab opens with artifact file
   Expected: File can be opened in proper viewer
```

### Test 3: PPTX Partial Rejection (Main Flow)
```
Step 1: Click [Reject] on PPTX
   Expected: Rejection form opens
   Expected: Slide selector shows 7 checkboxes
   Expected: All checkboxes checked (all slides "Keep")

Step 2: Uncheck slides 2 & 4
   Expected: Checkbox state changes
   Expected: Slide numbers show ❌ for unchecked

Step 3: Type feedback "Improve design"
   Expected: Text appears in textarea
   Expected: Character count shows correctly

Step 4: Click [Confirm Rejection]
   Expected: Form closes
   Expected: PPTX card shows v2, status=regenerating
   Expected: Spinner appears
   Expected: "Polling..." message shown

Step 5: Wait ~30-60 seconds
   Expected: Status changes to pending (automatically)
   Expected: Spinner disappears
   Expected: Card shows "✅ Ready"

Step 6: Click [View]
   Expected: pptx_v2.pptx opens
   Expected: Slides 1,3,5,6,7 unchanged from v1
   Expected: Slides 2,4 are NEW/different
```

### Test 4: DOCX Full Rejection
```
Step 1: Click [Reject] on DOCX
   Expected: Form opens
   Expected: NO slide selector (not PPTX)
   Expected: Message: "regenerates entire DOCX"

Step 2: Type feedback
   Expected: Text captured

Step 3: Click [Confirm Rejection]
   Expected: DOCX v2 shows, status=regenerating

Step 4: Wait ~30 seconds
   Expected: Status changes to pending

Step 5: Click [View]
   Expected: docx_v2.docx opens
   Expected: Content completely different from v1
```

### Test 5: Max Rejections (3/3)
```
Step 1: Reject PPTX 3 times
   Expected: v1 → v2 → v3 → v4 created
   Expected: Each shows attempt count (1/3, 2/3, 3/3)

After 3rd rejection:
   Expected: [Reject] button DISABLED ❌
   Expected: Message shows "Max attempts reached"
   Expected: Must click [Approve All] to proceed

Step 2: Click [Approve All]
   Expected: v4 approved as-is
   Expected: Page redirects to Phase 6
```

### Test 6: Approve All (Happy Path)
```
1. All artifacts show status=pending (or approved)
   Expected: [Approve All] button ENABLED

2. Click [Approve All]
   Expected: Button shows "⏳ Approving..."
   Expected: All artifacts marked approved
   Expected: Message: "Moving to Phase 6..."
   Expected: Redirect to /runs/{runId}/phase6
```

### Test 7: Polling Works
```
1. Reject PPTX → v2 shows regenerating
   Expected: Polling starts (every 5 seconds)
   Expected: "Polling..." message visible

2. Check console network tab
   Expected: GET /phase5/approval-status every 5 seconds

3. When regeneration completes
   Expected: Status changes (regenerating → pending)
   Expected: Polling stops
   Expected: [Reject] button enabled again
```

### Test 8: Multiple Artifacts
```
1. Reject PPTX (status=regenerating)
2. Reject DOCX (status=regenerating)
   Expected: Both show spinner
   Expected: XLSX/PDF/SOP/Narrative/DrawIO show normal

3. Polling continues for both
   Expected: When either completes, status updates

4. When all ready
   Expected: [Approve All] becomes enabled
   Expected: Can approve everything together
```

### Test 9: Error Handling
```
1. Disconnect network
2. Try to click [Approve All]
   Expected: Error message shown
   Expected: Network error displayed

3. Reconnect network
4. Try again
   Expected: Works normally
```

---

## Troubleshooting

### Issue: Artifacts show count as (0)
**Cause**: run_dir not passed to Phase 4
**Fix**: Already fixed in orchestrator.py (added 'run_dir' to KEEP_VARS)
**Verify**: Check line 1120 includes 'run_dir'

### Issue: [Reject] button always disabled
**Cause**: Status not "pending" or attempt_count = 3
**Fix**: Check artifact.status and artifact.attempt_count in console
**Debug**: Log in ArtifactCard: `console.log('Status:', artifact.status, 'Attempt:', artifact.attempt_count)`

### Issue: Polling not working
**Cause**: Interval not set or cleared incorrectly
**Fix**: Check useEffect dependencies in Phase5HITLReview
**Debug**: Open console, check if GET requests happen every 5 seconds

### Issue: Slide selector not showing
**Cause**: artifactType !== 'pptx'
**Fix**: Verify artifactType is lowercase 'pptx' not 'PPTX'
**Debug**: Log in RejectionForm: `console.log('Type:', artifactType, 'Is PPTX:', artifactType === 'pptx')`

### Issue: Form not closing after reject
**Cause**: API response doesn't have status='regenerating'
**Fix**: Check backend response in Network tab
**Debug**: Console log: `console.log('Response:', response)`

### Issue: Page not redirecting to Phase 6
**Cause**: onPhase6Complete not triggered or URL wrong
**Fix**: Add `onPhase6Complete` prop to Phase5HITLReview
**Debug**: Check if button click calls handleApproveAll

### Issue: Styles not applying
**Cause**: Tailwind CSS not configured
**Fix**: Make sure tailwindcss is installed and postcss configured
**Debug**: Check if other pages have Tailwind styles

### Issue: API returns 401 Unauthorized
**Cause**: User not authenticated
**Fix**: Check JWT token in localStorage
**Debug**: Check Authorization header in Network tab

### Issue: Artifacts API returns (0)
**Cause**: run_artifacts endpoint not finding files
**Fix**: Verify run_dir path: `workspace/{project_id}/runs/{run_id}/`
**Debug**: Check orchestrator line 2087 has correct path

---

## Summary

### What You Build
- 7 React components + 1 hook + 1 types file + 1 route page
- ~800 lines of React code
- Full approval/rejection UI with polling

### What Backend Does
- Tracks approval state in database
- Handles regeneration queueing
- Returns artifact status via API
- Manages version history

### How It Works
1. User sees artifacts
2. User rejects → backend creates v2, starts regeneration
3. UI polls → detects status change
4. User reviews v2
5. User approves → Phase 6

### Testing Checklist
- [ ] Page loads correctly
- [ ] All 7 artifacts display
- [ ] [View] opens files
- [ ] PPTX slide selector works
- [ ] Rejection submits correctly
- [ ] Status updates automatically (polling)
- [ ] Approve All redirects to Phase 6
- [ ] Max rejections handled
- [ ] Errors handled gracefully

---

**That's everything!** Your UI developer can now build the complete Phase 5 interface. 🚀

