import json
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.tz import ist_now
from src.core.db.base import Base


def utcnow() -> datetime:
    return ist_now()


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_admin: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user", server_default="user")


class RefreshToken(Base):
    """Server-tracked refresh JWTs (jti rotation + revocation)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replaced_by_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ProjectBrand(Base):
    __tablename__ = "project_brands"
    __table_args__ = (Index("ix_project_brands_project_id", "project_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False)
    primary_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    font_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    font_size_base: Mapped[int | None] = mapped_column(Integer, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    footer_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class EngagementMeta(Base):
    """Additive engagement metadata (code/type/stage/progress) layered on top of a Project.

    Mirrors ProjectBrand's shape/placement: one optional side-row per project,
    read with defaults when absent so every Project can be treated as a valid
    "Engagement" row by the frontend without requiring a human to seed it.
    """

    __tablename__ = "engagement_meta"
    __table_args__ = (Index("ix_engagement_meta_project_id", "project_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_task: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    client_org: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    sponsor_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_measures: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_close: Mapped[str | None] = mapped_column(String(32), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        Index("ix_memberships_project_user", "project_id", "user_id"),
        UniqueConstraint("project_id", "user_id", name="uq_memberships_project_user"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_project_created_at", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    output_types: Mapped[str] = mapped_column(Text, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    plan_payload: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pause_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resume_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    abort_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_cache_read: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_cache_creation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)


class SwarmTeam(Base):
    """Logical agent team for a run (swarm orchestration)."""

    __tablename__ = "swarm_teams"
    __table_args__ = (Index("ix_swarm_teams_run_id", "run_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class SwarmTeammate(Base):
    __tablename__ = "swarm_teammates"
    __table_args__ = (Index("ix_swarm_teammates_team", "team_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(64), ForeignKey("swarm_teams.id"), nullable=False)
    teammate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="worker")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class SwarmMessage(Base):
    __tablename__ = "swarm_messages"
    __table_args__ = (
        Index("ix_swarm_messages_run_created", "run_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), nullable=False)
    team_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("swarm_teams.id"), nullable=True)
    from_teammate: Mapped[str] = mapped_column(String(64), nullable=False)
    to_teammate: Mapped[str | None] = mapped_column(String(64), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RunEvent(Base):
    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    @property
    def payload_json(self) -> dict:
        try:
            obj = json.loads(self.payload)
            return obj if isinstance(obj, dict) else {"value": obj}
        except Exception:
            return {"value": self.payload}


class RunTask(Base):
    __tablename__ = "run_tasks"
    __table_args__ = (
        Index("ix_run_tasks_run_phase", "run_id", "phase"),
        Index("ix_run_tasks_run_status", "run_id", "status"),
    )

    # Task ids ("context", "plan", "qa", …) repeat in every run, so the key is (id, run_id).
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), primary_key=True, index=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    phase: Mapped[str] = mapped_column(String(16), nullable=False, default="act")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depends_on_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    swarm_team_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("swarm_teams.id"), nullable=True)
    assigned_teammate_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skills_used_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    tools_invoked_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    output_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class HookExecution(Base):
    __tablename__ = "hook_executions"
    __table_args__ = (
        Index("ix_hook_exec_run_point_name", "run_id", "hook_point", "hook_name"),
        Index("ix_hook_exec_idem", "run_id", "idempotency_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), nullable=False, index=True)
    hook_point: Mapped[str] = mapped_column(String(64), nullable=False)
    hook_name: Mapped[str] = mapped_column(String(128), nullable=False)
    hook_exec_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="OK")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class HookControl(Base):
    __tablename__ = "hook_controls"
    __table_args__ = (
        Index("ix_hook_controls_project_hook", "project_id", "hook_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    hook_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ConsentLedger(Base):
    __tablename__ = "consent_ledger"
    __table_args__ = (
        Index("ix_consent_ledger_project_principal", "project_id", "principal_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    principal_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    granted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DPDPRightsRequest(Base):
    __tablename__ = "dpdp_rights_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_type: Mapped[str] = mapped_column(String(32), nullable=False)  # access|correction|erasure
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class MemoryEvent(Base):
    __tablename__ = "memory_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)


class ProjectMemoryProfile(Base):
    __tablename__ = "project_memory_profiles"

    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), primary_key=True)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class UserProjectPreference(Base):
    """Per-user, per-project personalization (v4 §5.1): context_lines merged into assembled context."""

    __tablename__ = "user_project_preferences"

    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), primary_key=True)
    preferences_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Creative Studio")
    skill_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source_freshness_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)


class ConversationTurn(Base):
    """A conversation message being answered in the background (see POST .../conversation/messages?background=true)."""

    __tablename__ = "conversation_turns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    # running | done | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    phase: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    response_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class MemoryItem(Base):
    __tablename__ = "memory_items"
    __table_args__ = (
        UniqueConstraint("project_id", "memory_type", "key", name="uq_memory_item_project_type_key"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # preference|constraint|decision|fact
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="chat")
    consent_state: Mapped[str] = mapped_column(String(16), nullable=False, default="allowed")
    # When set, optional DPDP Consent Ledger check for this principal (see memory_enforce_consent_ledger).
    principal_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    output_types_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Keep legacy DB column names for compatibility; expose output-type semantics in code.
    custom_output_types_json: Mapped[str] = mapped_column("custom_output_formats_json", Text, nullable=False, default="[]")
    output_type_representations_json: Mapped[str] = mapped_column("output_format_preferences_json", Text, nullable=False, default="{}")
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False, default="interval")  # interval|once
    cadence_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")  # active|paused|archived
    retry_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ScheduledTaskRun(Base):
    __tablename__ = "scheduled_task_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("scheduled_tasks.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("runs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)


class WikiPage(Base):
    """Persistent wiki pages (LLM-maintained, markdown format)."""

    __tablename__ = "wiki_pages"
    __table_args__ = (
        Index("ix_wiki_pages_wiki_type_project", "wiki_type", "project_id"),
        Index("ix_wiki_pages_project_slug", "project_id", "slug"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    wiki_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # "leading_practice" or "project"
    project_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("projects.id"), nullable=True, index=True)  # None for LP wiki
    page_name: Mapped[str] = mapped_column(String(255), nullable=False)  # File name without .md
    slug: Mapped[str] = mapped_column(String(255), nullable=False)  # URL-friendly identifier
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # entity|concept|comparison|template|synthesis|artifact
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown body
    frontmatter: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # YAML metadata as JSON
    inbound_links: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list of page IDs
    outbound_links: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list of page IDs
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)  # "system" for auto-generated
    source_memory_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    source_run_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")  # low|medium|high
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class WikiLog(Base):
    """Append-only log of wiki operations (ingest, query, lint, update)."""

    __tablename__ = "wiki_logs"
    __table_args__ = (
        Index("ix_wiki_logs_wiki_type_project_ts", "wiki_type", "project_id", "timestamp"),
        Index("ix_wiki_logs_operation_ts", "operation", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    wiki_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("projects.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # ingest|query|lint|update
    source_name: Mapped[str | None] = mapped_column(String(512), nullable=True)  # e.g., article title, run_id, URL
    pages_touched: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list of page IDs
    corrections_made: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list of corrections
    qa_results: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: {passed, issues, suggestions}
    executed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)  # "system" or user_id
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class WikiIndex(Base):
    """Catalog index of all wiki pages (updated on each ingest)."""

    __tablename__ = "wiki_indexes"
    __table_args__ = (
        Index("ix_wiki_indexes_wiki_type_project", "wiki_type", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    wiki_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("projects.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown: catalog of all pages by category
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category_counts: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON: {entity: N, concept: M, ...}


class ActivityEvent(Base):
    """Workbench activity feed: recent activity, the engagement activity tab and the admin audit trail."""

    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("projects.id"), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)


class Review(Base):
    """A review of one artifact version; `payload_json` holds the evidence checks and slide preview."""

    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("projects.id"), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    owner_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"), nullable=True, index=True)
    due_date: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="Awaiting review")
    risk: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(String(64), ForeignKey("reviews.id"), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    anchor: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    link: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class LpPractice(Base):
    """Leading Practice catalog entry; `payload_json` holds the detail panel content."""

    __tablename__ = "lp_practices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    maturity: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    version_label: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Approved")
    owner: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class SavedPractice(Base):
    __tablename__ = "saved_practices"
    __table_args__ = (UniqueConstraint("user_id", "practice_id", name="uq_saved_practices_user_practice"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    practice_id: Mapped[str] = mapped_column(String(64), ForeignKey("lp_practices.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class WorkbenchRecord(Base):
    """Generic seeded record for workbench inventories that have no workflow of their own
    (milestones, next actions, skill metadata, ingestion jobs, policies, role matrix, ...)."""

    __tablename__ = "workbench_records"
    __table_args__ = (UniqueConstraint("collection", "record_id", name="uq_workbench_records_collection_record"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DocumentJob(Base):
    """Async document parsing job tracking for Celery tasks."""

    __tablename__ = "document_jobs"
    __table_args__ = (
        Index("ix_document_jobs_job_id", "job_id"),
        Index("ix_document_jobs_project_id", "project_id"),
        Index("ix_document_jobs_user_id", "user_id"),
        Index("ix_document_jobs_status", "status"),
        Index("ix_document_jobs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ingestion scope ("library")
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    parse_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DocumentFile(Base):
    """An uploaded file as stored in SeaweedFS (S3)."""

    __tablename__ = "document_files"
    __table_args__ = (
        Index("ix_document_files_project_id", "project_id"),
        Index("ix_document_files_job_id", "job_id"),
        Index("ix_document_files_sha256", "sha256_hash"),
        Index("ix_document_files_seaweedfs_id", "seaweedfs_file_id"),
        Index("ix_document_files_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ingestion scope ("library")
    job_id: Mapped[str] = mapped_column(String(255), ForeignKey("document_jobs.job_id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seaweedfs_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # S3 object key
    seaweedfs_volume_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_source: Mapped[str | None] = mapped_column(String(50), nullable=True, default="api_upload")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ParsedDocument(Base):
    """Docling output for one DocumentFile."""

    __tablename__ = "parsed_documents"
    __table_args__ = (
        Index("ix_parsed_documents_file_id", "document_file_id"),
        Index("ix_parsed_documents_project_id", "project_id"),
        Index("ix_parsed_documents_status", "parsing_status"),
        Index("ix_parsed_documents_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_file_id: Mapped[str] = mapped_column(String(64), ForeignKey("document_files.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ingestion scope ("library")
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_count: Mapped[int | None] = mapped_column(Integer, default=0)
    image_count: Mapped[int | None] = mapped_column(Integer, default=0)
    parsing_status: Mapped[str | None] = mapped_column(String(20), default="pending")
    parsing_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ChunkArchive(Base):
    """Full-text chunks of a parsed document (the source of truth; Qdrant holds their vectors)."""

    __tablename__ = "chunk_archive"
    __table_args__ = (
        Index("ix_chunk_archive_file_id", "document_file_id"),
        Index("ix_chunk_archive_parsed_id", "parsed_document_id"),
        Index("ix_chunk_archive_project_id", "project_id"),
        Index("ix_chunk_archive_source_type", "source_type"),
        Index("ix_chunk_archive_created", "created_at"),
        Index("ix_chunk_archive_file_chunk", "document_file_id", "chunk_number"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_file_id: Mapped[str] = mapped_column(String(64), ForeignKey("document_files.id"), nullable=False)
    parsed_document_id: Mapped[str] = mapped_column(String(64), ForeignKey("parsed_documents.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ingestion scope ("library")
    chunk_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # main_text, table, image
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DocumentChunkLink(Base):
    """Which passages make up a document version, in order. A passage (chunk_archive row) is stored and embedded
    once per unique text and can be linked from many versions/documents."""

    __tablename__ = "document_chunk_links"
    __table_args__ = (
        Index("ix_document_chunk_links_chunk", "chunk_id"),
        Index("ix_document_chunk_links_document", "document_file_id"),
    )

    document_file_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chunk_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(64), ForeignKey("chunk_archive.id"), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # passage existed before this version
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ChunkEmbedding(Base):
    """Embedding of one chunk and the Qdrant point that holds it."""

    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        Index("ix_chunk_embeddings_chunk_id", "chunk_id"),
        Index("ix_chunk_embeddings_file_id", "document_file_id"),
        Index("ix_chunk_embeddings_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(64), ForeignKey("chunk_archive.id"), nullable=False)
    document_file_id: Mapped[str] = mapped_column(String(64), ForeignKey("document_files.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ingestion scope ("library")
    embedding: Mapped[list] = mapped_column(JSON, nullable=False)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ExtractedFact(Base):
    __tablename__ = "extracted_facts"
    __table_args__ = (
        Index("ix_extracted_facts_parsed_id", "parsed_document_id"),
        Index("ix_extracted_facts_project_id", "project_id"),
        Index("ix_extracted_facts_type", "fact_type"),
        Index("ix_extracted_facts_name", "fact_name"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    parsed_document_id: Mapped[str] = mapped_column(String(64), ForeignKey("parsed_documents.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ingestion scope ("library")
    fact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    fact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    fact_value: Mapped[dict | str | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, default=0.5)
    source_context: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class WikiPageDraft(Base):
    __tablename__ = "wiki_pages_draft"
    __table_args__ = (
        Index("ix_wiki_draft_parsed_id", "parsed_document_id"),
        Index("ix_wiki_draft_project_id", "project_id"),
        Index("ix_wiki_draft_entity", "entity_name", "entity_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    parsed_document_id: Mapped[str] = mapped_column(String(64), ForeignKey("parsed_documents.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ingestion scope ("library")
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_facts: Mapped[list | str | None] = mapped_column(JSON, nullable=True)
    is_deduplicated: Mapped[bool | None] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class WikiPageFinal(Base):
    __tablename__ = "wiki_pages_final"
    __table_args__ = (
        Index("ix_wiki_final_project_id", "project_id"),
        Index("ix_wiki_final_entity", "entity_name"),
        Index("ix_wiki_final_published", "is_published"),
        Index("ix_wiki_final_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ingestion scope ("library")
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list | str | None] = mapped_column(JSON, nullable=True)
    source_facts: Mapped[list | str | None] = mapped_column(JSON, nullable=True)
    merge_info: Mapped[dict | str | None] = mapped_column(JSON, nullable=True)
    is_published: Mapped[bool | None] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class EmbeddingsMetadata(Base):
    __tablename__ = "embeddings_metadata"
    __table_args__ = (
        Index("ix_embeddings_wiki_id", "wiki_id"),
        Index("ix_embeddings_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    wiki_id: Mapped[str] = mapped_column(String(64), ForeignKey("wiki_pages_final.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ingestion scope ("library")
    embedding_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qdrant_collection: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class TaskFailure(Base):
    """Task failure tracking for error handling."""

    __tablename__ = "task_failures"
    __table_args__ = (
        Index("ix_task_failures_document", "document_file_id"),
        Index("ix_task_failures_project", "project_id"),
        Index("ix_task_failures_task", "task_name"),
        Index("ix_task_failures_error_type", "error_type"),
        Index("ix_task_failures_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    document_file_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str] = mapped_column(String(500), nullable=False)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False)
    is_final_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class InAppNotification(Base):
    """In-app notifications for document processing status updates."""

    __tablename__ = "in_app_notifications"
    __table_args__ = (
        Index("ix_in_app_notifications_user", "user_id"),
        Index("ix_in_app_notifications_project", "project_id"),
        Index("ix_in_app_notifications_type", "notification_type"),
        Index("ix_in_app_notifications_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False)
    document_file_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ingestion scope ("library")
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
