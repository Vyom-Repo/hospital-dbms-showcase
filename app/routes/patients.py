"""
Patients Route Handler
Patient registration, demographics, and directory lookups.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.database import get_pool

router = APIRouter(prefix="/api/patients", tags=["Patients"])


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    blood_group: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


@router.get("")
async def list_patients(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str | None = None,
):
    pool = get_pool()
    if search:
        rows = await pool.fetch("""
            SELECT patient_id, first_name, last_name, date_of_birth,
                   gender, email, phone, blood_group, registered_at
            FROM hms.patients
            WHERE first_name ILIKE $1 OR last_name ILIKE $1 OR email ILIKE $1
            ORDER BY patient_id DESC
            LIMIT $2 OFFSET $3
        """, f"%{search}%", limit, offset)
    else:
        rows = await pool.fetch("""
            SELECT patient_id, first_name, last_name, date_of_birth,
                   gender, email, phone, blood_group, registered_at
            FROM hms.patients
            ORDER BY patient_id DESC
            LIMIT $1 OFFSET $2
        """, limit, offset)
    return [dict(r) for r in rows]


@router.get("/count")
async def count_patients():
    pool = get_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM hms.patients")
    return {"count": count}


@router.post("")
async def create_patient(patient: PatientCreate):
    pool = get_pool()
    try:
        row = await pool.fetchrow("""
            INSERT INTO hms.patients (first_name, last_name, date_of_birth, gender,
                                  email, phone, address, blood_group,
                                  emergency_contact_name, emergency_contact_phone)
            VALUES ($1, $2, $3::DATE, $4, $5, $6, $7, $8, $9, $10)
            RETURNING patient_id, first_name, last_name, registered_at
        """, patient.first_name, patient.last_name, patient.date_of_birth,
            patient.gender, patient.email, patient.phone, patient.address,
            patient.blood_group, patient.emergency_contact_name,
            patient.emergency_contact_phone)
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{patient_id}")
async def get_patient(patient_id: int):
    pool = get_pool()
    row = await pool.fetchrow("""
        SELECT * FROM hms.patients WHERE patient_id = $1
    """, patient_id)
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")
    return dict(row)
