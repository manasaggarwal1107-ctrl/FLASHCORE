import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import (
    OrgContext,
    get_current_user,
    get_user_organisations,
    resolve_org_context_for_id,
)
from app.core.database import get_db
from app.models.auth import User
from app.models.organisation import Organisation, OrganisationMembership
from app.models.rossmann import AuditLog

router = APIRouter(prefix="/api/organisations", tags=["Organisations"])

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OrganisationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Organisation name must be at least 2 characters.")
        return cleaned

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not SLUG_RE.fullmatch(cleaned):
            raise ValueError(
                "Slug must contain lowercase letters, numbers, and single hyphens."
            )
        return cleaned


class OrganisationSummaryOut(BaseModel):
    organisation_id: int
    name: str
    slug: str
    status: str
    role: str
    membership_status: str


class MembershipCreate(BaseModel):
    user_id: int | None = Field(default=None, gt=0)
    email: str | None = Field(default=None, min_length=5, max_length=320)
    role: Literal["owner", "admin", "analyst", "operator"] = "analyst"

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()


class MembershipUpdate(BaseModel):
    role: Literal["owner", "admin", "analyst", "operator"] | None = None
    status: Literal["active", "revoked"] | None = None


class MembershipOut(BaseModel):
    id: int
    organisation_id: int
    user_id: int
    email: str
    role: str
    status: str
    user_status: str
    created_at: datetime


def _require_org_admin_context(
    org_id: int,
    current_user: User,
    db: Session,
) -> OrgContext:
    ctx = resolve_org_context_for_id(db, current_user, org_id)
    if ctx.membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Organisation owner or admin role is required.",
        )
    return ctx


def _lock_active_owners(db: Session, org_id: int) -> list[OrganisationMembership]:
    return list(
        db.scalars(
            select(OrganisationMembership)
            .where(
                OrganisationMembership.organisation_id == org_id,
                OrganisationMembership.role == "owner",
                OrganisationMembership.status == "active",
            )
            .order_by(OrganisationMembership.id)
            .with_for_update()
        ).all()
    )


@router.get("", response_model=list[OrganisationSummaryOut])
def list_my_organisations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = get_user_organisations(db, current_user.id)
    return [
        OrganisationSummaryOut(
            organisation_id=org.id,
            name=org.name,
            slug=org.slug,
            status=org.status,
            role=membership.role,
            membership_status=membership.status,
        )
        for membership, org in rows
    ]


@router.post("", response_model=OrganisationSummaryOut, status_code=201)
def create_organisation(
    payload: OrganisationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.scalar(
        select(Organisation).where(Organisation.slug == payload.slug)
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="An organisation with this slug already exists.",
        )

    org = Organisation(
        name=payload.name,
        slug=payload.slug,
        status="active",
    )
    try:
        db.add(org)
        db.flush()

        membership = OrganisationMembership(
            organisation_id=org.id,
            user_id=current_user.id,
            role="owner",
            status="active",
        )
        db.add(membership)
        db.add(
            AuditLog(
                organisation_id=org.id,
                actor_type="user",
                actor_ref=current_user.email,
                action="organisation_created",
                entity_name="organisations",
                entity_id=str(org.id),
                details={
                    "name": org.name,
                    "slug": org.slug,
                    "owner_user_id": current_user.id,
                    "status": "success",
                },
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An organisation with this slug already exists.",
        ) from exc

    db.refresh(org)
    db.refresh(membership)
    return OrganisationSummaryOut(
        organisation_id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        role=membership.role,
        membership_status=membership.status,
    )


@router.get("/{org_id}/memberships", response_model=list[MembershipOut])
def list_memberships(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_org_admin_context(org_id, current_user, db)
    rows = db.execute(
        select(OrganisationMembership, User)
        .join(User, User.id == OrganisationMembership.user_id)
        .where(OrganisationMembership.organisation_id == org_id)
        .order_by(OrganisationMembership.id.asc())
    ).all()

    return [
        MembershipOut(
            id=membership.id,
            organisation_id=membership.organisation_id,
            user_id=user.id,
            email=user.email,
            role=membership.role,
            status=membership.status,
            user_status=user.status,
            created_at=membership.created_at,
        )
        for membership, user in rows
    ]


@router.post("/{org_id}/memberships", response_model=MembershipOut, status_code=201)
def add_membership(
    org_id: int,
    payload: MembershipCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ctx = _require_org_admin_context(org_id, current_user, db)

    if payload.role == "owner" and ctx.membership.role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only an organisation owner can assign the owner role.",
        )

    if payload.user_id is None and payload.email is None:
        raise HTTPException(
            status_code=422,
            detail="Provide either user_id or email.",
        )

    if payload.user_id is not None:
        target_user = db.get(User, payload.user_id)
    else:
        target_user = db.scalar(
            select(User).where(func.lower(User.email) == payload.email)
        )

    if target_user is None:
        raise HTTPException(status_code=404, detail="Target user not found.")

    existing = db.scalar(
        select(OrganisationMembership).where(
            OrganisationMembership.organisation_id == org_id,
            OrganisationMembership.user_id == target_user.id,
        )
    )
    if existing is not None:
        if existing.status == "active":
            raise HTTPException(
                status_code=409,
                detail="User is already an active member of this organisation.",
            )
        existing.role = payload.role
        existing.status = "active"
        existing.updated_at = datetime.now(timezone.utc)
        membership = existing
    else:
        membership = OrganisationMembership(
            organisation_id=org_id,
            user_id=target_user.id,
            role=payload.role,
            status="active",
        )
        db.add(membership)
        db.flush()

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=ctx.membership.role,
            actor_ref=current_user.email,
            action="organisation_membership_added",
            entity_name="organisation_memberships",
            entity_id=str(membership.id),
            details={
                "target_user_id": target_user.id,
                "target_email": target_user.email,
                "role": payload.role,
                "status": "success",
            },
        )
    )
    db.commit()
    db.refresh(membership)

    return MembershipOut(
        id=membership.id,
        organisation_id=membership.organisation_id,
        user_id=target_user.id,
        email=target_user.email,
        role=membership.role,
        status=membership.status,
        user_status=target_user.status,
        created_at=membership.created_at,
    )


@router.patch("/{org_id}/memberships/{member_user_id}", response_model=MembershipOut)
def update_membership(
    org_id: int,
    member_user_id: int,
    payload: MembershipUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ctx = _require_org_admin_context(org_id, current_user, db)

    if payload.role is None and payload.status is None:
        raise HTTPException(
            status_code=422,
            detail="Provide role and/or status to update.",
        )

    membership = db.scalar(
        select(OrganisationMembership).where(
            OrganisationMembership.organisation_id == org_id,
            OrganisationMembership.user_id == member_user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Organisation membership not found.")

    target_user = db.get(User, member_user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="Target user not found.")

    if (membership.role == "owner" or payload.role == "owner") and ctx.membership.role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only an organisation owner can modify owner memberships.",
        )

    demoting_owner = (
        membership.role == "owner"
        and membership.status == "active"
        and (
            (payload.role is not None and payload.role != "owner")
            or payload.status == "revoked"
        )
    )
    if demoting_owner:
        active_owners = _lock_active_owners(db, org_id)
        if len(active_owners) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot revoke or demote the last active organisation owner.",
            )

    prev_role = membership.role
    prev_status = membership.status

    if payload.role is not None:
        membership.role = payload.role
    if payload.status is not None:
        membership.status = payload.status
    membership.updated_at = datetime.now(timezone.utc)

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=ctx.membership.role,
            actor_ref=current_user.email,
            action="organisation_membership_updated",
            entity_name="organisation_memberships",
            entity_id=str(membership.id),
            details={
                "target_user_id": target_user.id,
                "previous_role": prev_role,
                "new_role": membership.role,
                "previous_status": prev_status,
                "new_status": membership.status,
                "status": "success",
            },
        )
    )
    db.commit()
    db.refresh(membership)

    return MembershipOut(
        id=membership.id,
        organisation_id=membership.organisation_id,
        user_id=target_user.id,
        email=target_user.email,
        role=membership.role,
        status=membership.status,
        user_status=target_user.status,
        created_at=membership.created_at,
    )
