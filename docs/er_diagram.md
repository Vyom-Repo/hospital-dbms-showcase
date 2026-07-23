# Entity-Relationship Diagram — Hospital DBMS Showcase

This document provides the complete normalized relational schema (up to 3NF) for the **Hospital DBMS Showcase** application.

---

## 📐 ER Diagram (Mermaid.js)

```mermaid
erDiagram
    DEPARTMENTS ||--o{ DOCTORS : employs
    DEPARTMENTS ||--o{ ROOMS : contains
    DOCTORS ||--o{ APPOINTMENTS : attends
    PATIENTS ||--o{ APPOINTMENTS : books
    PATIENTS ||--o{ MEDICAL_RECORDS : has
    DOCTORS ||--o{ MEDICAL_RECORDS : writes
    APPOINTMENTS ||--o| MEDICAL_RECORDS : generates
    PATIENTS ||--o{ BILLING : charged
    APPOINTMENTS ||--o| BILLING : linked
    PATIENTS ||--o{ PATIENT_AUDIT_LOG : tracked
    ROOMS ||--o{ PATIENT_AUDIT_LOG : logged

    DEPARTMENTS {
        int department_id PK
        string name UK
        string building
        int floor_number
        string phone_extension
        timestamp created_at
    }
    DOCTORS {
        int doctor_id PK
        string first_name
        string last_name
        string email UK
        string phone
        string specialization
        int department_id FK
        string availability_status
        date hire_date
    }
    PATIENTS {
        int patient_id PK
        string first_name
        string last_name
        date date_of_birth
        string gender
        string email UK
        string phone
        string address
        string blood_group
        string emergency_contact_name
        string emergency_contact_phone
        timestamp registered_at
    }
    ROOMS {
        int room_id PK
        string room_number UK
        int department_id FK
        string room_type
        int total_beds
        int occupied_beds
        numeric daily_rate
    }
    APPOINTMENTS {
        int appointment_id PK
        int patient_id FK
        int doctor_id FK
        timestamp appointment_datetime
        int duration_minutes
        string status
        string reason
        timestamp created_at
    }
    MEDICAL_RECORDS {
        int record_id PK
        int patient_id FK
        int doctor_id FK
        int appointment_id FK
        text diagnosis
        text prescription
        text notes
        timestamp created_at
    }
    BILLING {
        int bill_id PK
        int patient_id FK
        int appointment_id FK
        numeric total_amount
        numeric paid_amount
        string payment_status
        string payment_method
        timestamp bill_date
        timestamp paid_date
    }
    PATIENT_AUDIT_LOG {
        int log_id PK
        int patient_id FK
        int room_id FK
        string action
        jsonb details
        timestamp logged_at
    }
```

---

## 🔑 Entity Integrity & Constraints Summary

| Entity | Primary Key | Foreign Keys | Unique Constraints | Check Constraints |
|--------|------------|--------------|-------------------|-------------------|
| **DEPARTMENTS** | `department_id` | — | `name` | `floor_number >= 0` |
| **DOCTORS** | `doctor_id` | `department_id` | `email` | `availability_status IN ('active','on_leave','unavailable')` |
| **PATIENTS** | `patient_id` | — | `email` | `gender IN ('M','F','O')`, `blood_group` valid blood type |
| **ROOMS** | `room_id` | `department_id` | `room_number` | `total_beds > 0`, `occupied_beds >= 0 AND <= total_beds`, `daily_rate > 0` |
| **APPOINTMENTS** | `appointment_id` | `patient_id`, `doctor_id` | `(doctor_id, appointment_datetime)` | `status IN ('scheduled','completed','cancelled','no_show')`, `duration_minutes > 0` |
| **MEDICAL_RECORDS** | `record_id` | `patient_id`, `doctor_id`, `appointment_id` | — | — |
| **BILLING** | `bill_id` | `patient_id`, `appointment_id` | — | `total_amount >= 0`, `paid_amount >= 0 AND <= total_amount` |
| **PATIENT_AUDIT_LOG** | `log_id` | `patient_id`, `room_id` | — | — |
