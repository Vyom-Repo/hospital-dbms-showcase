"""
Appointments — Concurrency Showcase

Demonstrates:
- SELECT ... FOR UPDATE row-level locking to prevent double-booking
- Explicit transaction blocks with READ COMMITTED isolation
- Calling stored function fn_book_appointment for atomic booking
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import get_pool

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


class AppointmentBook(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_datetime: str   # ISO format: 2025-03-15T10:00:00
    duration_minutes: int = 30
    reason: str | None = None


class AppointmentCancel(BaseModel):
    appointment_id: int


# ─────────────────────────────────────────────────────────────────────────────
# LIST appointments with filters
# ─────────────────────────────────────────────────────────────────────────────
@router.get("")
async def list_appointments(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    doctor_id: int | None = None,
    patient_id: int | None = None,
    status: str | None = None,
):
    pool = get_pool()
    conditions = []
    params = []
    idx = 1

    if doctor_id:
        conditions.append(f"a.doctor_id = ${idx}")
        params.append(doctor_id)
        idx += 1
    if patient_id:
        conditions.append(f"a.patient_id = ${idx}")
        params.append(patient_id)
        idx += 1
    if status:
        conditions.append(f"a.status = ${idx}")
        params.append(status)
        idx += 1

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    params.extend([limit, offset])
    query = f"""
        SELECT a.appointment_id, a.appointment_datetime, a.duration_minutes,
               a.status, a.reason, a.created_at,
               p.first_name || ' ' || p.last_name AS patient_name,
               d.first_name || ' ' || d.last_name AS doctor_name,
               d.specialization
        FROM appointments a
        JOIN patients p ON p.patient_id = a.patient_id
        JOIN doctors d ON d.doctor_id = a.doctor_id
        {where_clause}
        ORDER BY a.appointment_datetime DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    rows = await pool.fetch(query, *params)
    return [dict(r) for r in rows]


@router.get("/count")
async def count_appointments():
    pool = get_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM appointments")
    return {"count": count}


# ─────────────────────────────────────────────────────────────────────────────
# BOOK appointment — CONCURRENCY SHOWCASE
#
# This endpoint demonstrates TWO concurrency-safe approaches:
# 1. Application-level: explicit FOR UPDATE lock in a transaction
# 2. Database-level: calling fn_book_appointment stored function
#
# We use the stored function approach in production, but show
# the raw transaction approach in the /book/raw endpoint for learning.
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/book")
async def book_appointment(appt: AppointmentBook):
    """
    Book via stored function fn_book_appointment.
    The function internally uses SELECT ... FOR UPDATE on the doctor row
    to prevent race conditions.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # The stored function handles all locking internally
        async with conn.transaction():
            row = await conn.fetchrow("""
                SELECT * FROM fn_book_appointment($1, $2, $3::TIMESTAMP, $4, $5)
            """, appt.patient_id, appt.doctor_id, appt.appointment_datetime,
                appt.duration_minutes, appt.reason)

            result = dict(row)
            if result["appointment_id"] == -1:
                raise HTTPException(status_code=409, detail=result["status_message"])
            return result


@router.post("/book/raw")
async def book_appointment_raw(appt: AppointmentBook):
    """
    Book via explicit application-level transaction with FOR UPDATE locking.
    This endpoint exists to showcase the raw concurrency mechanism.

    Transaction flow:
    1. BEGIN (implicit via conn.transaction())
    2. SELECT ... FOR UPDATE on doctor row → locks the row
    3. Check for time-slot conflicts
    4. INSERT appointment
    5. COMMIT → releases the lock

    If two receptionists try to book the same doctor/time simultaneously:
    - Request A acquires the lock at step 2
    - Request B WAITS at step 2 until A commits
    - Request B then sees A's inserted appointment at step 3
    - Request B returns conflict error
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # ─── Explicit transaction with READ COMMITTED isolation ──────────
        async with conn.transaction(isolation="read_committed"):

            # STEP 1: Lock the doctor row — prevents concurrent bookings
            doctor = await conn.fetchrow("""
                SELECT doctor_id, availability_status
                FROM doctors
                WHERE doctor_id = $1
                FOR UPDATE
            """, appt.doctor_id)
            # ^^^ Any concurrent transaction hitting this same row will BLOCK here

            if not doctor:
                raise HTTPException(status_code=404, detail="Doctor not found")

            if doctor["availability_status"] != "active":
                raise HTTPException(
                    status_code=409,
                    detail=f"Doctor is currently {doctor['availability_status']}"
                )

            # STEP 2: Check for overlapping appointments
            conflict = await conn.fetchval("""
                SELECT COUNT(*)
                FROM appointments
                WHERE doctor_id = $1
                  AND status = 'scheduled'
                  AND appointment_datetime < $2::TIMESTAMP + ($3 || ' minutes')::INTERVAL
                  AND appointment_datetime + (duration_minutes || ' minutes')::INTERVAL > $2::TIMESTAMP
            """, appt.doctor_id, appt.appointment_datetime, str(appt.duration_minutes))

            if conflict > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Time slot conflicts with an existing appointment"
                )

            # STEP 3: Insert the appointment
            row = await conn.fetchrow("""
                INSERT INTO appointments
                    (patient_id, doctor_id, appointment_datetime,
                     duration_minutes, reason, status)
                VALUES ($1, $2, $3::TIMESTAMP, $4, $5, 'scheduled')
                RETURNING appointment_id, appointment_datetime, status
            """, appt.patient_id, appt.doctor_id, appt.appointment_datetime,
                appt.duration_minutes, appt.reason)

            # STEP 4: COMMIT happens automatically when exiting the block
            return {
                **dict(row),
                "status_message": f"SUCCESS: Appointment #{row['appointment_id']} booked (raw tx)"
            }


# ─────────────────────────────────────────────────────────────────────────────
# CANCEL appointment
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/cancel")
async def cancel_appointment(cancel: AppointmentCancel):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                UPDATE appointments
                SET status = 'cancelled'
                WHERE appointment_id = $1 AND status = 'scheduled'
                RETURNING appointment_id, status
            """, cancel.appointment_id)

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail="Appointment not found or already cancelled/completed"
                )
            return dict(row)
