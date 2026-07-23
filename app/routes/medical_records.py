"""
Medical Records — CRUD routes
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import get_pool

router = APIRouter(prefix="/api/medical-records", tags=["Medical Records"])


class RecordCreate(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_id: int | None = None
    diagnosis: str
    prescription: str | None = None
    notes: str | None = None


@router.get("")
async def list_records(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    patient_id: int | None = None,
):
    pool = get_pool()
    if patient_id:
        rows = await pool.fetch("""
            SELECT mr.record_id, mr.diagnosis, mr.prescription, mr.notes,
                   mr.created_at, mr.appointment_id,
                   p.first_name || ' ' || p.last_name AS patient_name,
                   d.first_name || ' ' || d.last_name AS doctor_name
            FROM medical_records mr
            JOIN patients p ON p.patient_id = mr.patient_id
            JOIN doctors d ON d.doctor_id = mr.doctor_id
            WHERE mr.patient_id = $1
            ORDER BY mr.created_at DESC
            LIMIT $2 OFFSET $3
        """, patient_id, limit, offset)
    else:
        rows = await pool.fetch("""
            SELECT mr.record_id, mr.diagnosis, mr.prescription, mr.notes,
                   mr.created_at, mr.appointment_id,
                   p.first_name || ' ' || p.last_name AS patient_name,
                   d.first_name || ' ' || d.last_name AS doctor_name
            FROM medical_records mr
            JOIN patients p ON p.patient_id = mr.patient_id
            JOIN doctors d ON d.doctor_id = mr.doctor_id
            ORDER BY mr.created_at DESC
            LIMIT $1 OFFSET $2
        """, limit, offset)
    return [dict(r) for r in rows]


@router.get("/count")
async def count_records():
    pool = get_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM medical_records")
    return {"count": count}


@router.post("")
async def create_record(rec: RecordCreate):
    pool = get_pool()
    try:
        row = await pool.fetchrow("""
            INSERT INTO medical_records (patient_id, doctor_id, appointment_id,
                                          diagnosis, prescription, notes)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING record_id, diagnosis, created_at
        """, rec.patient_id, rec.doctor_id, rec.appointment_id,
            rec.diagnosis, rec.prescription, rec.notes)
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
