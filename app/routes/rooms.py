"""
Rooms — CRUD + Concurrency-Safe Allocation

Demonstrates SELECT ... FOR UPDATE on room rows to prevent
two staff members from allocating the last bed simultaneously.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import get_pool

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


class RoomCreate(BaseModel):
    room_number: str
    department_id: int
    room_type: str  # general, semi_private, private, icu
    total_beds: int
    daily_rate: float


class AdmitPatient(BaseModel):
    patient_id: int
    room_id: int
    doctor_id: int
    diagnosis: str
    notes: str | None = None


class DischargePatient(BaseModel):
    patient_id: int
    room_id: int


@router.get("")
async def list_rooms(
    department_id: int | None = None,
    room_type: str | None = None,
    available_only: bool = False,
):
    pool = get_pool()
    conditions = []
    params = []
    idx = 1

    if department_id:
        conditions.append(f"r.department_id = ${idx}")
        params.append(department_id)
        idx += 1
    if room_type:
        conditions.append(f"r.room_type = ${idx}")
        params.append(room_type)
        idx += 1
    if available_only:
        conditions.append("r.occupied_beds < r.total_beds")

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = await pool.fetch(f"""
        SELECT r.room_id, r.room_number, r.room_type,
               r.total_beds, r.occupied_beds,
               (r.total_beds - r.occupied_beds) AS available_beds,
               r.daily_rate, dep.name AS department_name
        FROM rooms r
        JOIN departments dep ON dep.department_id = r.department_id
        {where_clause}
        ORDER BY r.room_number
    """, *params)
    return [dict(r) for r in rows]


@router.post("")
async def create_room(room: RoomCreate):
    pool = get_pool()
    try:
        row = await pool.fetchrow("""
            INSERT INTO rooms (room_number, department_id, room_type,
                               total_beds, daily_rate)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING room_id, room_number, room_type, total_beds
        """, room.room_number, room.department_id, room.room_type,
            room.total_beds, room.daily_rate)
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIT PATIENT — Calls fn_admit_patient stored function
# Atomic: room allocation + appointment + medical record + billing
# Uses FOR UPDATE lock on room row inside the function
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/admit")
async def admit_patient(req: AdmitPatient):
    """
    Atomic patient admission via stored function fn_admit_patient.

    The function internally:
    1. SELECT room FOR UPDATE → locks room row
    2. Increments occupied_beds
    3. Creates appointment, medical record, and billing
    4. Logs audit event
    All in a single transaction.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction(isolation="read_committed"):
            row = await conn.fetchrow("""
                SELECT * FROM fn_admit_patient($1, $2, $3, $4, $5)
            """, req.patient_id, req.room_id, req.doctor_id,
                req.diagnosis, req.notes)

            result = dict(row)
            if result["appointment_id"] == -1:
                raise HTTPException(status_code=409, detail=result["status_message"])
            return result


# ─────────────────────────────────────────────────────────────────────────────
# DISCHARGE PATIENT
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/discharge")
async def discharge_patient(req: DischargePatient):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                SELECT * FROM fn_discharge_patient($1, $2)
            """, req.patient_id, req.room_id)

            result = dict(row)
            if "ERROR" in result["status_message"]:
                raise HTTPException(status_code=409, detail=result["status_message"])
            return result


# ─────────────────────────────────────────────────────────────────────────────
# Room occupancy view
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/occupancy")
async def room_occupancy():
    pool = get_pool()
    rows = await pool.fetch("SELECT * FROM v_room_occupancy_dashboard")
    return [dict(r) for r in rows]
