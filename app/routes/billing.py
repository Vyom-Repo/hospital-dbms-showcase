"""
Billing Route Handler
Manages patient invoices and trigger-enforced payment classification.
"""

from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.database import get_pool

router = APIRouter(prefix="/api/billing", tags=["Billing"])


def serialize_row(row):
    if row is None:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, Decimal):
            d[k] = float(v)
    return d


class BillCreate(BaseModel):
    patient_id: int
    appointment_id: int | None = None
    total_amount: float
    payment_method: str | None = None


class PaymentUpdate(BaseModel):
    bill_id: int
    paid_amount: float
    payment_method: str


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
        FROM hms.billing b
        JOIN hms.patients p ON p.patient_id = b.patient_id
        {where_clause}
        ORDER BY b.bill_date DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """, *params)
    return [serialize_row(r) for r in rows]


@router.get("/count")
async def count_bills():
    pool = get_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM hms.billing")
    return {"count": count}


@router.post("")
async def create_bill(bill: BillCreate):
    pool = get_pool()
    try:
        row = await pool.fetchrow("""
            INSERT INTO hms.billing (patient_id, appointment_id, total_amount,
                                  payment_method)
            VALUES ($1, $2, $3, $4)
            RETURNING bill_id, total_amount, payment_status, bill_date
        """, bill.patient_id, bill.appointment_id,
            bill.total_amount, bill.payment_method)
        return serialize_row(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pay")
async def make_payment(payment: PaymentUpdate):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            bill = await conn.fetchrow("""
                SELECT bill_id, total_amount, paid_amount
                FROM hms.billing
                WHERE bill_id = $1
                FOR UPDATE
            """, payment.bill_id)

            if not bill:
                raise HTTPException(status_code=404, detail="Bill not found")

            new_paid = float(bill["paid_amount"]) + payment.paid_amount
            if new_paid > float(bill["total_amount"]):
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment exceeds outstanding amount. Total: {bill['total_amount']}, Already paid: {bill['paid_amount']}, Attempted: {payment.paid_amount}"
                )

            row = await conn.fetchrow("""
                UPDATE hms.billing
                SET paid_amount = $1,
                    payment_method = $2
                WHERE bill_id = $3
                RETURNING bill_id, total_amount, paid_amount,
                          payment_status, paid_date
            """, new_paid, payment.payment_method, payment.bill_id)

            return serialize_row(row)


@router.get("/summary")
async def billing_summary():
    pool = get_pool()
    rows = await pool.fetch("""
        SELECT * FROM hms.v_patient_billing_summary
        WHERE total_bills > 0
        ORDER BY outstanding_balance DESC
        LIMIT 100
    """)
    return [serialize_row(r) for r in rows]
