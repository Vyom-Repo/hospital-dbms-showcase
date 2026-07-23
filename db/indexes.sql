-- =============================================================================
-- Hospital Management System — Index Definitions
-- Strategic B-Tree and composite indexes on high-traffic columns
-- =============================================================================

SET search_path TO hms, public;

-- =============================================================================
-- APPOINTMENTS — Most heavily queried table
-- =============================================================================

-- Composite: doctor schedule lookups and conflict detection
-- Supports: WHERE doctor_id = ? AND appointment_datetime BETWEEN ? AND ?
CREATE INDEX idx_appointments_doctor_datetime
    ON hms.appointments (doctor_id, appointment_datetime);

-- Patient appointment history
CREATE INDEX idx_appointments_patient
    ON hms.appointments (patient_id);

-- Filter by status (scheduled, completed, cancelled, no_show)
CREATE INDEX idx_appointments_status
    ON hms.appointments (status);

-- Range queries on appointment dates (e.g., "today's appointments")
CREATE INDEX idx_appointments_datetime
    ON hms.appointments (appointment_datetime);

-- Composite: patient's appointments by status (e.g., "my upcoming appointments")
CREATE INDEX idx_appointments_patient_status
    ON hms.appointments (patient_id, status);

-- =============================================================================
-- MEDICAL RECORDS
-- =============================================================================

-- Patient history ordered by most recent first
CREATE INDEX idx_medrec_patient_created
    ON hms.medical_records (patient_id, created_at DESC);

-- Doctor's records
CREATE INDEX idx_medrec_doctor
    ON hms.medical_records (doctor_id);

-- Linked appointment lookup
CREATE INDEX idx_medrec_appointment
    ON hms.medical_records (appointment_id);

-- =============================================================================
-- BILLING
-- =============================================================================

-- Outstanding payment lookups per patient
CREATE INDEX idx_billing_patient_status
    ON hms.billing (patient_id, payment_status);

-- Monthly/quarterly revenue aggregation queries
CREATE INDEX idx_billing_date
    ON hms.billing (bill_date);

-- Payment status filtering
CREATE INDEX idx_billing_status
    ON hms.billing (payment_status);

-- Appointment-linked billing
CREATE INDEX idx_billing_appointment
    ON hms.billing (appointment_id);

-- =============================================================================
-- DOCTORS
-- =============================================================================

-- Department doctor listings
CREATE INDEX idx_doctors_department
    ON hms.doctors (department_id);

-- Availability filtering
CREATE INDEX idx_doctors_availability
    ON hms.doctors (availability_status);

-- Name search
CREATE INDEX idx_doctors_name
    ON hms.doctors (last_name, first_name);

-- =============================================================================
-- PATIENTS
-- =============================================================================

-- Patient name search (reception desk lookups)
CREATE INDEX idx_patients_name
    ON hms.patients (last_name, first_name);

-- Date of birth (age-based queries)
CREATE INDEX idx_patients_dob
    ON hms.patients (date_of_birth);

-- =============================================================================
-- ROOMS
-- =============================================================================

-- Room availability by department and type
CREATE INDEX idx_rooms_dept_type
    ON hms.rooms (department_id, room_type);

-- Available rooms (partial index — only rooms with free beds)
CREATE INDEX idx_rooms_available
    ON hms.rooms (department_id, room_type)
    WHERE occupied_beds < total_beds;
