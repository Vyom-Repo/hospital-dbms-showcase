-- =============================================================================
-- Hospital Management System — Triggers
-- Business logic enforced at the database level
-- =============================================================================

SET search_path TO hms, public;

-- =============================================================================
-- TRIGGER 1: Validate appointment time (BEFORE INSERT)
-- Rejects appointments outside business hours or in the past
-- =============================================================================

CREATE OR REPLACE FUNCTION hms.fn_trg_validate_appointment_time()
RETURNS TRIGGER AS $$
BEGIN
    -- Reject appointments in the past
    IF NEW.appointment_datetime < NOW() THEN
        RAISE EXCEPTION 'Cannot book appointments in the past. Requested: %',
            NEW.appointment_datetime;
    END IF;

    -- Reject appointments outside business hours (8:00 AM – 18:00 PM)
    IF EXTRACT(HOUR FROM NEW.appointment_datetime) < 8
       OR EXTRACT(HOUR FROM NEW.appointment_datetime) >= 18 THEN
        RAISE EXCEPTION 'Appointments must be between 08:00 and 18:00. Requested hour: %',
            EXTRACT(HOUR FROM NEW.appointment_datetime);
    END IF;

    -- Reject Sunday appointments
    IF EXTRACT(DOW FROM NEW.appointment_datetime) = 0 THEN
        RAISE EXCEPTION 'Appointments cannot be booked on Sundays.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_appointment_time
    BEFORE INSERT ON hms.appointments
    FOR EACH ROW
    EXECUTE FUNCTION hms.fn_trg_validate_appointment_time();

-- =============================================================================
-- TRIGGER 2: Auto-update doctor availability (AFTER INSERT/DELETE)
-- When a doctor has >= 15 appointments in a single day → mark unavailable
-- =============================================================================

CREATE OR REPLACE FUNCTION hms.fn_trg_update_doctor_availability()
RETURNS TRIGGER AS $$
DECLARE
    v_doctor_id     INTEGER;
    v_appt_date     DATE;
    v_count         INTEGER;
    v_max_daily     INTEGER := 15;
BEGIN
    -- Determine which doctor/date to check
    IF TG_OP = 'DELETE' THEN
        v_doctor_id := OLD.doctor_id;
        v_appt_date := OLD.appointment_datetime::DATE;
    ELSE
        v_doctor_id := NEW.doctor_id;
        v_appt_date := NEW.appointment_datetime::DATE;
    END IF;

    -- Count active appointments for this doctor on this date
    SELECT COUNT(*) INTO v_count
    FROM hms.appointments
    WHERE doctor_id = v_doctor_id
      AND appointment_datetime::DATE = v_appt_date
      AND status IN ('scheduled', 'completed');

    -- Update availability accordingly
    IF v_count >= v_max_daily THEN
        UPDATE hms.doctors
        SET availability_status = 'unavailable'
        WHERE doctor_id = v_doctor_id
          AND availability_status = 'active';
    ELSE
        UPDATE hms.doctors
        SET availability_status = 'active'
        WHERE doctor_id = v_doctor_id
          AND availability_status = 'unavailable';
    END IF;

    RETURN NULL; -- AFTER trigger, return value ignored
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_doctor_availability
    AFTER INSERT OR DELETE ON hms.appointments
    FOR EACH ROW
    EXECUTE FUNCTION hms.fn_trg_update_doctor_availability();

-- =============================================================================
-- TRIGGER 3: Auto-update billing payment status (BEFORE UPDATE)
-- Sets payment_status based on paid_amount vs total_amount
-- =============================================================================

CREATE OR REPLACE FUNCTION hms.fn_trg_auto_payment_status()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.paid_amount >= NEW.total_amount AND NEW.total_amount > 0 THEN
        NEW.payment_status := 'paid';
        NEW.paid_date := COALESCE(NEW.paid_date, NOW());
    ELSIF NEW.paid_amount > 0 AND NEW.paid_amount < NEW.total_amount THEN
        NEW.payment_status := 'partial';
    ELSIF NEW.paid_amount = 0 THEN
        NEW.payment_status := 'pending';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auto_payment_status
    BEFORE UPDATE ON hms.billing
    FOR EACH ROW
    WHEN (OLD.paid_amount IS DISTINCT FROM NEW.paid_amount)
    EXECUTE FUNCTION hms.fn_trg_auto_payment_status();

-- =============================================================================
-- TRIGGER 4: Audit log for room occupancy changes (AFTER UPDATE)
-- Logs admission/discharge events when occupied_beds changes
-- =============================================================================

CREATE OR REPLACE FUNCTION hms.fn_trg_audit_room_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.occupied_beds > OLD.occupied_beds THEN
        -- Admission event
        INSERT INTO hms.patient_audit_log (room_id, action, details)
        VALUES (
            NEW.room_id,
            'ROOM_ADMISSION',
            jsonb_build_object(
                'room_number', NEW.room_number,
                'previous_occupied', OLD.occupied_beds,
                'current_occupied', NEW.occupied_beds,
                'total_beds', NEW.total_beds
            )
        );
    ELSIF NEW.occupied_beds < OLD.occupied_beds THEN
        -- Discharge event
        INSERT INTO hms.patient_audit_log (room_id, action, details)
        VALUES (
            NEW.room_id,
            'ROOM_DISCHARGE',
            jsonb_build_object(
                'room_number', NEW.room_number,
                'previous_occupied', OLD.occupied_beds,
                'current_occupied', NEW.occupied_beds,
                'beds_freed', OLD.occupied_beds - NEW.occupied_beds
            )
        );
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_room_changes
    AFTER UPDATE ON hms.rooms
    FOR EACH ROW
    WHEN (OLD.occupied_beds IS DISTINCT FROM NEW.occupied_beds)
    EXECUTE FUNCTION hms.fn_trg_audit_room_changes();
