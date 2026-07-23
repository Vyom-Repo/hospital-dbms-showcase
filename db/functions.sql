-- =============================================================================
-- Hospital Management System — Stored Procedures / Functions
-- Demonstrates: Row-level locking, transaction isolation, atomic multi-table ops
-- =============================================================================

SET search_path TO hms, public;

-- =============================================================================
-- FUNCTION 1: Book Appointment (with SELECT ... FOR UPDATE)
-- Prevents double-booking via row-level locking on the doctor
-- =============================================================================

CREATE OR REPLACE FUNCTION hms.fn_book_appointment(
    p_patient_id        INTEGER,
    p_doctor_id         INTEGER,
    p_datetime          TIMESTAMP,
    p_duration_minutes  INTEGER DEFAULT 30,
    p_reason            TEXT DEFAULT NULL
)
RETURNS TABLE (
    appointment_id      INTEGER,
    status_message      TEXT
) AS $$
DECLARE
    v_doctor_status     VARCHAR(20);
    v_conflict_count    INTEGER;
    v_new_id            INTEGER;
BEGIN
    -- =========================================================================
    -- STEP 1: Lock the doctor row to prevent concurrent booking races.
    -- Any other transaction trying to book this doctor will WAIT here
    -- until this transaction commits or rolls back.
    -- =========================================================================
    SELECT d.availability_status INTO v_doctor_status
    FROM hms.doctors d
    WHERE d.doctor_id = p_doctor_id
    FOR UPDATE;  -- ROW-LEVEL LOCK

    IF NOT FOUND THEN
        RETURN QUERY SELECT -1, 'ERROR: Doctor not found'::TEXT;
        RETURN;
    END IF;

    -- Check doctor is available
    IF v_doctor_status != 'active' THEN
        RETURN QUERY SELECT -1,
            ('ERROR: Doctor is currently ' || v_doctor_status)::TEXT;
        RETURN;
    END IF;

    -- =========================================================================
    -- STEP 2: Check for time-slot conflicts (overlapping appointments)
    -- =========================================================================
    SELECT COUNT(*) INTO v_conflict_count
    FROM hms.appointments a
    WHERE a.doctor_id = p_doctor_id
      AND a.status = 'scheduled'
      AND a.appointment_datetime < p_datetime + (p_duration_minutes || ' minutes')::INTERVAL
      AND a.appointment_datetime + (a.duration_minutes || ' minutes')::INTERVAL > p_datetime;

    IF v_conflict_count > 0 THEN
        RETURN QUERY SELECT -1,
            'ERROR: Time slot conflicts with an existing appointment'::TEXT;
        RETURN;
    END IF;

    -- =========================================================================
    -- STEP 3: Validate patient exists
    -- =========================================================================
    IF NOT EXISTS (SELECT 1 FROM hms.patients WHERE patient_id = p_patient_id) THEN
        RETURN QUERY SELECT -1, 'ERROR: Patient not found'::TEXT;
        RETURN;
    END IF;

    -- =========================================================================
    -- STEP 4: Insert the appointment
    -- =========================================================================
    INSERT INTO hms.appointments (patient_id, doctor_id, appointment_datetime,
                                   duration_minutes, reason, status)
    VALUES (p_patient_id, p_doctor_id, p_datetime,
            p_duration_minutes, p_reason, 'scheduled')
    RETURNING appointments.appointment_id INTO v_new_id;

    RETURN QUERY SELECT v_new_id,
        ('SUCCESS: Appointment #' || v_new_id || ' booked')::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION hms.fn_book_appointment IS
    'Concurrency-safe appointment booking with FOR UPDATE locking on doctor row';


-- =============================================================================
-- FUNCTION 2: Admit Patient (Atomic Multi-Table Transaction)
-- Allocates room + creates appointment + medical record + initial billing
-- =============================================================================

CREATE OR REPLACE FUNCTION hms.fn_admit_patient(
    p_patient_id    INTEGER,
    p_room_id       INTEGER,
    p_doctor_id     INTEGER,
    p_diagnosis     TEXT,
    p_notes         TEXT DEFAULT NULL
)
RETURNS TABLE (
    appointment_id  INTEGER,
    record_id       INTEGER,
    bill_id         INTEGER,
    status_message  TEXT
) AS $$
DECLARE
    v_room_occupied INTEGER;
    v_room_total    INTEGER;
    v_daily_rate    NUMERIC(10, 2);
    v_appt_id       INTEGER;
    v_record_id      INTEGER;
    v_bill_id        INTEGER;
    v_appt_datetime  TIMESTAMP;
BEGIN
    -- =========================================================================
    -- STEP 1: Lock the room row to prevent concurrent bed allocation
    -- =========================================================================
    SELECT r.occupied_beds, r.total_beds, r.daily_rate
    INTO v_room_occupied, v_room_total, v_daily_rate
    FROM hms.rooms r
    WHERE r.room_id = p_room_id
    FOR UPDATE;  -- ROW-LEVEL LOCK

    IF NOT FOUND THEN
        RETURN QUERY SELECT -1, -1, -1, 'ERROR: Room not found'::TEXT;
        RETURN;
    END IF;

    -- Check capacity
    IF v_room_occupied >= v_room_total THEN
        RETURN QUERY SELECT -1, -1, -1, 'ERROR: Room is fully occupied'::TEXT;
        RETURN;
    END IF;

    -- =========================================================================
    -- STEP 2: Allocate bed (increment occupied_beds)
    -- =========================================================================
    UPDATE hms.rooms
    SET occupied_beds = occupied_beds + 1
    WHERE room_id = p_room_id;

    -- =========================================================================
    -- STEP 3: Create appointment for the admission
    -- =========================================================================
    -- Round to next half-hour slot
    v_appt_datetime := date_trunc('hour', NOW()) + 
                        INTERVAL '30 min' * CEIL(EXTRACT(MINUTE FROM NOW()) / 30.0);
    -- Clamp to business hours
    IF EXTRACT(HOUR FROM v_appt_datetime) < 8 THEN
        v_appt_datetime := date_trunc('day', v_appt_datetime) + INTERVAL '8 hours';
    ELSIF EXTRACT(HOUR FROM v_appt_datetime) >= 18 THEN
        v_appt_datetime := date_trunc('day', v_appt_datetime) + INTERVAL '1 day 8 hours';
    END IF;
    -- Skip Sunday
    IF EXTRACT(DOW FROM v_appt_datetime) = 0 THEN
        v_appt_datetime := v_appt_datetime + INTERVAL '1 day';
    END IF;

    INSERT INTO hms.appointments (patient_id, doctor_id, appointment_datetime,
                                   duration_minutes, reason, status)
    VALUES (p_patient_id, p_doctor_id, v_appt_datetime,
            60, 'Hospital Admission: ' || p_diagnosis, 'scheduled')
    RETURNING appointments.appointment_id INTO v_appt_id;

    -- =========================================================================
    -- STEP 4: Create medical record
    -- =========================================================================
    INSERT INTO hms.medical_records (patient_id, doctor_id, appointment_id,
                                      diagnosis, notes)
    VALUES (p_patient_id, p_doctor_id, v_appt_id,
            p_diagnosis, p_notes)
    RETURNING medical_records.record_id INTO v_record_id;

    -- =========================================================================
    -- STEP 5: Generate initial billing record (1 day advance)
    -- =========================================================================
    INSERT INTO hms.billing (patient_id, appointment_id, total_amount,
                              payment_status, bill_date)
    VALUES (p_patient_id, v_appt_id, v_daily_rate,
            'pending', NOW())
    RETURNING billing.bill_id INTO v_bill_id;

    -- =========================================================================
    -- STEP 6: Audit log
    -- =========================================================================
    INSERT INTO hms.patient_audit_log (patient_id, room_id, action, details)
    VALUES (
        p_patient_id, p_room_id, 'PATIENT_ADMITTED',
        jsonb_build_object(
            'doctor_id', p_doctor_id,
            'diagnosis', p_diagnosis,
            'appointment_id', v_appt_id,
            'bill_id', v_bill_id
        )
    );

    RETURN QUERY SELECT v_appt_id, v_record_id, v_bill_id,
        'SUCCESS: Patient admitted, room allocated, records created'::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION hms.fn_admit_patient IS
    'Atomic admission: room allocation (FOR UPDATE) + appointment + medical record + billing';


-- =============================================================================
-- FUNCTION 3: Discharge Patient
-- Frees bed + finalizes billing
-- =============================================================================

CREATE OR REPLACE FUNCTION hms.fn_discharge_patient(
    p_patient_id    INTEGER,
    p_room_id       INTEGER
)
RETURNS TABLE (
    status_message  TEXT
) AS $$
DECLARE
    v_occupied  INTEGER;
BEGIN
    -- Lock room for safe decrement
    SELECT r.occupied_beds INTO v_occupied
    FROM hms.rooms r
    WHERE r.room_id = p_room_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT 'ERROR: Room not found'::TEXT;
        RETURN;
    END IF;

    IF v_occupied <= 0 THEN
        RETURN QUERY SELECT 'ERROR: Room has no occupied beds'::TEXT;
        RETURN;
    END IF;

    -- Free the bed
    UPDATE hms.rooms
    SET occupied_beds = occupied_beds - 1
    WHERE room_id = p_room_id;

    -- Mark pending appointments as completed
    UPDATE hms.appointments
    SET status = 'completed'
    WHERE patient_id = p_patient_id
      AND status = 'scheduled';

    -- Log discharge
    INSERT INTO hms.patient_audit_log (patient_id, room_id, action, details)
    VALUES (
        p_patient_id, p_room_id, 'PATIENT_DISCHARGED',
        jsonb_build_object('discharged_at', NOW()::TEXT)
    );

    RETURN QUERY SELECT 'SUCCESS: Patient discharged, bed freed'::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION hms.fn_discharge_patient IS
    'Discharge: free bed (FOR UPDATE) + complete appointments + audit log';


-- =============================================================================
-- FUNCTION 4: Monthly Revenue by Department
-- =============================================================================

CREATE OR REPLACE FUNCTION hms.fn_monthly_revenue(
    p_year   INTEGER,
    p_month  INTEGER
)
RETURNS TABLE (
    department_name     VARCHAR(100),
    total_billed        NUMERIC,
    total_collected     NUMERIC,
    outstanding         NUMERIC,
    bill_count          BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dep.name                                AS department_name,
        COALESCE(SUM(b.total_amount), 0)       AS total_billed,
        COALESCE(SUM(b.paid_amount), 0)        AS total_collected,
        COALESCE(SUM(b.total_amount - b.paid_amount), 0) AS outstanding,
        COUNT(b.bill_id)                        AS bill_count
    FROM hms.billing b
    JOIN hms.appointments a ON a.appointment_id = b.appointment_id
    JOIN hms.doctors d ON d.doctor_id = a.doctor_id
    JOIN hms.departments dep ON dep.department_id = d.department_id
    WHERE EXTRACT(YEAR FROM b.bill_date) = p_year
      AND EXTRACT(MONTH FROM b.bill_date) = p_month
    GROUP BY dep.department_id, dep.name
    ORDER BY total_billed DESC;
END;
$$ LANGUAGE plpgsql;
