from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.campaigns import SurgeCampaignProduct
from app.models.finance import PaymentRefund
from app.models.operations import SalesRecord
from app.models.payments import PaymentOrder, PaymentProviderAccount, PaymentTransaction
from app.models.retail import InventoryBalance
from app.models.voice import AiUsageLog
from app.schemas.expansion import VoiceQueryRequest
from app.services import voice_service


def _signup_and_headers(client, email: str, org_name: str, org_slug: str, role: str = "owner"):
    resp = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "StrongPassword!123"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org_resp = client.post(
        "/api/organisations",
        headers=headers,
        json={"name": org_name, "slug": org_slug},
    )
    assert org_resp.status_code == 201, org_resp.text
    org_data = org_resp.json()
    org_id = org_data.get("organisation_id") or org_data.get("id")
    assert org_id is not None, org_data
    headers["X-Organisation-Id"] = str(org_id)
    return headers, org_id, token


def test_stage6_catalog_warehouses_transfers_damaged_and_procurement(client):
    h, org_id, _ = _signup_and_headers(client, "stage6@flashcore.local", "Stage 6 Retail", "stage6-retail")

    # 1. Extended product creation & barcode search
    p_resp = client.post(
        "/api/v1/products",
        headers=h,
        json={
            "sku": "SKU-BAR-100",
            "barcode": "8901234567890",
            "name": "Wireless Barcode Scanner",
            "brand": "FlashTech",
            "category": "Hardware",
            "cost_price_minor": 150000,
            "price_minor": 249900,
            "tax_rate_bps": 1800,
            "tax_name": "GST 18%",
            "reorder_threshold": 4,
            "status": "active",
        },
    )
    assert p_resp.status_code == 201, p_resp.text
    prod = p_resp.json()
    assert prod["barcode"] == "8901234567890"
    assert prod["brand"] == "FlashTech"
    assert prod["cost_price"] == "1500.00"

    search_resp = client.get("/api/v1/products?search=8901234567890", headers=h)
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] == 1

    # 2. Multi-warehouse setup
    wh1 = client.post(
        "/api/v1/warehouses",
        headers=h,
        json={"code": "WH-DEL", "name": "Delhi Hub", "location_type": "warehouse", "city": "Delhi", "is_default": True},
    )
    wh2 = client.post(
        "/api/v1/warehouses",
        headers=h,
        json={"code": "STR-MUM", "name": "Mumbai Flagship", "location_type": "store", "city": "Mumbai"},
    )
    assert wh1.status_code == 201 and wh2.status_code == 201
    loc1 = int(wh1.json()["id"])
    loc2 = int(wh2.json()["id"])

    # 3. Supplier & Purchase Order full + partial receipt lifecycle
    sup = client.post(
        "/api/v1/suppliers",
        headers=h,
        json={"code": "SUP-1", "name": "Acme Hardware Dist", "contact_name": "Riya", "payment_terms": "Net 30"},
    )
    assert sup.status_code == 201
    sup_id = int(sup.json()["id"])

    po_resp = client.post(
        "/api/v1/purchase-orders",
        headers=h,
        json={
            "supplier_id": sup_id,
            "location_id": loc1,
            "notes": "=SUM(A1:A2) Urgent replenishment",
            "items": [{"product_id": int(prod["id"]), "ordered_quantity": 20, "unit_cost_minor": 140000}],
        },
    )
    assert po_resp.status_code == 201
    po = po_resp.json()
    assert po["status"] == "DRAFT"
    po_item_id = int(po["items"][0]["id"])

    sub_resp = client.post(f"/api/v1/purchase-orders/{po['id']}/submit", headers=h)
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    rec1 = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receive",
        headers=h,
        json={"items": [{"item_id": po_item_id, "quantity_received": 8}], "note": "Lot 1"},
    )
    assert rec1.status_code == 200
    assert rec1.json()["status"] == "PARTIALLY_RECEIVED"

    rec_over = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receive",
        headers=h,
        json={"items": [{"item_id": po_item_id, "quantity_received": 15}]},
    )
    assert rec_over.status_code == 409

    rec2 = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receive",
        headers=h,
        json={"items": [{"item_id": po_item_id, "quantity_received": 12}], "note": "Lot 2"},
    )
    assert rec2.status_code == 200
    assert rec2.json()["status"] == "COMPLETED"

    # 4. Multi-location stock transfer + damaged stock tracking
    tr_resp = client.post(
        "/api/v1/transfers",
        headers=h,
        json={
            "product_id": int(prod["id"]),
            "from_location_id": loc1,
            "to_location_id": loc2,
            "quantity": 6,
            "requires_approval": True,
        },
    )
    assert tr_resp.status_code == 201
    tr_id = tr_resp.json()["id"]
    assert tr_resp.json()["status"] == "PENDING_APPROVAL"

    # Cannot dispatch before approval
    assert client.post(f"/api/v1/transfers/{tr_id}/dispatch", headers=h).status_code == 409
    assert client.post(f"/api/v1/transfers/{tr_id}/approve", headers=h).status_code == 200
    assert client.post(f"/api/v1/transfers/{tr_id}/dispatch", headers=h).status_code == 200
    recv_tr = client.post(f"/api/v1/transfers/{tr_id}/receive", headers=h)
    assert recv_tr.status_code == 200
    assert recv_tr.json()["status"] == "RECEIVED"

    # Damaged stock quarantine reduces sellable quantity
    dmg = client.post(
        "/api/v1/retail-inventory/damaged",
        headers=h,
        json={"product_id": int(prod["id"]), "location_id": loc1, "quantity_delta": 2, "reason": "Box crushed"},
    )
    assert dmg.status_code == 200
    assert dmg.json()["on_hand"] == 12  # 20 - 6 transferred - 2 damaged
    assert dmg.json()["damaged"] == 2

    # Negative stock prevention via transfer > available
    bad_tr = client.post(
        "/api/v1/transfers",
        headers=h,
        json={"product_id": int(prod["id"]), "from_location_id": loc1, "to_location_id": loc2, "quantity": 50},
    )
    assert bad_tr.status_code == 201
    assert client.post(f"/api/v1/transfers/{bad_tr.json()['id']}/dispatch", headers=h).status_code == 409

    # 5. Inventory intelligence & valuation
    intel = client.get("/api/v1/retail-inventory/intelligence", headers=h)
    assert intel.status_code == 200
    assert intel.json()["insufficient_data"] is True
    assert intel.json()["total_stock_value_minor"] == 18 * 150000


def test_stage7_8_campaigns_coupons_concurrency_sales_returns_and_csv(client, db_session):
    h, org_id, _ = _signup_and_headers(client, "stage7@flashcore.local", "Stage 7 Retail", "stage7-retail")

    # Setup product + location + stock + customer
    wh = client.post("/api/v1/warehouses", headers=h, json={"code": "WH1", "name": "Central", "is_default": True})
    loc_id = int(wh.json()["id"])
    prod = client.post(
        "/api/v1/products",
        headers=h,
        json={"sku": "FLASH-01", "name": "Limited Sneaker", "category": "Footwear", "price_minor": 500000, "tax_rate_bps": 1200, "status": "active"},
    ).json()
    pid = int(prod["id"])
    client.post("/api/v1/inventory/adjustments", headers=h, json={"product_id": pid, "location_id": loc_id, "quantity_delta": 50, "reason": "Initial stock"})
    cust = client.post("/api/v1/customers", headers=h, json={"name": "Aarav Sharma", "email": "aarav@example.com"}).json()
    cid = int(cust["id"])

    # Create coupon + validate
    promo = client.post(
        "/api/v1/promotions",
        headers=h,
        json={"code": "SAVE500", "name": "Flat 500 Off", "discount_type": "fixed", "discount_value": 50000, "min_order_minor": 100000},
    )
    assert promo.status_code == 201
    val = client.post("/api/v1/promotions/validate", headers=h, json={"code": "SAVE500", "subtotal_minor": 400000, "customer_id": cid})
    assert val.status_code == 200
    assert val.json()["valid"] is True and val.json()["discount_minor"] == 50000

    # Create active Surge Campaign (20% off, allocated 3 units)
    now = datetime.now(timezone.utc)
    camp = client.post(
        "/api/v1/campaigns",
        headers=h,
        json={
            "name": "Midnight Surge",
            "starts_at": (now - timedelta(minutes=5)).isoformat(),
            "ends_at": (now + timedelta(hours=2)).isoformat(),
            "discount_type": "percentage",
            "discount_value": 2000,
            "activate_immediately": True,
            "products": [{"product_id": pid, "allocated_units": 3}],
        },
    )
    assert camp.status_code == 201, camp.text
    camp_id = int(camp.json()["id"])
    assert camp.json()["products"][0]["sale_price_minor"] == 400000

    # Concurrent surge purchases: 6 threads try to buy 1 unit each against 3 allocated units
    def attempt_buy(idx: int):
        return client.post(
            "/api/v1/orders",
            headers=h,
            json={
                "customer_id": cid,
                "campaign_id": camp_id,
                "coupon_code": "SAVE500" if idx == 0 else None,
                "items": [{"product_id": pid, "location_id": loc_id, "quantity": 1}],
            },
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt_buy, range(6)))

    successes = [r for r in results if r.status_code == 201]
    rejections = [r for r in results if r.status_code == 409]
    assert len(successes) == 3
    assert len(rejections) == 3

    cp_row = db_session.scalar(select(SurgeCampaignProduct).where(SurgeCampaignProduct.campaign_id == camp_id))
    assert cp_row.sold_units == 3

    # Simulate captured payment on first order -> SalesRecord auto-created + return + non-auto-restock check
    o_data = successes[0].json()
    oid = int(o_data["id"])
    oi_id = o_data["lines"][0]["id"]

    # Insert verified captured payment rows as checkout verification does
    acct = PaymentProviderAccount(
        organisation_id=org_id,
        provider="razorpay",
        mode="test",
        key_id="rzp_test_stage8",
        encrypted_key_secret="dummy",
        encrypted_webhook_secret="dummy_wh",
        key_version="v1",
    )
    db_session.add(acct)
    db_session.flush()
    po = PaymentOrder(
        organisation_id=org_id,
        order_id=oid,
        provider_account_id=acct.id,
        provider="razorpay",
        provider_order_id="order_stage8_1",
        receipt="rcpt_stage8_1",
        amount_minor=o_data["total_minor"],
        currency="INR",
        status="CAPTURED",
    )
    db_session.add(po)
    db_session.flush()
    tx = PaymentTransaction(
        organisation_id=org_id,
        order_id=oid,
        payment_order_id=po.id,
        provider="razorpay",
        provider_payment_id="pay_stage8_1",
        event_type="CAPTURED",
        amount_minor=o_data["total_minor"],
        currency="INR",
        status="CAPTURED",
        source="checkout_verify",
    )
    db_session.add(tx)
    from app.models.retail import Order as OrderModel
    from app.services import inventory_service, sales_service

    ord_row = db_session.get(OrderModel, oid)
    inventory_service.confirm_order_reservations(db_session, organisation_id=org_id, order_id=oid, actor_ref="stage7@flashcore.local")
    ord_row.order_status = "PAID"
    ord_row.payment_status = "CAPTURED"
    sales_service.sync_sales_record_for_order(db_session, ord_row, transaction_ref="pay_stage8_1")
    db_session.commit()

    # Check sales records & dashboard
    sr = client.get("/api/v1/sales/records", headers=h)
    assert sr.status_code == 200 and sr.json()["total"] == 1
    dash = client.get("/api/v1/sales/dashboard", headers=h)
    assert dash.status_code == 200
    assert dash.json()["order_count"] == 1
    assert dash.json()["total_revenue_minor"] == o_data["total_minor"]

    # Return request with damaged condition -> must NOT restore sellable inventory
    bal_before = db_session.scalar(select(InventoryBalance).where(InventoryBalance.product_id == pid, InventoryBalance.location_id == loc_id))
    qty_before = bal_before.quantity

    ret = client.post(
        "/api/v1/returns",
        headers=h,
        json={
            "order_id": oid,
            "return_type": "return",
            "reason": "=CMD|Damaged sole",
            "items": [{"order_item_id": oi_id, "quantity": 1, "condition": "damaged"}],
        },
    )
    assert ret.status_code == 201
    ret_id = ret.json()["id"]

    # Review without restock_approved on damaged item -> sellable quantity unchanged, damaged_quantity incremented
    rev = client.post(
        f"/api/v1/returns/{ret_id}/review",
        headers=h,
        json={"decision": "COMPLETED", "restock_approved": False},
    )
    assert rev.status_code == 200
    db_session.expire_all()
    bal_after = db_session.scalar(select(InventoryBalance).where(InventoryBalance.product_id == pid, InventoryBalance.location_id == loc_id))
    assert bal_after.quantity == qty_before
    assert bal_after.damaged_quantity == 1

    # CSV export formula-injection protection
    csv_resp = client.get("/api/v1/reports/sales/export.csv", headers=h)
    assert csv_resp.status_code == 200
    assert "Order Number" in csv_resp.text

    # In-app notifications sync
    notifs = client.get("/api/v1/notifications", headers=h)
    assert notifs.status_code == 200
    assert "items" in notifs.json()


def test_stage5_voice_intelligence_bi_approval_and_tenant_isolation(client, db_session):
    h_org1, org1_id, _ = _signup_and_headers(client, "voice1@flashcore.local", "Voice Org 1", "voice-org-1")
    h_org2, org2_id, _ = _signup_and_headers(client, "voice2@flashcore.local", "Voice Org 2", "voice-org-2")

    p1 = client.post(
        "/api/v1/products",
        headers=h_org1,
        json={"sku": "VOICE-SKU", "name": "Smart Speaker", "price_minor": 299900, "status": "active"},
    ).json()
    pid1 = int(p1["id"])

    # 1. Read-only Hindi/Hinglish BI query via deterministic router + TTS hint check
    q_resp = client.post(
        "/api/v1/voice/query",
        headers=h_org1,
        json={"transcript": "Aaj ki sales aur low stock batao", "language": "hinglish", "input_mode": "voice"},
    )
    assert q_resp.status_code == 200, q_resp.text
    q_data = q_resp.json()
    assert q_data["tts_hint"]["language"] == "hinglish"
    assert q_data["tts_hint"]["voice_lang"] == "hi-IN"
    assert q_data["tts_hint"]["supports_hindi"] is True
    assert len(q_data["tool_executions"]) >= 1

    # 2. Controlled Mutation Proposal via Groq tool-call mock -> MUST NOT auto-execute
    class FakeLLM:
        def __init__(self):
            self.turn = 0

        def complete(self, *, messages, tools):
            self.turn += 1
            if self.turn == 1:
                return voice_service.LLMCompletionResult(
                    content="",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "name": "propose_adjust_inventory",
                            "arguments": {"product_id": pid1, "quantity_delta": 15, "reason": "Voice confirmed count"},
                        }
                    ],
                    model="llama-3.3-70b-versatile",
                    prompt_tokens=100,
                    completion_tokens=40,
                )
            return voice_service.LLMCompletionResult(
                content="I prepared a proposal to add 15 units. Please approve it explicitly.",
                model="llama-3.3-70b-versatile",
                prompt_tokens=120,
                completion_tokens=30,
            )

    from app.core.auth_dependencies import OrgContext
    from app.models.auth import User
    from app.models.organisation import Organisation, OrganisationMembership

    user1 = db_session.scalar(select(User).where(User.email == "voice1@flashcore.local"))
    org1 = db_session.get(Organisation, org1_id)
    mem1 = db_session.scalar(
        select(OrganisationMembership).where(
            OrganisationMembership.user_id == user1.id,
            OrganisationMembership.organisation_id == org1_id,
        )
    )
    res = voice_service.handle_query(
        db_session,
        OrgContext(user=user1, organisation=org1, membership=mem1),
        VoiceQueryRequest(transcript="Add 15 units to Smart Speaker", language="en", input_mode="text"),
        llm_provider=FakeLLM(),
    )
    assert res.pending_proposal is not None
    assert res.pending_proposal.status == "PENDING_APPROVAL"
    prop_id = res.pending_proposal.id

    # Stock is STILL 0 until explicitly confirmed
    prod_before = client.get(f"/api/v1/products/{pid1}", headers=h_org1).json()
    assert prod_before["inventory"]["on_hand"] == 0

    # Tenant isolation: Org 2 cannot approve or view Org 1's proposal/session
    assert (
        client.post(
            f"/api/v1/voice/actions/{prop_id}/decide",
            headers=h_org2,
            json={"approve": True},
        ).status_code
        == 404
    )

    # Approve from Org 1 -> executes cleanly and increments stock to 15
    exec_resp = client.post(
        f"/api/v1/voice/actions/{prop_id}/decide",
        headers=h_org1,
        json={"approve": True, "note": "Verified shelf"},
    )
    assert exec_resp.status_code == 200, exec_resp.text
    assert exec_resp.json()["status"] == "EXECUTED"
    prod_after = client.get(f"/api/v1/products/{pid1}", headers=h_org1).json()
    assert prod_after["inventory"]["on_hand"] == 15

    # Usage log recorded
    logs = db_session.scalars(select(AiUsageLog).where(AiUsageLog.organisation_id == org1_id)).all()
    assert len(logs) >= 2
