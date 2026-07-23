"""
Billing — CRUD + Payment Processing
Demonstrates trigger-based auto-status via trg_auto_payment_status
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import get_pool

router = APIRouter(prefix="/api/billing", tags=["Billing"])


class BillCreate(BaseModel):
    patient_id: int
    appointment_id: int | None = None
    total_amount: float
    payment_method: str | None = None  # cash, card, insurance, online


class PaymentUpdate(BaseModel):
    bill_id: int
    paid_amount: float
    payment_method: str  # cash, card, insurance, online


@router.get("")
async def list_bills(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    patient_id: int | None = None,
    payment_status: str | None = None,
):
    pool = get_pool()
    conditions = []
    params = []
    idx = 1

    if patient_id:
        conditions.append(f"b.patient_id = ${idx}")
        params.append(patient_id)
        idx += 1
    if payment_status:
        conditions.append(f"b.payment_status = ${idx}")
        params.append(payment_status)
        idx += 1

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.extend([limit, offset])

    rows = await pool.fetch(f"""
        SELECT b.bill_id, b.total_amount, b.paid_amount, b.payment_status,
               b.payment_method, b.bill_date, b.paid_date,
               p.first_name || ' ' || p.last_name AS patient_name,
               b.appointment_id
        FROM billing b
        JOIN patients p ON p.patient_id = b.patient_id
        {where_clause}
        ORDER BY b.bill_date DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """, *params)
    return [dict(r) for r in rows]


@router.get("/count")
async def count_bills():
    pool = get_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM billing")
    return {"count": count}


@router.post("")
async def create_bill(bill: BillCreate):
    pool = get_pool()
    try:
        row = await pool.fetchrow("""
            INSERT INTO billing (patient_id, appointment_id, total_amount,
                                  payment_method)
            VALUES ($1, $2, $3, $4)
            RETURNING bill_id, total_amount, payment_status, bill_date
        """, bill.patient_id, bill.appointment_id,
            bill.total_amount, bill.payment_method)
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pay")
async def make_payment(payment: PaymentUpdate):
    """
    Process a payment. The trg_auto_payment_status trigger
    automatically updates payment_status based on paid_amount vs total_amount:
    - paid_amount >= total_amount → 'paid'
    - 0 < paid_amount < total_amount → 'partial'
    - paid_amount == 0 → 'pending'
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Check current bill
            bill = await conn.fetchrow("""
                SELECT bill_id, total_amount, paid_amount
                FROM billing
                WHERE bill_id = $1
                FOR UPDATE
            """, payment.bill_id)

            if not bill:
                raise HTTPException(status_code=404, detail="Bill not found")

            new_paid = float(bill["paid_amount"]) + payment.paid_amount
            if new_paid > float(bill["total_amount"]):
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment exceeds outstanding amount. "
                           f"Total: {bill['total_amount']}, "
                           f"Already paid: {bill['paid_amount']}, "
                           f"Attempted: {payment.paid_amount}"
                )

            # Update — trigger will auto-set payment_status
            row = await conn.fetchrow("""
                UPDATE billing
                SET paid_amount = $1,
                    payment_method = $2
                WHERE bill_id = $3
                RETURNING bill_id, total_amount, paid_amount,
                          payment_status, paid_date
            """, new_paid, payment.payment_method, payment.bill_id)

            return dict(row)


@router.get("/summary")
async def billing_summary():
    """Patient billing summary from v_patient_billing_summary view."""
    pool = get_pool()
    rows = await pool.fetch("""
        SELECT * FROM v_patient_billing_summary
        WHERE total_bills > 0
        ORDER BY outstanding_balance DESC
        LIMIT 100
    """)
    return [dict(r) for r in rows]
