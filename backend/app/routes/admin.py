from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user, require_roles
from app.core.database import get_db
from app.models.auth import AuthSession, User
from app.models.rossmann import AuditLog


router = APIRouter(
    prefix="/api/admin",
    tags=["Administration"],
    dependencies=[Depends(require_roles("admin"))],
)


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    status: str
    created_at: datetime


class RoleUpdate(BaseModel):
    role: Literal["admin", "analyst", "operator"]


class StatusUpdate(BaseModel):
    status: Literal["active", "disabled"]


def lock_active_admins(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.role == "admin", User.status == "active")
            .order_by(User.id)
            .with_for_update()
        ).all()
    )


def revoke_user_sessions(db: Session, user_id: int) -> None:
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(
        select(User).order_by(User.id)
    ).all()


@router.patch(
    "/users/{user_id}/role",
    response_model=AdminUserResponse,
)
def update_user_role(
    user_id: int,
    payload: RoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.id == current_user.id:
        raise HTTPException(
            status_code=409,
            detail="You cannot change your own role.",
        )

    if user.role == payload.role:
        return user

    if user.role == "admin" and user.status == "active":
        active_admins = lock_active_admins(db)

        if len(active_admins) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot demote the last active administrator.",
            )

    user.role = payload.role
    user.updated_at = datetime.now(timezone.utc)

    revoke_user_sessions(db, user.id)

    db.commit()
    db.refresh(user)

    return user


@router.patch(
    "/users/{user_id}/status",
    response_model=AdminUserResponse,
)
def update_user_status(
    user_id: int,
    payload: StatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.id == current_user.id:
        raise HTTPException(
            status_code=409,
            detail="You cannot change your own account status.",
        )

    if user.status == payload.status:
        return user

    if (
        user.role == "admin"
        and user.status == "active"
        and payload.status == "disabled"
    ):
        active_admins = lock_active_admins(db)

        if len(active_admins) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot disable the last active administrator.",
            )

    user.status = payload.status
    user.updated_at = datetime.now(timezone.utc)

    if payload.status == "disabled":
        revoke_user_sessions(db, user.id)

    db.commit()
    db.refresh(user)

    return user


class AuditLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    occurred_at: datetime
    actor: str
    action: str
    entity_type: str
    entity_ref: str | None = None
    outcome: str | None = None
    metadata: dict | None = None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    total: int
    page: int
    page_size: int


def _sanitize_metadata(details: dict | None) -> dict | None:
    if not details or not isinstance(details, dict):
        return details
    sanitized = {}
    for k, v in details.items():
        if any(secret_term in k.lower() for secret_term in ("password", "token", "secret", "hash", "key", "auth")):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_metadata(v)
        else:
            sanitized[k] = v
    return sanitized


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    action: str | None = None,
    entity_type: str | None = Query(None, alias="entityType"),
    outcome: str | None = None,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    search: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_name == entity_type)
        count_query = count_query.where(AuditLog.entity_name == entity_type)
    if from_date:
        query = query.where(AuditLog.created_at >= from_date)
        count_query = count_query.where(AuditLog.created_at >= from_date)
    if to_date:
        query = query.where(AuditLog.created_at <= to_date)
        count_query = count_query.where(AuditLog.created_at <= to_date)
    if search:
        search_filter = (
            AuditLog.actor_ref.ilike(f"%{search}%")
            | AuditLog.actor_type.ilike(f"%{search}%")
            | AuditLog.action.ilike(f"%{search}%")
            | AuditLog.entity_name.ilike(f"%{search}%")
            | AuditLog.entity_id.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = db.scalar(count_query) or 0
    offset = (page - 1) * page_size
    records = db.scalars(query.order_by(AuditLog.id.desc()).offset(offset).limit(page_size)).all()

    items = []
    for log in records:
        actor = f"{log.actor_type}:{log.actor_ref}" if log.actor_ref else (log.actor_type or "system")
        details = _sanitize_metadata(log.details)
        out = "recorded"
        if details and isinstance(details, dict):
            out = details.get("status") or details.get("outcome") or "recorded"
        if outcome and out.lower() != outcome.lower():
            continue
        items.append({
            "id": str(log.id),
            "occurred_at": log.created_at,
            "actor": actor,
            "action": log.action,
            "entity_type": log.entity_name,
            "entity_ref": str(log.entity_id) if log.entity_id else None,
            "outcome": out,
            "metadata": details,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
