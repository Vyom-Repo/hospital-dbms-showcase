-- =============================================================================
-- Hospital Management System — Views
-- Standard views for real-time queries, materialized view for heavy aggregation
-- =============================================================================

SET search_path TO hms, public;

-- =============================================================================
-- VIEW 1: Monthly Revenue by Department
-- =============================================================================

CREATE OR REPLACE VIEW hms.v_monthly_revenue_by_department AS
SELECT
    dep.department_id,
    dep.name                                    AS department_name,
    TO_CHAR(b.bill_date, 'YYYY-MM')           AS month,
    COUNT(b.bill_id)                            AS total_bills,
    SUM(b.total_amount)                         AS total_billed,
    SUM(b.paid_amount)                          AS total_collected,
    SUM(b.total_amount - b.paid_amount)        AS outstanding_amount,
    ROUND(
        CASE WHEN SUM(b.total_amount) > 0
             THEN (SUM(b.paid_amount) / SUM(b.total_amount)) * 100
             ELSE 0
        END, 2
    )                                           AS collection_rate_pct
FROM hms.billing b
JOIN hms.appointments a ON a.appointment_id = b.appointment_id
JOIN hms.doctors d ON d.doctor_id = a.doctor_id
JOIN hms.departments dep ON dep.department_id = d.department_id
GROUP BY dep.department_id, dep.name, TO_CHAR(b.bill_date, 'YYYY-MM')
ORDER BY month DESC, total_billed DESC;

COMMENT ON VIEW hms.v_monthly_revenue_by_department IS
    'Revenue breakdown by department and month with collection rates';

-- =============================================================================
-- VIEW 2: Doctor Appointment Load
-- =============================================================================

CREATE OR REPLACE VIEW hms.v_doctor_appointment_load AS
SELECT
    d.doctor_id,
    d.first_name || ' ' || d.last_name         AS doctor_name,
    d.specialization,
    dep.name                                    AS department_name,
    d.availability_status,
    COUNT(a.appointment_id) FILTER (WHERE a.status = 'scheduled')
                                                AS upcoming_appointments,
    COUNT(a.appointment_id) FILTER (WHERE a.status = 'completed')
                                                AS completed_appointments,
    COUNT(a.appointment_id) FILTER (WHERE a.status = 'cancelled')
                                                AS cancelled_appointments,
    COUNT(a.appointment_id)                     AS total_appointments,
    ROUND(AVG(a.duration_minutes), 1)           AS avg_duration_minutes,
    MAX(a.appointment_datetime) FILTER (WHERE a.status = 'scheduled')
                                                AS next_appointment
FROM hms.doctors d
LEFT JOIN hms.appointments a ON a.doctor_id = d.doctor_id
LEFT JOIN hms.departments dep ON dep.department_id = d.department_id
GROUP BY d.doctor_id, d.first_name, d.last_name, d.specialization,
         dep.name, d.availability_status
ORDER BY upcoming_appointments DESC;

COMMENT ON VIEW hms.v_doctor_appointment_load IS
    'Per-doctor workload: appointment counts by status, average duration, next scheduled';

-- =============================================================================
-- VIEW 3: Room Occupancy Dashboard
-- =============================================================================

CREATE OR REPLACE VIEW hms.v_room_occupancy_dashboard AS
SELECT
    r.room_id,
    r.room_number,
    dep.name                                    AS department_name,
    r.room_type,
    r.total_beds,
    r.occupied_beds,
    (r.total_beds - r.occupied_beds)           AS available_beds,
    ROUND(
        (r.occupied_beds::NUMERIC / r.total_beds) * 100, 1
    )                                           AS occupancy_rate_pct,
    r.daily_rate,
    CASE
        WHEN r.occupied_beds >= r.total_beds THEN 'FULL'
        WHEN r.occupied_beds::NUMERIC / r.total_beds > 0.8 THEN 'HIGH'
        WHEN r.occupied_beds::NUMERIC / r.total_beds > 0.5 THEN 'MODERATE'
        ELSE 'LOW'
    END                                         AS occupancy_level
FROM hms.rooms r
JOIN hms.departments dep ON dep.department_id = r.department_id
ORDER BY occupancy_rate_pct DESC;

COMMENT ON VIEW hms.v_room_occupancy_dashboard IS
    'Real-time room occupancy rates with availability status indicators';

-- =============================================================================
-- VIEW 4: Patient Billing Summary
-- =============================================================================

CREATE OR REPLACE VIEW hms.v_patient_billing_summary AS
SELECT
    p.patient_id,
    p.first_name || ' ' || p.last_name         AS patient_name,
    p.email,
    p.phone,
    COUNT(b.bill_id)                            AS total_bills,
    COALESCE(SUM(b.total_amount), 0)           AS total_billed,
    COALESCE(SUM(b.paid_amount), 0)            AS total_paid,
    COALESCE(SUM(b.total_amount - b.paid_amount), 0) AS outstanding_balance,
    COUNT(b.bill_id) FILTER (WHERE b.payment_status = 'pending')
                                                AS pending_bills,
    COUNT(b.bill_id) FILTER (WHERE b.payment_status = 'paid')
                                                AS paid_bills
FROM hms.patients p
LEFT JOIN hms.billing b ON b.patient_id = p.patient_id
GROUP BY p.patient_id, p.first_name, p.last_name, p.email, p.phone
ORDER BY outstanding_balance DESC;

COMMENT ON VIEW hms.v_patient_billing_summary IS
    'Per-patient financial overview: billed, paid, and outstanding amounts';

-- =============================================================================
-- MATERIALIZED VIEW 5: Department Statistics (heavy aggregation)
-- Refresh periodically via: REFRESH MATERIALIZED VIEW hms.mv_department_statistics;
-- =============================================================================

CREATE MATERIALIZED VIEW hms.mv_department_statistics AS
SELECT
    dep.department_id,
    dep.name                                    AS department_name,
    dep.building,
    dep.floor_number,

    -- Doctor stats
    COUNT(DISTINCT d.doctor_id)                AS total_doctors,
    COUNT(DISTINCT d.doctor_id) FILTER (WHERE d.availability_status = 'active')
                                                AS active_doctors,

    -- Room stats
    COUNT(DISTINCT r.room_id)                  AS total_rooms,
    COALESCE(SUM(DISTINCT r.total_beds), 0)   AS total_beds,
    COALESCE(SUM(DISTINCT r.occupied_beds), 0) AS occupied_beds,

    -- Appointment stats (last 30 days)
    COUNT(a.appointment_id) FILTER (
        WHERE a.appointment_datetime >= NOW() - INTERVAL '30 days'
    )                                           AS appointments_last_30d,

    -- Revenue stats (last 30 days)
    COALESCE(SUM(b.total_amount) FILTER (
        WHERE b.bill_date >= NOW() - INTERVAL '30 days'
    ), 0)                                       AS revenue_last_30d

FROM hms.departments dep
LEFT JOIN hms.doctors d ON d.department_id = dep.department_id
LEFT JOIN hms.rooms r ON r.department_id = dep.department_id
LEFT JOIN hms.appointments a ON a.doctor_id = d.doctor_id
LEFT JOIN hms.billing b ON b.appointment_id = a.appointment_id
GROUP BY dep.department_id, dep.name, dep.building, dep.floor_number
ORDER BY department_name;

-- Unique index required for CONCURRENT refresh
CREATE UNIQUE INDEX idx_mv_dept_stats_id
    ON hms.mv_department_statistics (department_id);

COMMENT ON MATERIALIZED VIEW hms.mv_department_statistics IS
    'Precomputed department-level statistics; refresh via REFRESH MATERIALIZED VIEW CONCURRENTLY';
