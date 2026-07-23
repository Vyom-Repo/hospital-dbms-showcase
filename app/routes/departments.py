"""
Departments Route Handler
Management of clinical departments and facility wings.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_pool

router = APIRouter(prefix="/api/departments", tags=["Departments"])


class DepartmentCreate(BaseModel):
    name: str
    building: str
    floor_number: int
    phone_extension: str | None = None


@router.get("")
async def list_departments():
    pool = get_pool()
    rows = await pool.fetch("""
        SELECT department_id, name, building, floor_number,
               phone_extension, created_at
        FROM hms.departments
        ORDER BY name
    """)
    return [dict(r) for r in rows]


@router.post("")
async def create_department(dept: DepartmentCreate):
    pool = get_pool()
    try:
        row = await pool.fetchrow("""
            INSERT INTO departments (name, building, floor_number, phone_extension)
            VALUES ($1, $2, $3, $4)
            RETURNING department_id, name, building, floor_number
        """, dept.name, dept.building, dept.floor_number, dept.phone_extension)
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{department_id}")
async def get_department(department_id: int):
    pool = get_pool()
    row = await pool.fetchrow("""
        SELECT department_id, name, building, floor_number,
               phone_extension, created_at
        FROM hms.departments WHERE department_id = $1
    """, department_id)
    if not row:
        raise HTTPException(status_code=404, detail="Department not found")
    return dict(row)
