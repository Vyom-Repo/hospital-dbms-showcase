"""
Admin & Performance Analytics
Exposes system metrics, view aggregations, and execution plan benchmarks.
"""

from decimal import Decimal
from fastapi import APIRouter, HTTPException
from app.database import get_pool

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def serialize_row(row):
    """Convert asyncpg Record or dict containing Decimal objects to JSON-serializable types."""
    if row is None:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, Decimal):
            d[k] = float(v)
    return d


@router.get("/views/revenue")
async def monthly_revenue(
    year: int | None = None,
    month: int | None = None,
):
    pool = get_pool()
    if year and month:
        rows = await pool.fetch("""
            SELECT * FROM hms.v_monthly_revenue_by_department
            WHERE month = $1
            ORDER BY total_billed DESC
        """, f"{year}-{month:02d}")
    else:
        rows = await pool.fetch("""
            SELECT * FROM hms.v_monthly_revenue_by_department
            ORDER BY month DESC, total_billed DESC
            LIMIT 200
        """)
    return [serialize_row(r) for r in rows]


@router.get("/views/doctor-load")
async def doctor_load():
    pool = get_pool()
    rows = await pool.fetch("SELECT * FROM hms.v_doctor_appointment_load LIMIT 200")
    return [serialize_row(r) for r in rows]


@router.get("/views/room-occupancy")
async def room_occupancy():
    pool = get_pool()
    rows = await pool.fetch("SELECT * FROM hms.v_room_occupancy_dashboard")
    return [serialize_row(r) for r in rows]


@router.get("/views/billing-summary")
async def billing_summary():
    pool = get_pool()
    rows = await pool.fetch("""
        SELECT * FROM hms.v_patient_billing_summary
        WHERE total_bills > 0
        ORDER BY outstanding_balance DESC
        LIMIT 100
    """)
    return [serialize_row(r) for r in rows]


@router.get("/views/department-stats")
async def department_stats():
    pool = get_pool()
    rows = await pool.fetch("SELECT * FROM hms.mv_department_statistics")
    return [serialize_row(r) for r in rows]


@router.post("/views/refresh-materialized")
async def refresh_materialized():
    pool = get_pool()
    await pool.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY hms.mv_department_statistics")
    return {"status": "Materialized view refreshed successfully"}


PERFORMANCE_QUERIES = {
    "appointment_conflict_check": {
        "title": "Appointment Conflict Detection",
        "description": "Check for overlapping appointments for a specific doctor using idx_appointments_doctor_datetime index.",
        "sql": """
            SELECT a.appointment_id, a.appointment_datetime, a.duration_minutes
            FROM hms.appointments a
            WHERE a.doctor_id = 1
              AND a.status = 'scheduled'
              AND a.appointment_datetime BETWEEN '2025-06-01' AND '2025-06-30'
            ORDER BY a.appointment_datetime
        """,
    },
    "patient_history_lookup": {
        "title": "Patient Medical History",
        "description": "Retrieve complete medical history using idx_medrec_patient_created index.",
        "sql": """
            SELECT mr.record_id, mr.diagnosis, mr.prescription, mr.created_at,
                   d.first_name || ' ' || d.last_name AS doctor_name
            FROM hms.medical_records mr
            JOIN hms.doctors d ON d.doctor_id = mr.doctor_id
            WHERE mr.patient_id = 500
            ORDER BY mr.created_at DESC
            LIMIT 20
        """,
    },
    "monthly_revenue_aggregation": {
        "title": "Monthly Revenue Aggregation",
        "description": "Aggregate billing data by department using idx_billing_date index.",
        "sql": """
            SELECT dep.name AS department,
                   COUNT(b.bill_id) AS bills,
                   SUM(b.total_amount) AS total_billed,
                   SUM(b.paid_amount) AS total_collected
            FROM hms.billing b
            JOIN hms.appointments a ON a.appointment_id = b.appointment_id
            JOIN hms.doctors d ON d.doctor_id = a.doctor_id
            JOIN hms.departments dep ON dep.department_id = d.department_id
            WHERE b.bill_date BETWEEN '2025-01-01' AND '2025-01-31'
            GROUP BY dep.name
            ORDER BY total_billed DESC
        """,
    },
    "doctor_schedule_range": {
        "title": "Doctor Weekly Schedule",
        "description": "Fetch doctor schedule using idx_appointments_doctor_datetime index.",
        "sql": """
            SELECT a.appointment_id, a.appointment_datetime,
                   a.duration_minutes, a.status,
                   p.first_name || ' ' || p.last_name AS patient_name
            FROM hms.appointments a
            JOIN hms.patients p ON p.patient_id = a.patient_id
            WHERE a.doctor_id = 10
              AND a.appointment_datetime >= NOW()
              AND a.appointment_datetime < NOW() + INTERVAL '7 days'
            ORDER BY a.appointment_datetime
        """,
    },
    "room_availability_search": {
        "title": "Available Rooms by Department",
        "description": "Find available beds using idx_rooms_available partial index.",
        "sql": """
            SELECT r.room_id, r.room_number, r.room_type,
                   r.total_beds, r.occupied_beds,
                   (r.total_beds - r.occupied_beds) AS available_beds,
                   r.daily_rate
            FROM hms.rooms r
            WHERE r.department_id = 3
              AND r.occupied_beds < r.total_beds
            ORDER BY r.daily_rate ASC
        """,
    },
    "outstanding_payments": {
        "title": "Outstanding Patient Payments",
        "description": "Find patients with outstanding balances using idx_billing_patient_status index.",
        "sql": """
            SELECT p.patient_id,
                   p.first_name || ' ' || p.last_name AS patient_name,
                   SUM(b.total_amount - b.paid_amount) AS outstanding
            FROM hms.billing b
            JOIN hms.patients p ON p.patient_id = b.patient_id
            WHERE b.payment_status IN ('pending', 'partial')
            GROUP BY p.patient_id, p.first_name, p.last_name
            HAVING SUM(b.total_amount - b.paid_amount) > 100
            ORDER BY outstanding DESC
            LIMIT 50
        """,
    },
}


@router.get("/explain")
async def list_performance_queries():
    return {
        key: {"title": q["title"], "description": q["description"]}
        for key, q in PERFORMANCE_QUERIES.items()
    }


@router.get("/explain/{query_key}")
async def run_explain_analyze(query_key: str):
    if query_key not in PERFORMANCE_QUERIES:
        raise HTTPException(
            status_code=404,
            detail=f"Query not found. Available: {list(PERFORMANCE_QUERIES.keys())}"
        )

    pq = PERFORMANCE_QUERIES[query_key]
    pool = get_pool()

    rows = await pool.fetch(f"EXPLAIN ANALYZE {pq['sql']}")
    plan_lines = [row["QUERY PLAN"] for row in rows]
    result_rows = await pool.fetch(pq["sql"])

    return {
        "query_key": query_key,
        "title": pq["title"],
        "description": pq["description"],
        "sql": pq["sql"].strip(),
        "explain_analyze": plan_lines,
        "result_count": len(result_rows),
        "sample_results": [serialize_row(r) for r in result_rows[:5]],
    }


@router.get("/stats/tables")
async def table_stats():
    pool = get_pool()
    rows = await pool.fetch("""
        SELECT
            relname AS table_name,
            n_live_tup AS estimated_rows,
            pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
            pg_size_pretty(pg_relation_size(c.oid)) AS data_size,
            pg_size_pretty(pg_indexes_size(c.oid)) AS index_size
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'hms'
          AND c.relkind = 'r'
        ORDER BY pg_total_relation_size(c.oid) DESC
    """)
    return [serialize_row(r) for r in rows]


@router.get("/stats/indexes")
async def index_stats():
    pool = get_pool()
    rows = await pool.fetch("""
        SELECT
            schemaname,
            relname AS table_name,
            indexrelname AS index_name,
            idx_scan AS times_used,
            idx_tup_read AS tuples_read,
            idx_tup_fetch AS tuples_fetched,
            pg_size_pretty(pg_relation_size(i.indexrelid)) AS index_size
        FROM pg_stat_user_indexes i
        WHERE schemaname = 'hms'
        ORDER BY idx_scan DESC
    """)
    return [serialize_row(r) for r in rows]


@router.get("/dashboard")
async def dashboard_stats():
    pool = get_pool()
    async with pool.acquire() as conn:
        patients = await conn.fetchval("SELECT COUNT(*) FROM hms.patients")
        doctors = await conn.fetchval("SELECT COUNT(*) FROM hms.doctors")
        appointments_today = await conn.fetchval("""
            SELECT COUNT(*) FROM hms.appointments
            WHERE appointment_datetime::DATE = CURRENT_DATE
              AND status = 'scheduled'
        """)
        total_appointments = await conn.fetchval("SELECT COUNT(*) FROM hms.appointments")
        pending_bills = await conn.fetchval("""
            SELECT COUNT(*) FROM hms.billing WHERE payment_status = 'pending'
        """)
        total_revenue = await conn.fetchval("""
            SELECT COALESCE(SUM(paid_amount), 0) FROM hms.billing
        """)
        occupancy = await conn.fetchrow("""
            SELECT COALESCE(SUM(occupied_beds), 0) AS occupied,
                   COALESCE(SUM(total_beds), 0) AS total
            FROM hms.rooms
        """)

        return {
            "total_patients": patients,
            "total_doctors": doctors,
            "appointments_today": appointments_today,
            "total_appointments": total_appointments,
            "pending_bills": pending_bills,
            "total_revenue": float(total_revenue),
            "beds_occupied": occupancy["occupied"],
            "beds_total": occupancy["total"],
        }
