from dataclasses import dataclass
import uuid
from datetime import datetime, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.auth import AuthSession, User
from app.models.organisation import Organisation, OrganisationMembership

DEFAULT_ORGANISATION_NAME = "Default Workspace"
DEFAULT_ORGANISATION_SLUG = "default-workspace"

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class OrgContext:
    user: User
    organisation: Organisation
    membership: OrganisationMembership


def get_or_create_default_organisation(db: Session) -> Organisation:
    org = db.scalar(
        select(Organisation).where(Organisation.slug == DEFAULT_ORGANISATION_SLUG)
    )
    if org is not None:
        return org

    org = Organisation(
        name=DEFAULT_ORGANISATION_NAME,
        slug=DEFAULT_ORGANISATION_SLUG,
        status="active",
    )
    try:
        with db.begin_nested():
            db.add(org)
            db.flush()
        return org
    except IntegrityError:
        existing = db.scalar(
            select(Organisation).where(Organisation.slug == DEFAULT_ORGANISATION_SLUG)
        )
        if existing is None:
            raise
        return existing


def get_user_organisations(
    db: Session,
    user_id: int,
) -> list[tuple[OrganisationMembership, Organisation]]:
    rows = db.execute(
        select(OrganisationMembership, Organisation)
        .join(Organisation, Organisation.id == OrganisationMembership.organisation_id)
        .where(
            OrganisationMembership.user_id == user_id,
            OrganisationMembership.status == "active",
            Organisation.status == "active",
        )
        .order_by(
            (Organisation.slug != DEFAULT_ORGANISATION_SLUG).asc(),
            Organisation.id.asc(),
        )
    ).all()
    return [(row[0], row[1]) for row in rows]


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
        jti = uuid.UUID(payload["jti"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise unauthorized

    session = db.get(AuthSession, jti)

    if (
        session is None
        or session.user_id != user_id
        or session.revoked_at is not None
        or session.expires_at <= datetime.now(timezone.utc)
    ):
        raise unauthorized

    user = db.get(User, user_id)

    if user is None:
        raise unauthorized

    if user.status != "active":
        raise HTTPException(status_code=403, detail="Account is disabled.")

    return user


def require_roles(*allowed_roles: str):
    """Platform-level role dependency (e.g. global user administration)."""

    def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return role_dependency


def resolve_org_context_for_id(
    db: Session,
    current_user: User,
    organisation_id: int,
) -> OrgContext:
    row = db.execute(
        select(OrganisationMembership, Organisation)
        .join(Organisation, Organisation.id == OrganisationMembership.organisation_id)
        .where(
            OrganisationMembership.user_id == current_user.id,
            OrganisationMembership.organisation_id == organisation_id,
        )
    ).first()

    if row is None:
        raise HTTPException(
            status_code=403,
            detail="You do not belong to the requested organisation.",
        )

    membership, organisation = row

    if organisation.status != "active":
        raise HTTPException(
            status_code=403,
            detail="Organisation is not active.",
        )

    if membership.status != "active":
        raise HTTPException(
            status_code=403,
            detail="Organisation membership is not active.",
        )

    return OrgContext(
        user=current_user,
        organisation=organisation,
        membership=membership,
    )


def get_org_context(
    current_user: User = Depends(get_current_user),
    x_organisation_id: str | None = Header(default=None, alias="X-Organisation-Id"),
    db: Session = Depends(get_db),
) -> OrgContext:
    if x_organisation_id is not None and x_organisation_id.strip() != "":
        try:
            org_id = int(x_organisation_id.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="Invalid X-Organisation-Id header.",
            ) from exc

        if org_id <= 0:
            raise HTTPException(
                status_code=422,
                detail="X-Organisation-Id must be a positive integer.",
            )

        return resolve_org_context_for_id(db, current_user, org_id)

    memberships = get_user_organisations(db, current_user.id)
    if not memberships:
        raise HTTPException(
            status_code=403,
            detail="No active organisation membership found.",
        )

    membership, organisation = memberships[0]
    return OrgContext(
        user=current_user,
        organisation=organisation,
        membership=membership,
    )


def require_org_roles(*allowed_roles: str):
    """Organisation-scoped RBAC dependency enforced against verified membership."""

    def org_role_dependency(
        org_ctx: OrgContext = Depends(get_org_context),
    ) -> OrgContext:
        if org_ctx.membership.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action in this organisation.",
            )
        return org_ctx

    return org_role_dependency
