-- =============================================================================
-- Hospital Management System — Database Schema (DDL)
-- PostgreSQL 14+
-- Normalized to Third Normal Form (3NF)
-- =============================================================================

-- Drop existing objects for idempotent re-runs
DROP SCHEMA IF EXISTS hms CASCADE;
CREATE SCHEMA hms;

SET search_path TO hms, public;

-- =============================================================================
-- 1. DEPARTMENTS
-- =============================================================================
CREATE TABLE hms.departments (
    department_id   SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    building        VARCHAR(50)     NOT NULL,
    floor_number    INTEGER         NOT NULL CHECK (floor_number >= 0),
    phone_extension VARCHAR(10),
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_departments_name UNIQUE (name)
);

COMMENT ON TABLE hms.departments IS 'Hospital departments / clinical divisions';

-- =============================================================================
-- 2. DOCTORS
-- =============================================================================
CREATE TABLE hms.doctors (
    doctor_id           SERIAL          PRIMARY KEY,
    first_name          VARCHAR(60)     NOT NULL,
    last_name           VARCHAR(60)     NOT NULL,
    email               VARCHAR(120)    NOT NULL,
    phone               VARCHAR(20),
    specialization      VARCHAR(100)    NOT NULL,
    department_id       INTEGER         NOT NULL,
    availability_status VARCHAR(20)     NOT NULL DEFAULT 'active'
                            CHECK (availability_status IN ('active', 'on_leave', 'unavailable')),
    hire_date           DATE            NOT NULL,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_doctors_email UNIQUE (email),
    CONSTRAINT fk_doctors_department
        FOREIGN KEY (department_id)
        REFERENCES hms.departments (department_id)
        ON DELETE RESTRICT
);

COMMENT ON TABLE hms.doctors IS 'Physician / specialist roster';

-- =============================================================================
-- 3. PATIENTS
-- =============================================================================
CREATE TABLE hms.patients (
    patient_id              SERIAL          PRIMARY KEY,
    first_name              VARCHAR(60)     NOT NULL,
    last_name               VARCHAR(60)     NOT NULL,
    date_of_birth           DATE            NOT NULL,
    gender                  VARCHAR(1)      NOT NULL CHECK (gender IN ('M', 'F', 'O')),
    email                   VARCHAR(120),
    phone                   VARCHAR(20),
    address                 TEXT,
    blood_group             VARCHAR(5)      CHECK (blood_group IN (
                                'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'
                            )),
    emergency_contact_name  VARCHAR(120),
    emergency_contact_phone VARCHAR(20),
    registered_at           TIMESTAMP       NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_patients_email UNIQUE (email)
);

COMMENT ON TABLE hms.patients IS 'Patient demographic and contact information';

-- =============================================================================
-- 4. ROOMS / WARDS
-- =============================================================================
CREATE TABLE hms.rooms (
    room_id         SERIAL          PRIMARY KEY,
    room_number     VARCHAR(10)     NOT NULL,
    department_id   INTEGER         NOT NULL,
    room_type       VARCHAR(15)     NOT NULL
                        CHECK (room_type IN ('general', 'semi_private', 'private', 'icu')),
    total_beds      INTEGER         NOT NULL CHECK (total_beds > 0),
    occupied_beds   INTEGER         NOT NULL DEFAULT 0 CHECK (occupied_beds >= 0),
    daily_rate      NUMERIC(10, 2)  NOT NULL CHECK (daily_rate > 0),
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_rooms_number UNIQUE (room_number),
    CONSTRAINT chk_rooms_capacity CHECK (occupied_beds <= total_beds),
    CONSTRAINT fk_rooms_department
        FOREIGN KEY (department_id)
        REFERENCES hms.departments (department_id)
        ON DELETE RESTRICT
);

COMMENT ON TABLE hms.rooms IS 'Physical rooms / wards with bed capacity tracking';

-- =============================================================================
-- 5. APPOINTMENTS
-- =============================================================================
CREATE TABLE hms.appointments (
    appointment_id      SERIAL          PRIMARY KEY,
    patient_id          INTEGER         NOT NULL,
    doctor_id           INTEGER         NOT NULL,
    appointment_datetime TIMESTAMP      NOT NULL,
    duration_minutes    INTEGER         NOT NULL DEFAULT 30 CHECK (duration_minutes > 0),
    status              VARCHAR(15)     NOT NULL DEFAULT 'scheduled'
                            CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
    reason              TEXT,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),

    -- Prevent double-booking: one doctor, one time slot
    CONSTRAINT uq_appointments_doctor_slot UNIQUE (doctor_id, appointment_datetime),

    CONSTRAINT fk_appointments_patient
        FOREIGN KEY (patient_id)
        REFERENCES hms.patients (patient_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_appointments_doctor
        FOREIGN KEY (doctor_id)
        REFERENCES hms.doctors (doctor_id)
        ON DELETE RESTRICT
);

COMMENT ON TABLE hms.appointments IS 'Scheduled encounters between patients and doctors';

-- =============================================================================
-- 6. MEDICAL RECORDS
-- =============================================================================
CREATE TABLE hms.medical_records (
    record_id       SERIAL          PRIMARY KEY,
    patient_id      INTEGER         NOT NULL,
    doctor_id       INTEGER         NOT NULL,
    appointment_id  INTEGER,
    diagnosis       TEXT            NOT NULL,
    prescription    TEXT,
    notes           TEXT,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_medrec_patient
        FOREIGN KEY (patient_id)
        REFERENCES hms.patients (patient_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_medrec_doctor
        FOREIGN KEY (doctor_id)
        REFERENCES hms.doctors (doctor_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_medrec_appointment
        FOREIGN KEY (appointment_id)
        REFERENCES hms.appointments (appointment_id)
        ON DELETE SET NULL
);

COMMENT ON TABLE hms.medical_records IS 'Clinical diagnosis, prescriptions, and encounter notes';

-- =============================================================================
-- 7. BILLING
-- =============================================================================
CREATE TABLE hms.billing (
    bill_id         SERIAL          PRIMARY KEY,
    patient_id      INTEGER         NOT NULL,
    appointment_id  INTEGER,
    total_amount    NUMERIC(12, 2)  NOT NULL CHECK (total_amount >= 0),
    paid_amount     NUMERIC(12, 2)  NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
    payment_status  VARCHAR(10)     NOT NULL DEFAULT 'pending'
                        CHECK (payment_status IN ('pending', 'partial', 'paid', 'refunded')),
    payment_method  VARCHAR(15)     CHECK (payment_method IN ('cash', 'card', 'insurance', 'online')),
    bill_date       TIMESTAMP       NOT NULL DEFAULT NOW(),
    paid_date       TIMESTAMP,

    CONSTRAINT chk_billing_paid_lte_total CHECK (paid_amount <= total_amount),
    CONSTRAINT fk_billing_patient
        FOREIGN KEY (patient_id)
        REFERENCES hms.patients (patient_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_billing_appointment
        FOREIGN KEY (appointment_id)
        REFERENCES hms.appointments (appointment_id)
        ON DELETE SET NULL
);

COMMENT ON TABLE hms.billing IS 'Financial records for patient encounters and services';

-- =============================================================================
-- 8. AUDIT LOG (for trigger-based archiving)
-- =============================================================================
CREATE TABLE hms.patient_audit_log (
    log_id      SERIAL          PRIMARY KEY,
    patient_id  INTEGER,
    room_id     INTEGER,
    action      VARCHAR(50)     NOT NULL,
    details     JSONB,
    logged_at   TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE hms.patient_audit_log IS 'Audit trail for patient admissions, discharges, and room changes';
