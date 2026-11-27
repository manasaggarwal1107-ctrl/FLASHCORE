from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import json
import os
import time
from typing import Any, Protocol

from fastapi import HTTPException
import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.campaigns import SurgeCampaign
from app.models.finance import PaymentApprovalRequest, PaymentRefund
from app.models.operations import SalesRecord
from app.models.procurement import Supplier
from app.models.retail import (
    CommerceProduct,
    Customer,
    InventoryBalance,
    InventoryLocation,
    Order,
    OrderItem,
)
from app.models.rossmann import AuditLog
from app.models.voice import AiActionProposal, AiUsageLog, VoiceMessage, VoiceSession
from app.schemas.expansion import (
    AiActionDecisionRequest,
    AiActionProposalOut,
    CampaignProductIn,
    PromotionCreate,
    PurchaseOrderCreate,
    PurchaseOrderItemIn,
    SurgeCampaignCreate,
    VoiceMessageOut,
    VoiceQueryRequest,
    VoiceQueryResponse,
    VoiceSessionCreate,
    VoiceSessionOut,
)
from app.schemas.retail import (
    CommerceProductCreate,
    InventoryAdjustmentCreate,
    format_minor_to_decimal_str,
)
from app.services import (
    campaign_service,
    catalog_service,
    inventory_service,
    procurement_service,
)

DEFAULT_GROQ_CHAT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GROQ_STT_MODEL = "whisper-large-v3-turbo"
MAX_REQUESTS_PER_MINUTE = 25

# Sliding window per (org_id, user_id)
_AI_RATE_WINDOW: dict[tuple[int, int], deque[float]] = defaultdict(deque)


def _enforce_rate_limit(org_id: int, user_id: int) -> None:
    now = time.monotonic()
    bucket = _AI_RATE_WINDOW[(org_id, user_id)]
    while bucket and now - bucket[0] > 60.0:
        bucket.popleft()
    if len(bucket) >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="AI assistant rate limit reached. Please wait a minute before sending more queries.",
        )
    bucket.append(now)


class LLMCompletionResult:
    def __init__(
        self,
        *,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        provider: str = "groq",
        model: str = DEFAULT_GROQ_CHAT_MODEL,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls or []
        self.provider = provider
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class LLMProvider(Protocol):
    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMCompletionResult: ...


class STTProvider(Protocol):
    def transcribe(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        language: str | None = None,
    ) -> dict[str, Any]: ...


class GroqLLMProvider:
    """Server-side Groq Chat Completions client via OpenAI-compatible REST API."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = (api_key or os.getenv("GROQ_API_KEY") or "").strip()
        self._model = model or os.getenv("GROQ_CHAT_MODEL", DEFAULT_GROQ_CHAT_MODEL)

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMCompletionResult:
        if not self._api_key:
            raise RuntimeError("GROQ_API_KEY is not configured on the server.")

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 700,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice.get("message", {})
        usage = data.get("usage", {})
        raw_calls = msg.get("tool_calls") or []
        parsed_calls: list[dict[str, Any]] = []
        for tc in raw_calls:
            fn = tc.get("function", {})
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
            except Exception:
                args = {}
            parsed_calls.append(
                {
                    "id": tc.get("id") or f"call_{len(parsed_calls)}",
                    "name": fn.get("name"),
                    "arguments": args,
                }
            )
        return LLMCompletionResult(
            content=msg.get("content") or "",
            tool_calls=parsed_calls,
            provider="groq",
            model=data.get("model") or self._model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )


class GroqWhisperSTTProvider:
    """Server-side Groq Whisper speech-to-text provider with multilingual support."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = (api_key or os.getenv("GROQ_API_KEY") or "").strip()
        self._model = model or os.getenv("GROQ_STT_MODEL", DEFAULT_GROQ_STT_MODEL)

    def transcribe(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        language: str | None = None,
    ) -> dict[str, Any]:
        if not self._api_key:
            raise RuntimeError("GROQ_API_KEY is not configured for server STT.")
        form_data: dict[str, Any] = {"model": self._model, "response_format": "verbose_json"}
        if language in ("en", "hi"):
            form_data["language"] = language
        elif language == "hinglish":
            form_data["prompt"] = "Hinglish retail conversation mixing Hindi and English."

        with httpx.Client(timeout=25.0) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                data=form_data,
                files={"file": (filename or "speech.webm", audio_bytes, "audio/webm")},
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "text": (data.get("text") or "").strip(),
            "language": data.get("language") or language or "auto",
            "provider": "groq-whisper",
            "model": self._model,
        }


def build_tts_hint(language: str, text_reply: str) -> dict[str, Any]:
    """Explicit multilingual TTS provider descriptor.

    Groq's English TTS is not assumed to support Hindi; browser SpeechSynthesis
    is provided as the multilingual fallback while keeping cloud TTS pluggable.
    """
    norm = (language or "en").lower()
    if norm == "hi":
        bcp47 = "hi-IN"
    elif norm == "hinglish":
        bcp47 = "hi-IN"
    else:
        bcp47 = "en-IN"
    return {
        "provider": "browser-speech-synthesis",
        "language": norm,
        "voice_lang": bcp47,
        "supports_hindi": True,
        "text_length": len(text_reply),
    }


READ_ONLY_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_sales_overview",
            "description": "Get today's sales, yesterday's revenue, total revenue, order count, and refund summary.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_selling_products",
            "description": "List best-selling products by revenue and units sold.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_alerts",
            "description": "List low-stock and out-of-stock products along with current inventory counts.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_orders",
            "description": "List orders currently in DRAFT, PENDING_PAYMENT, or PROCESSING status.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_customers",
            "description": "List customers with highest lifetime paid spend and order count.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_performance",
            "description": "Inspect flash sale / surge campaign performance and optional specific campaign revenue.",
            "parameters": {
                "type": "object",
                "properties": {"campaign_name": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_refund_status",
            "description": "Summarize refunds by status and pending approval requests.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    # Controlled mutation proposals (NEVER executed until user explicitly confirms via /actions/{id}/decide)
    {
        "type": "function",
        "function": {
            "name": "propose_adjust_inventory",
            "description": "Propose an inventory stock adjustment requiring explicit user confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "quantity_delta": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["product_id", "quantity_delta", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_product",
            "description": "Propose adding a new retail product requiring explicit user confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string"},
                    "name": {"type": "string"},
                    "price_minor": {"type": "integer"},
                    "category": {"type": "string"},
                },
                "required": ["sku", "name", "price_minor"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_discount_campaign",
            "description": "Propose creating a coupon/discount promotion requiring explicit confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "name": {"type": "string"},
                    "discount_type": {"type": "string", "enum": ["percentage", "fixed"]},
                    "discount_value": {"type": "integer"},
                },
                "required": ["code", "name", "discount_type", "discount_value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_flash_sale",
            "description": "Propose creating a flash sale surge campaign requiring explicit confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "product_id": {"type": "integer"},
                    "allocated_units": {"type": "integer"},
                    "discount_bps": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                },
                "required": ["name", "product_id", "allocated_units"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_purchase_order",
            "description": "Propose creating a draft purchase order requiring explicit confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "integer"},
                    "location_id": {"type": "integer"},
                    "product_id": {"type": "integer"},
                    "ordered_quantity": {"type": "integer"},
                    "unit_cost_minor": {"type": "integer"},
                },
                "required": ["supplier_id", "product_id", "ordered_quantity", "unit_cost_minor"],
            },
        },
    },
]

MUTATION_TOOLS = {
    "propose_adjust_inventory",
    "propose_create_product",
    "propose_create_discount_campaign",
    "propose_create_flash_sale",
    "propose_create_purchase_order",
}


def _run_read_only_tool(
    db: Session, org_id: int, tool_name: str, args: dict[str, Any]
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_yesterday = start_today - timedelta(days=1)

    if tool_name == "get_sales_overview":
        today_rev = int(
            db.scalar(
                select(func.coalesce(func.sum(SalesRecord.net_amount_minor - SalesRecord.refunded_minor), 0)).where(
                    SalesRecord.organisation_id == org_id,
                    SalesRecord.sold_at >= start_today,
                )
            )
            or 0
        )
        yesterday_rev = int(
            db.scalar(
                select(func.coalesce(func.sum(SalesRecord.net_amount_minor - SalesRecord.refunded_minor), 0)).where(
                    SalesRecord.organisation_id == org_id,
                    SalesRecord.sold_at >= start_yesterday,
                    SalesRecord.sold_at < start_today,
                )
            )
            or 0
        )
        total_rev = int(
            db.scalar(
                select(func.coalesce(func.sum(SalesRecord.net_amount_minor - SalesRecord.refunded_minor), 0)).where(
                    SalesRecord.organisation_id == org_id
                )
            )
            or 0
        )
        cnt = int(
            db.scalar(
                select(func.count(SalesRecord.id)).where(
                    SalesRecord.organisation_id == org_id,
                    SalesRecord.refund_status != "FULL",
                )
            )
            or 0
        )
        return {
            "today_sales": format_minor_to_decimal_str(today_rev),
            "yesterday_revenue": format_minor_to_decimal_str(yesterday_rev),
            "total_net_revenue": format_minor_to_decimal_str(total_rev),
            "paid_orders_count": cnt,
            "currency": "INR",
        }

    if tool_name == "get_top_selling_products":
        limit = min(max(int(args.get("limit") or 5), 1), 20)
        rows = db.execute(
            select(
                OrderItem.product_id,
                OrderItem.sku_snapshot,
                OrderItem.name_snapshot,
                func.coalesce(func.sum(OrderItem.quantity), 0).label("units"),
                func.coalesce(func.sum(OrderItem.line_total_minor), 0).label("rev_minor"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                OrderItem.organisation_id == org_id,
                Order.order_status.in_(("PAID", "PROCESSING", "FULFILLED")),
            )
            .group_by(OrderItem.product_id, OrderItem.sku_snapshot, OrderItem.name_snapshot)
            .order_by(func.sum(OrderItem.line_total_minor).desc())
            .limit(limit)
        ).all()
        return {
            "top_products": [
                {
                    "product_id": r.product_id,
                    "sku": r.sku_snapshot,
                    "name": r.name_snapshot,
                    "units_sold": int(r.units or 0),
                    "revenue": format_minor_to_decimal_str(int(r.rev_minor or 0)),
                }
                for r in rows
            ]
        }

    if tool_name == "get_inventory_alerts":
        rows = db.execute(
            select(
                CommerceProduct.id,
                CommerceProduct.sku,
                CommerceProduct.name,
                func.coalesce(func.sum(InventoryBalance.quantity), 0).label("on_hand"),
                func.coalesce(func.sum(InventoryBalance.reserved_quantity), 0).label("reserved"),
                func.min(InventoryBalance.low_stock_threshold).label("threshold"),
            )
            .outerjoin(InventoryBalance, InventoryBalance.product_id == CommerceProduct.id)
            .where(CommerceProduct.organisation_id == org_id)
            .group_by(CommerceProduct.id, CommerceProduct.sku, CommerceProduct.name, CommerceProduct.reorder_threshold)
        ).all()
        low = []
        items = []
        for r in rows:
            on_hand = int(r.on_hand or 0)
            reserved = int(r.reserved or 0)
            avail = max(0, on_hand - reserved)
            thresh = int(r.threshold) if r.threshold is not None else 5
            entry = {
                "product_id": r.id,
                "sku": r.sku,
                "name": r.name,
                "on_hand": on_hand,
                "available": avail,
                "threshold": thresh,
            }
            items.append(entry)
            if avail <= thresh:
                low.append(entry)
        return {"low_stock_items": low, "inventory_items": items[:15]}

    if tool_name == "get_pending_orders":
        rows = db.scalars(
            select(Order)
            .where(
                Order.organisation_id == org_id,
                Order.order_status.in_(("DRAFT", "PENDING_PAYMENT", "PROCESSING")),
            )
            .order_by(Order.id.desc())
            .limit(15)
        ).all()
        return {
            "pending_orders": [
                {
                    "order_id": o.id,
                    "order_number": o.order_number,
                    "status": o.order_status,
                    "payment_status": o.payment_status,
                    "total": format_minor_to_decimal_str(o.total_minor),
                }
                for o in rows
            ]
        }

    if tool_name == "get_top_customers":
        rows = db.execute(
            select(
                Customer.id,
                Customer.name,
                func.count(SalesRecord.id).label("orders"),
                func.coalesce(func.sum(SalesRecord.net_amount_minor - SalesRecord.refunded_minor), 0).label("spend"),
            )
            .join(SalesRecord, SalesRecord.customer_id == Customer.id)
            .where(Customer.organisation_id == org_id)
            .group_by(Customer.id, Customer.name)
            .order_by(func.sum(SalesRecord.net_amount_minor - SalesRecord.refunded_minor).desc())
            .limit(10)
        ).all()
        return {
            "top_customers": [
                {
                    "customer_id": r.id,
                    "name": r.name,
                    "orders": int(r.orders or 0),
                    "spend": format_minor_to_decimal_str(int(r.spend or 0)),
                }
                for r in rows
            ]
        }

    if tool_name == "get_campaign_performance":
        name_filter = (args.get("campaign_name") or "").strip().lower()
        rows = db.execute(
            select(
                SurgeCampaign.id,
                SurgeCampaign.name,
                SurgeCampaign.status,
                SurgeCampaign.total_units_sold,
                func.coalesce(func.sum(SalesRecord.net_amount_minor), 0).label("rev_minor"),
            )
            .outerjoin(SalesRecord, SalesRecord.campaign_id == SurgeCampaign.id)
            .where(SurgeCampaign.organisation_id == org_id)
            .group_by(SurgeCampaign.id, SurgeCampaign.name, SurgeCampaign.status, SurgeCampaign.total_units_sold)
            .order_by(func.coalesce(func.sum(SalesRecord.net_amount_minor), 0).desc())
        ).all()
        if name_filter:
            rows = [r for r in rows if name_filter in r.name.lower()]
        return {
            "campaigns": [
                {
                    "campaign_id": r.id,
                    "name": r.name,
                    "status": r.status,
                    "units_sold": r.total_units_sold,
                    "revenue": format_minor_to_decimal_str(int(r.rev_minor or 0)),
                }
                for r in rows[:10]
            ]
        }

    if tool_name == "get_refund_status":
        rows = db.execute(
            select(
                PaymentRefund.status,
                func.count(PaymentRefund.id).label("cnt"),
                func.coalesce(func.sum(PaymentRefund.amount_minor), 0).label("amt"),
            )
            .where(PaymentRefund.organisation_id == org_id)
            .group_by(PaymentRefund.status)
        ).all()
        pending_approvals = int(
            db.scalar(
                select(func.count(PaymentApprovalRequest.id)).where(
                    PaymentApprovalRequest.organisation_id == org_id,
                    PaymentApprovalRequest.status == "PENDING",
                )
            )
            or 0
        )
        return {
            "by_status": [
                {
                    "status": r.status,
                    "count": int(r.cnt or 0),
                    "amount": format_minor_to_decimal_str(int(r.amt or 0)),
                }
                for r in rows
            ],
            "pending_approvals": pending_approvals,
        }

    return {"error": f"Unknown read-only tool: {tool_name}"}


def _deterministic_bi_fallback(
    db: Session, org_id: int, text_query: str, language: str
) -> tuple[str, list[dict[str, Any]]]:
    """Safe read-only intent router when Groq API is unavailable or fails."""
    q = text_query.lower()
    tool_execs: list[dict[str, Any]] = []

    if any(k in q for k in ("low", "stock", "inventory", "kam", "maal")):
        res = _run_read_only_tool(db, org_id, "get_inventory_alerts", {})
        tool_execs.append({"tool": "get_inventory_alerts", "result": res})
        low = res["low_stock_items"]
        if language == "hi":
            reply = (
                f"वर्तमान में {len(low)} उत्पाद कम स्टॉक स्तर पर हैं।"
                if low
                else "सभी उपलब्ध उत्पादों का स्टॉक सुरक्षित सीमा के भीतर है।"
            )
        elif language == "hinglish":
            reply = (
                f"Abhi {len(low)} products low stock par hain: "
                + ", ".join(f"{x['name']} ({x['available']} left)" for x in low[:5])
                if low
                else "Abhi sabhi tracked products sufficient stock mein hain."
            )
        else:
            reply = (
                f"{len(low)} product(s) are currently low on stock: "
                + ", ".join(f"{x['name']} ({x['available']} left)" for x in low[:5])
                if low
                else "All tracked products currently have stock above their reorder thresholds."
            )
        return reply, tool_execs

    if any(k in q for k in ("refund", "wapas")):
        res = _run_read_only_tool(db, org_id, "get_refund_status", {})
        tool_execs.append({"tool": "get_refund_status", "result": res})
        reply = (
            f"Refund summary: {len(res['by_status'])} status bucket(s), "
            f"{res['pending_approvals']} approval(s) pending."
        )
        return reply, tool_execs

    if any(k in q for k in ("campaign", "flash", "sale", "offer")):
        res = _run_read_only_tool(db, org_id, "get_campaign_performance", {})
        tool_execs.append({"tool": "get_campaign_performance", "result": res})
        camps = res["campaigns"]
        reply = (
            f"Found {len(camps)} campaign(s); top campaign: {camps[0]['name']} (INR {camps[0]['revenue']})."
            if camps
            else "No surge campaigns have been created in this workspace yet."
        )
        return reply, tool_execs

    if any(k in q for k in ("pending", "order")):
        res = _run_read_only_tool(db, org_id, "get_pending_orders", {})
        tool_execs.append({"tool": "get_pending_orders", "result": res})
        orders = res["pending_orders"]
        reply = f"There are {len(orders)} pending or processing order(s)."
        return reply, tool_execs

    if any(k in q for k in ("customer", "buyer", "grahak")):
        res = _run_read_only_tool(db, org_id, "get_top_customers", {})
        tool_execs.append({"tool": "get_top_customers", "result": res})
        custs = res["top_customers"]
        reply = (
            f"Top customer: {custs[0]['name']} with INR {custs[0]['spend']} across {custs[0]['orders']} paid order(s)."
            if custs
            else "No paid customer sales records exist yet."
        )
        return reply, tool_execs

    res = _run_read_only_tool(db, org_id, "get_sales_overview", {})
    tool_execs.append({"tool": "get_sales_overview", "result": res})
    if language == "hi":
        reply = (
            f"आज की कुल बिक्री INR {res['today_sales']} रही, कल की आय INR {res['yesterday_revenue']} थी, "
            f"और कुल शुद्ध राजस्व INR {res['total_net_revenue']} ({res['paid_orders_count']} ऑर्डर) है।"
        )
    elif language == "hinglish":
        reply = (
            f"Aaj ki sales INR {res['today_sales']} hai, kal ki revenue INR {res['yesterday_revenue']} thi, "
            f"aur total net revenue INR {res['total_net_revenue']} ({res['paid_orders_count']} orders) hai."
        )
    else:
        reply = (
            f"Today's sales total INR {res['today_sales']}, yesterday's revenue was INR {res['yesterday_revenue']}, "
            f"and total net revenue is INR {res['total_net_revenue']} across {res['paid_orders_count']} paid order(s)."
        )
    return reply, tool_execs


def _proposal_to_out(p: AiActionProposal) -> AiActionProposalOut:
    return AiActionProposalOut(
        id=str(p.id),
        tool_name=p.tool_name,
        arguments=p.arguments_json,
        summary=p.summary,
        status=p.status,
        approved_by=p.approved_by,
        result=p.result_json,
        error_message=p.error_message,
        created_at=p.created_at,
    )


def create_or_get_session(
    db: Session, org_ctx: OrgContext, payload: VoiceSessionCreate | None = None
) -> VoiceSessionOut:
    lang = payload.language_mode if payload else "auto"
    title = (payload.title.strip() if payload and payload.title else "FLASHCORE Voice Session")
    sess = VoiceSession(
        organisation_id=org_ctx.organisation.id,
        user_id=org_ctx.user.id,
        language_mode=lang,
        title=title,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return get_session(db, org_ctx, sess.id)


def list_sessions(db: Session, org_ctx: OrgContext) -> list[VoiceSessionOut]:
    rows = db.scalars(
        select(VoiceSession)
        .where(
            VoiceSession.organisation_id == org_ctx.organisation.id,
            VoiceSession.user_id == org_ctx.user.id,
        )
        .order_by(VoiceSession.id.desc())
        .limit(20)
    ).all()
    return [get_session(db, org_ctx, r.id) for r in rows]


def get_session(db: Session, org_ctx: OrgContext, session_id: int) -> VoiceSessionOut:
    sess = db.scalar(
        select(VoiceSession).where(
            VoiceSession.id == session_id,
            VoiceSession.organisation_id == org_ctx.organisation.id,
        )
    )
    if sess is None:
        raise HTTPException(status_code=404, detail="Voice session not found.")
    msgs = db.scalars(
        select(VoiceMessage)
        .where(VoiceMessage.session_id == sess.id)
        .order_by(VoiceMessage.id.asc())
    ).all()
    props = db.scalars(
        select(AiActionProposal)
        .where(AiActionProposal.session_id == sess.id)
        .order_by(AiActionProposal.id.desc())
    ).all()
    return VoiceSessionOut(
        id=str(sess.id),
        language_mode=sess.language_mode,
        title=sess.title,
        messages=[
            VoiceMessageOut(
                id=str(m.id),
                role=m.role,
                content=m.content,
                transcript_language=m.transcript_language,
                tool_calls=m.tool_calls,
                created_at=m.created_at,
            )
            for m in msgs
        ],
        proposals=[_proposal_to_out(p) for p in props],
        created_at=sess.created_at,
    )


def handle_query(
    db: Session,
    org_ctx: OrgContext,
    payload: VoiceQueryRequest,
    *,
    llm_provider: LLMProvider | None = None,
) -> VoiceQueryResponse:
    org_id = org_ctx.organisation.id
    _enforce_rate_limit(org_id, org_ctx.user.id)

    if payload.session_id is not None:
        sess = db.scalar(
            select(VoiceSession).where(
                VoiceSession.id == payload.session_id,
                VoiceSession.organisation_id == org_id,
            )
        )
        if sess is None:
            raise HTTPException(status_code=404, detail="Voice session not found.")
    else:
        sess = VoiceSession(
            organisation_id=org_id,
            user_id=org_ctx.user.id,
            language_mode=payload.language,
            title=payload.transcript.strip()[:60] or "FLASHCORE Voice Session",
        )
        db.add(sess)
        db.flush()

    db.add(
        VoiceMessage(
            organisation_id=org_id,
            session_id=sess.id,
            role="user",
            content=payload.transcript.strip(),
            transcript_language=payload.language,
            stt_provider="web-speech" if payload.input_mode == "voice" else "text",
        )
    )
    db.flush()

    history_rows = list(
        db.scalars(
            select(VoiceMessage)
            .where(VoiceMessage.session_id == sess.id)
            .order_by(VoiceMessage.id.asc())
        ).all()
    )[-12:]

    system_prompt = (
        "You are FLASHCORE Voice Intelligence ('Talk to your business. Understand it. Control it.'), "
        "a friendly, precise retail operations & commerce assistant. "
        f"Current organisation: {org_ctx.organisation.name}. User role: {org_ctx.membership.role}. "
        f"Preferred language mode: {payload.language}. Reply in English, Hindi (Devanagari), or Hinglish matching the user. "
        "Always inspect live data via read-only tools rather than guessing numbers. "
        "For any change/creation request (stock, product, campaign, coupon, PO), call the corresponding propose_* tool "
        "and explain clearly that explicit user approval is required before execution."
    )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for h in history_rows:
        if h.role in ("user", "assistant"):
            messages.append({"role": h.role, "content": h.content})

    provider = llm_provider or GroqLLMProvider()
    t0 = time.monotonic()
    tool_executions: list[dict[str, Any]] = []
    pending_proposal: AiActionProposal | None = None
    used_provider = "groq"
    used_model = DEFAULT_GROQ_CHAT_MODEL
    reply_text = ""

    try:
        first = provider.complete(messages=messages, tools=READ_ONLY_TOOLS)
        used_provider = first.provider
        used_model = first.model
        p_tokens = first.prompt_tokens
        c_tokens = first.completion_tokens

        if first.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": first.content or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"]),
                            },
                        }
                        for tc in first.tool_calls
                    ],
                }
            )
            for tc in first.tool_calls:
                tname = tc["name"]
                targs = tc.get("arguments") or {}
                if tname in MUTATION_TOOLS:
                    summary = f"{tname} with {json.dumps(targs)}"
                    prop = AiActionProposal(
                        organisation_id=org_id,
                        session_id=sess.id,
                        user_id=org_ctx.user.id,
                        tool_name=tname,
                        arguments_json=targs,
                        summary=summary,
                        status="PENDING_APPROVAL",
                    )
                    db.add(prop)
                    db.flush()
                    pending_proposal = prop
                    tool_result = {
                        "proposal_id": prop.id,
                        "status": "PENDING_APPROVAL",
                        "message": "Action requires explicit user confirmation before execution.",
                    }
                else:
                    tool_result = _run_read_only_tool(db, org_id, tname, targs)
                tool_executions.append({"tool": tname, "arguments": targs, "result": tool_result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(tool_result),
                    }
                )
            second = provider.complete(messages=messages, tools=[])
            reply_text = second.content.strip() or "Completed inspection."
            p_tokens = (p_tokens or 0) + (second.prompt_tokens or 0)
            c_tokens = (c_tokens or 0) + (second.completion_tokens or 0)
        else:
            reply_text = first.content.strip()

        latency_ms = int((time.monotonic() - t0) * 1000)
        db.add(
            AiUsageLog(
                organisation_id=org_id,
                user_id=org_ctx.user.id,
                provider=used_provider,
                model=used_model,
                operation="chat_completion",
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                latency_ms=latency_ms,
                status="success",
            )
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        used_provider = "local-bi-fallback"
        used_model = "deterministic-router"
        reply_text, tool_executions = _deterministic_bi_fallback(
            db, org_id, payload.transcript, payload.language
        )
        db.add(
            AiUsageLog(
                organisation_id=org_id,
                user_id=org_ctx.user.id,
                provider="groq",
                model=DEFAULT_GROQ_CHAT_MODEL,
                operation="chat_completion",
                latency_ms=latency_ms,
                status="error",
                error_detail=type(exc).__name__,
            )
        )

    tts_hint = build_tts_hint(payload.language, reply_text)
    db.add(
        VoiceMessage(
            organisation_id=org_id,
            session_id=sess.id,
            role="assistant",
            content=reply_text,
            transcript_language=payload.language,
            tts_provider=tts_hint["provider"],
            tool_calls=tool_executions or None,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
    )
    sess.updated_at = datetime.now(timezone.utc)
    db.commit()
    if pending_proposal is not None:
        db.refresh(pending_proposal)

    return VoiceQueryResponse(
        session_id=str(sess.id),
        reply=reply_text,
        language=payload.language,
        provider=used_provider,
        model=used_model,
        tool_executions=tool_executions,
        pending_proposal=_proposal_to_out(pending_proposal) if pending_proposal else None,
        tts_hint=tts_hint,
    )


def decide_action_proposal(
    db: Session,
    org_ctx: OrgContext,
    proposal_id: int,
    payload: AiActionDecisionRequest,
) -> AiActionProposalOut:
    org_id = org_ctx.organisation.id
    if org_ctx.membership.role not in ("owner", "admin", "operator"):
        raise HTTPException(
            status_code=403,
            detail="Your role cannot approve or execute AI operational mutations.",
        )

    prop = db.scalar(
        select(AiActionProposal)
        .where(
            AiActionProposal.id == proposal_id,
            AiActionProposal.organisation_id == org_id,
        )
        .with_for_update()
    )
    if prop is None:
        raise HTTPException(status_code=404, detail="Action proposal not found.")
    if prop.status != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=409, detail=f"Proposal already processed (status: {prop.status})."
        )

    now = datetime.now(timezone.utc)
    if not payload.approve:
        prop.status = "REJECTED"
        prop.approved_by = org_ctx.user.email
        prop.approved_at = now
        db.add(
            AuditLog(
                organisation_id=org_id,
                actor_type=org_ctx.membership.role,
                actor_ref=org_ctx.user.email,
                action="ai_action_rejected",
                entity_name="ai_action_proposals",
                entity_id=str(prop.id),
                details={"tool_name": prop.tool_name, "note": payload.note},
            )
        )
        db.commit()
        db.refresh(prop)
        return _proposal_to_out(prop)

    args = prop.arguments_json or {}
    try:
        result: dict[str, Any]
        if prop.tool_name == "propose_adjust_inventory":
            out = inventory_service.adjust_stock(
                db,
                org_ctx,
                InventoryAdjustmentCreate(
                    product_id=int(args["product_id"]),
                    quantity_delta=int(args["quantity_delta"]),
                    reason=str(args.get("reason") or "Voice Assistant approved adjustment"),
                ),
            )
            result = {"balance_id": out.id, "on_hand": out.on_hand, "available": out.available}
        elif prop.tool_name == "propose_create_product":
            out = catalog_service.create_product(
                db,
                org_ctx,
                CommerceProductCreate(
                    sku=str(args["sku"]),
                    name=str(args["name"]),
                    price_minor=int(args["price_minor"]),
                    category=args.get("category"),
                    status="active",
                ),
            )
            result = {"product_id": out.id, "sku": out.sku, "name": out.name}
        elif prop.tool_name == "propose_create_discount_campaign":
            out = campaign_service.create_promotion(
                db,
                org_ctx,
                PromotionCreate(
                    code=str(args["code"]),
                    name=str(args["name"]),
                    discount_type=args["discount_type"],
                    discount_value=int(args["discount_value"]),
                ),
            )
            result = {"promotion_id": out.id, "code": out.code}
        elif prop.tool_name == "propose_create_flash_sale":
            hours = max(1, int(args.get("duration_hours") or 24))
            out = campaign_service.create_campaign(
                db,
                org_ctx,
                SurgeCampaignCreate(
                    name=str(args["name"]),
                    starts_at=now,
                    ends_at=now + timedelta(hours=hours),
                    discount_type="percentage",
                    discount_value=int(args.get("discount_bps") or 1000),
                    activate_immediately=True,
                    products=[
                        CampaignProductIn(
                            product_id=int(args["product_id"]),
                            allocated_units=int(args["allocated_units"]),
                        )
                    ],
                ),
            )
            result = {"campaign_id": out.id, "name": out.name, "status": out.status}
        elif prop.tool_name == "propose_create_purchase_order":
            loc = inventory_service.get_or_create_default_location(db, org_id)
            loc_id = int(args.get("location_id") or loc.id)
            out = procurement_service.create_purchase_order(
                db,
                org_ctx,
                PurchaseOrderCreate(
                    supplier_id=int(args["supplier_id"]),
                    location_id=loc_id,
                    items=[
                        PurchaseOrderItemIn(
                            product_id=int(args["product_id"]),
                            ordered_quantity=int(args["ordered_quantity"]),
                            unit_cost_minor=int(args["unit_cost_minor"]),
                        )
                    ],
                ),
            )
            result = {"purchase_order_id": out.id, "po_number": out.po_number}
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported AI tool: {prop.tool_name}")

        prop = db.get(AiActionProposal, proposal_id) or prop
        prop.status = "EXECUTED"
        prop.approved_by = org_ctx.user.email
        prop.approved_at = now
        prop.executed_at = datetime.now(timezone.utc)
        prop.result_json = result
    except Exception as exc:
        prop = db.get(AiActionProposal, proposal_id) or prop
        prop.status = "FAILED"
        prop.approved_by = org_ctx.user.email
        prop.approved_at = now
        prop.error_message = str(getattr(exc, "detail", exc))
        db.commit()
        raise

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="ai_action_executed",
            entity_name="ai_action_proposals",
            entity_id=str(prop.id),
            details={"tool_name": prop.tool_name, "result": prop.result_json},
        )
    )
    db.commit()
    db.refresh(prop)
    return _proposal_to_out(prop)
