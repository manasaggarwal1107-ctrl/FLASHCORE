import base64
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.expansion import (
    AiActionDecisionRequest,
    AiActionProposalOut,
    VoiceQueryRequest,
    VoiceQueryResponse,
    VoiceSessionCreate,
    VoiceSessionOut,
)
from app.services import voice_service

router = APIRouter(prefix="/api/v1/voice", tags=["FLASHCORE Voice Intelligence"])


class VoiceTranscribeRequest(BaseModel):
    audio_base64: str = Field(min_length=4, max_length=14_000_000)
    filename: str = Field(default="recording.webm", max_length=120)
    language: Literal["en", "hi", "hinglish", "auto"] = "auto"


@router.get("/sessions", response_model=list[VoiceSessionOut])
def list_sessions(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return voice_service.list_sessions(db, org_ctx)


@router.post("/sessions", response_model=VoiceSessionOut, status_code=201)
def create_session(
    payload: VoiceSessionCreate | None = None,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return voice_service.create_or_get_session(db, org_ctx, payload)


@router.get("/sessions/{session_id}", response_model=VoiceSessionOut)
def get_session(
    session_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return voice_service.get_session(db, org_ctx, session_id)


@router.post("/query", response_model=VoiceQueryResponse)
def query_voice_assistant(
    payload: VoiceQueryRequest,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return voice_service.handle_query(db, org_ctx, payload)


@router.post("/transcribe")
def transcribe_audio(
    payload: VoiceTranscribeRequest,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
):
    voice_service._enforce_rate_limit(org_ctx.organisation.id, org_ctx.user.id)
    try:
        raw_b64 = payload.audio_base64.split(",", 1)[-1]
        content = base64.b64decode(raw_b64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid base64 audio payload.") from exc

    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=422, detail="Audio payload must be non-empty and under 10 MB."
        )
    stt = voice_service.GroqWhisperSTTProvider()
    try:
        return stt.transcribe(
            audio_bytes=content,
            filename=payload.filename,
            language=payload.language,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Server speech transcription unavailable; browser speech recognition fallback is active.",
        ) from exc


@router.post("/actions/{proposal_id}/decide", response_model=AiActionProposalOut)
def decide_proposal(
    proposal_id: int,
    payload: AiActionDecisionRequest,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return voice_service.decide_action_proposal(db, org_ctx, proposal_id, payload)
