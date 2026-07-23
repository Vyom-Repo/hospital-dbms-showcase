"""
Appointments Route Handler
Provides booking endpoints with SELECT FOR UPDATE concurrency protection.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import get_pool

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


class AppointmentBook(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_datetime: str
    duration_minutes: int = 30
    reason: str | None = None


class AppointmentCancel(BaseModel):
    appointment_id: int


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
        FROM hms.appointments a
        JOIN hms.patients p ON p.patient_id = a.patient_id
        JOIN hms.doctors d ON d.doctor_id = a.doctor_id
        {where_clause}
        ORDER BY a.appointment_datetime DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    rows = await pool.fetch(query, *params)
    return [dict(r) for r in rows]


@router.get("/count")
async def count_appointments():
    pool = get_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM hms.appointments")
    return {"count": count}


@router.post("/book")
async def book_appointment(appt: AppointmentBook):
    pool = get_pool()
    async with pool.acquire() as conn:
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
    Explicit transaction booking using SELECT ... FOR UPDATE to lock doctor schedule.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction(isolation="read_committed"):
            doctor = await conn.fetchrow("""
                SELECT doctor_id, availability_status
                FROM doctors
                WHERE doctor_id = $1
                FOR UPDATE
            """, appt.doctor_id)

            if not doctor:
                raise HTTPException(status_code=404, detail="Doctor not found")

            if doctor["availability_status"] != "active":
                raise HTTPException(
                    status_code=409,
                    detail=f"Doctor is currently {doctor['availability_status']}"
                )

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

            row = await conn.fetchrow("""
                INSERT INTO appointments
                    (patient_id, doctor_id, appointment_datetime,
                     duration_minutes, reason, status)
                VALUES ($1, $2, $3::TIMESTAMP, $4, $5, 'scheduled')
                RETURNING appointment_id, appointment_datetime, status
            """, appt.patient_id, appt.doctor_id, appt.appointment_datetime,
                appt.duration_minutes, appt.reason)

            return {
                **dict(row),
                "status_message": f"SUCCESS: Appointment #{row['appointment_id']} booked (raw tx)"
            }


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
