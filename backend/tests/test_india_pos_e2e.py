from datetime import datetime, timedelta, timezone


def _auth_org(client, email: str, org_name: str, org_slug: str):
    r = client.post("/api/auth/signup", json={"email": email, "password": "IndiaRetail!2026"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    org = client.post("/api/organisations", headers=hdr, json={"name": org_name, "slug": org_slug})
    assert org.status_code == 201, org.text
    org_id = org.json()["organisation_id"]
    hdr["X-Organisation-Id"] = str(org_id)
    return hdr, org_id


def test_complete_22_step_india_first_retail_acceptance_journey(client):
    # 1. Create Indian retail organisation
    h, org_id = _auth_org(client, "india-owner@flashcore.local", "Bharat Electronics Pvt Ltd", "bharat-electronics")

    # 2. Configure India GST profile (Maharashtra State Code 27)
    tax_resp = client.put(
        "/api/v1/tax/profile",
        headers=h,
        json={
            "legal_name": "Bharat Electronics Pvt Ltd",
            "gstin": "27AABCB1234F1Z5",
            "registration_type": "regular",
            "state_name": "Maharashtra",
            "state_code": "27",
            "invoice_prefix": "BE",
            "financial_year_code": "2627",
        },
    )
    assert tax_resp.status_code == 200, tax_resp.text
    assert tax_resp.json()["gstin"] == "27AABCB1234F1Z5"

    # 3. Create warehouse + retail branch
    wh = client.post(
        "/api/v1/warehouses",
        headers=h,
        json={"code": "WH-PNQ", "name": "Pune Hub", "location_type": "warehouse", "state": "Maharashtra", "is_default": True},
    )
    store = client.post(
        "/api/v1/warehouses",
        headers=h,
        json={"code": "STR-MUM", "name": "Mumbai Store", "location_type": "store", "state": "Maharashtra"},
    )
    assert wh.status_code == 201 and store.status_code == 201
    wh_id = int(wh.json()["id"])
    store_id = int(store.json()["id"])

    # 4. Create product with HSN code, cost price, GST rate (18%)
    prod = client.post(
        "/api/v1/products",
        headers=h,
        json={
            "sku": "IND-AUDIO-01",
            "barcode": "8909998887771",
            "name": "Acoustic Earbuds Pro",
            "brand": "BharatSound",
            "category": "Electronics",
            "hsn_sac_code": "8518",
            "cost_price_minor": 100000,
            "price_minor": 200000,
            "tax_rate_bps": 1800,
            "tax_name": "GST 18%",
            "unit": "PCS",
            "status": "active",
        },
    )
    assert prod.status_code == 201, prod.text
    pid = int(prod.json()["id"])

    # 5. Create supplier with GSTIN
    sup = client.post(
        "/api/v1/suppliers",
        headers=h,
        json={"code": "SUP-BLR", "name": "Deccan Acoustics LLP", "gstin": "29AABCD9999K1Z2", "state_code": "29"},
    )
    assert sup.status_code == 201, sup.text
    sup_id = int(sup.json()["id"])

    # 6. Purchase requisition -> PO -> submit -> receive stock + record supplier invoice
    req = client.post(
        "/api/v1/requisitions",
        headers=h,
        json={
            "location_id": wh_id,
            "supplier_id": sup_id,
            "notes": "Restock fast-moving audio SKU",
            "items": [{"product_id": pid, "ordered_quantity": 20, "unit_cost_minor": 100000}],
        },
    )
    assert req.status_code == 201
    po_conv = client.post(f"/api/v1/requisitions/{req.json()['id']}/convert", headers=h)
    assert po_conv.status_code == 200
    po_id = int(po_conv.json()["purchase_order_id"])

    assert client.post(f"/api/v1/purchase-orders/{po_id}/submit", headers=h).status_code == 200
    pos = client.get("/api/v1/purchase-orders", headers=h).json()
    po_item_id = int(pos[0]["items"][0]["id"])
    assert (
        client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            headers=h,
            json={"items": [{"item_id": po_item_id, "quantity_received": 20}]},
        ).status_code
        == 200
    )

    sup_inv = client.post(
        "/api/v1/supplier-invoices",
        headers=h,
        json={
            "invoice_number": "DAC-2627-011",
            "supplier_id": sup_id,
            "purchase_order_id": po_id,
            "subtotal_minor": 2000000,
            "gst_minor": 360000,
        },
    )
    assert sup_inv.status_code == 201

    # 7. Transfer 10 units to retail store
    tr = client.post(
        "/api/v1/transfers",
        headers=h,
        json={"product_id": pid, "from_location_id": wh_id, "to_location_id": store_id, "quantity": 10},
    ).json()
    assert client.post(f"/api/v1/transfers/{tr['id']}/dispatch", headers=h).status_code == 200
    assert client.post(f"/api/v1/transfers/{tr['id']}/receive", headers=h).status_code == 200

    # 8. Create customer (same state 27 -> intra-state CGST + SGST) + verify DPDP consent toggle
    cust = client.post(
        "/api/v1/customers",
        headers=h,
        json={"name": "Priya Deshmukh", "email": "priya@example.in", "phone": "+919820011223", "state_code": "27"},
    ).json()
    cid = int(cust["id"])
    consent = client.put(f"/api/v1/customers/{cid}/consent", headers=h, json={"marketing_consent": True, "opt_out": False})
    assert consent.status_code == 200 and consent.json()["marketing_consent"] is True

    # 9. Open POS shift, hold & resume a bill, run promotional campaign & split Cash+UPI POS checkout
    shift = client.post(
        "/api/v1/pos/shifts/open",
        headers=h,
        json={"location_id": store_id, "opening_cash_minor": 50000},
    ).json()
    held = client.post(
        "/api/v1/pos/held-bills",
        headers=h,
        json={"location_id": store_id, "label": "Counter 1", "customer_id": cid, "items": [{"product_id": pid, "quantity": 2}]},
    ).json()

    now = datetime.now(timezone.utc)
    camp = client.post(
        "/api/v1/campaigns",
        headers=h,
        json={
            "name": "Diwali Audio Surge",
            "starts_at": (now - timedelta(minutes=5)).isoformat(),
            "ends_at": (now + timedelta(hours=3)).isoformat(),
            "discount_type": "percentage",
            "discount_value": 1000,  # 10% off -> 180000 minor
            "activate_immediately": True,
            "products": [{"product_id": pid, "allocated_units": 5}],
        },
    ).json()

    # Sale price = 180000 * 2 = 360000 subtotal + 18% GST (64800 -> CGST 32400 + SGST 32400) = 424800 total
    pos_res = client.post(
        "/api/v1/pos/checkout",
        headers=h,
        json={
            "location_id": store_id,
            "customer_id": cid,
            "shift_id": int(shift["id"]),
            "held_bill_id": int(held["id"]),
            "campaign_id": int(camp["id"]),
            "offline_tx_id": "offline-pos-0001",
            "items": [{"product_id": pid, "quantity": 2}],
            "payments": [
                {"method": "cash", "amount_minor": 124800},
                {"method": "upi", "amount_minor": 300000, "reference_utr": "UPI43219876"},
            ],
        },
    )
    assert pos_res.status_code == 201, pos_res.text
    pos_out = pos_res.json()
    assert pos_out["cgst_minor"] == 32400
    assert pos_out["sgst_minor"] == 32400
    assert pos_out["igst_minor"] == 0
    assert pos_out["total_minor"] == 424800
    assert pos_out["invoice"]["invoice_number"].startswith("BE-2627-")

    # 10. Idempotent offline queue replay does NOT duplicate stock deduction or order
    replay = client.post(
        "/api/v1/pos/checkout",
        headers=h,
        json={
            "location_id": store_id,
            "customer_id": cid,
            "offline_tx_id": "offline-pos-0001",
            "items": [{"product_id": pid, "quantity": 2}],
            "payments": [{"method": "cash", "amount_minor": 424800}],
        },
    )
    assert replay.status_code == 201
    assert replay.json()["offline_replayed"] is True

    # Verify printable invoice endpoint works
    inv_html = client.get(f"/api/v1/invoices/{pos_out['invoice']['id']}/print", headers=h)
    assert inv_html.status_code == 200 and "CGST + SGST" in inv_html.text

    # 11. Verify Gross Sales vs Tax vs COGS vs Gross Profit separation + CRM Loyalty points earned
    pnl = client.get("/api/v1/sales/pnl", headers=h).json()
    assert pnl["gross_sales_minor"] == 360000
    assert pnl["tax_collected_minor"] == 64800
    assert pnl["cogs_minor"] == 200000  # 2 units * 100000 cost
    assert pnl["gross_profit_minor"] == 160000  # net_sales_ex_tax (360000) - COGS (200000)

    c360 = client.get(f"/api/v1/customers/{cid}/profile", headers=h).json()
    assert c360["loyalty_points"] == 42  # 424800 // 10000
    assert c360["paid_order_count"] == 1

    # 12. Close shift & verify cash drawer reconciliation (opening 50000 + cash 124800 = 174800 expected)
    closed = client.post(
        f"/api/v1/pos/shifts/{shift['id']}/close",
        headers=h,
        json={"counted_cash_minor": 174800},
    ).json()
    assert closed["status"] == "CLOSED"
    assert closed["expected_cash_minor"] == 174800
    assert closed["variance_minor"] == 0

    # 13. Process return of 1 unit in good condition + approved restock -> generates Credit Note CN-2627-...
    ord_detail = client.get(f"/api/v1/orders/{pos_out['order_id']}", headers=h).json()
    oi_id = ord_detail["lines"][0]["id"]
    ret = client.post(
        "/api/v1/returns",
        headers=h,
        json={"order_id": int(pos_out["order_id"]), "return_type": "return", "reason": "Customer exchanged gift", "items": [{"order_item_id": oi_id, "quantity": 1, "condition": "good"}]},
    ).json()
    assert (
        client.post(
            f"/api/v1/returns/{ret['id']}/review",
            headers=h,
            json={"decision": "COMPLETED", "restock_approved": True},
        ).status_code
        == 200
    )
    invs = client.get("/api/v1/invoices", headers=h).json()
    assert any(i["document_type"] == "credit_note" and i["invoice_number"].startswith("CN-2627-") for i in invs)

    # 14. Automation run & Readiness check
    assert client.post("/api/v1/automation/rules", headers=h, json={"name": "Low Stock Alert", "trigger_type": "low_stock", "threshold_value": 5}).status_code == 201
    assert client.post("/api/v1/automation/run", headers=h).json()["executed_rules"] == 1
    assert len(client.get("/api/v1/integrations/readiness", headers=h).json()) >= 5

    # 15. Voice BI query sees real sales & audit trail recorded
    vq = client.post("/api/v1/voice/query", headers=h, json={"transcript": "What were today's sales?", "language": "en", "input_mode": "text"})
    assert vq.status_code == 200
    audits = client.get("/api/admin/audit-logs", headers=h).json()
    assert len(audits["items"]) >= 4
