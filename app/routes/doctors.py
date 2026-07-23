"""
Doctors — CRUD routes
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import get_pool

router = APIRouter(prefix="/api/doctors", tags=["Doctors"])


class DoctorCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    specialization: str
    department_id: int
    hire_date: str  # YYYY-MM-DD


@router.get("")
async def list_doctors(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    department_id: int | None = None,
):
    pool = get_pool()
    if department_id:
        rows = await pool.fetch("""
            SELECT d.doctor_id, d.first_name, d.last_name, d.email, d.phone,
                   d.specialization, d.availability_status, d.hire_date,
                   dep.name AS department_name
            FROM doctors d
            JOIN departments dep ON dep.department_id = d.department_id
            WHERE d.department_id = $1
            ORDER BY d.last_name, d.first_name
            LIMIT $2 OFFSET $3
        """, department_id, limit, offset)
    else:
        rows = await pool.fetch("""
            SELECT d.doctor_id, d.first_name, d.last_name, d.email, d.phone,
                   d.specialization, d.availability_status, d.hire_date,
                   dep.name AS department_name
            FROM doctors d
            JOIN departments dep ON dep.department_id = d.department_id
            ORDER BY d.last_name, d.first_name
            LIMIT $1 OFFSET $2
        """, limit, offset)
    return [dict(r) for r in rows]


@router.get("/count")
async def count_doctors():
    pool = get_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM doctors")
    return {"count": count}


@router.post("")
async def create_doctor(doc: DoctorCreate):
    pool = get_pool()
    try:
        row = await pool.fetchrow("""
            INSERT INTO doctors (first_name, last_name, email, phone,
                                 specialization, department_id, hire_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7::DATE)
            RETURNING doctor_id, first_name, last_name, specialization
        """, doc.first_name, doc.last_name, doc.email, doc.phone,
            doc.specialization, doc.department_id, doc.hire_date)
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{doctor_id}")
async def get_doctor(doctor_id: int):
    pool = get_pool()
    row = await pool.fetchrow("""
        SELECT d.*, dep.name AS department_name
        FROM doctors d
        JOIN departments dep ON dep.department_id = d.department_id
        WHERE d.doctor_id = $1
    """, doctor_id)
    if not row:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return dict(row)
