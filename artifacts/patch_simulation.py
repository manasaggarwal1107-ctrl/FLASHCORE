with open('backend/app/routes/simulation.py', 'r', encoding='utf-8') as f:
    text_data = f.read()

target = '''    attempt_status = "rejected" if failure else "success"

    attempt = fetch_one(
        db,
        """
        INSERT INTO purchase_attempts
            (simulation_run_id, flash_sale_product_id, customer_ref,
             idempotency_key, quantity, status, failure_reason)
        VALUES
            (:run_id, :product_id, :customer, :key, :quantity,
             :status, :reason)
        RETURNING *
        """,
        {
            "run_id": sale["simulation_run_id"],
            "product_id": sale_product_id,
            "customer": payload.customer_ref,
            "key": payload.idempotency_key,
            "quantity": payload.quantity,
            "status": attempt_status,
            "reason": failure,
        },
    )'''

replacement = '''    attempt_status = "rejected" if failure else "success"

    try:
        attempt = fetch_one(
            db,
            """
            INSERT INTO purchase_attempts
                (simulation_run_id, flash_sale_product_id, customer_ref,
                 idempotency_key, quantity, status, failure_reason)
            VALUES
                (:run_id, :product_id, :customer, :key, :quantity,
                 :status, :reason)
            RETURNING *
            """,
            {
                "run_id": sale["simulation_run_id"],
                "product_id": sale_product_id,
                "customer": payload.customer_ref,
                "key": payload.idempotency_key,
                "quantity": payload.quantity,
                "status": attempt_status,
                "reason": failure,
            },
        )
    except IntegrityError as exc:
        db.rollback()
        existing = fetch_one(
            db,
            "SELECT * FROM purchase_attempts WHERE idempotency_key=:key",
            {"key": payload.idempotency_key},
        )
        if existing:
            if (
                existing["customer_ref"] == payload.customer_ref
                and existing["flash_sale_product_id"] == sale_product_id
                and existing["quantity"] == payload.quantity
            ):
                return {"duplicate": True, "attempt": dict(existing)}
            raise HTTPException(
                409, "Idempotency key was used by another request"
            ) from exc
        raise HTTPException(
            409, "Purchase conflicts with a database constraint"
        ) from exc'''

norm_text = text_data.replace('\r\n', '\n')
norm_target = target.replace('\r\n', '\n')
norm_replacement = replacement.replace('\r\n', '\n')

if norm_target not in norm_text:
    print("ERROR: Target block not found")
    sys.exit(1)

updated = norm_text.replace(norm_target, norm_replacement, 1)

with open('backend/app/routes/simulation.py', 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(updated)
print("Successfully applied idempotency race-condition patch!")
