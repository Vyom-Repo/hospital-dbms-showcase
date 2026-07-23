"""
Database Population Tool
Generates synthetic benchmark datasets using Faker and asyncpg bulk COPY buffers.
"""

import asyncio
import asyncpg
import io
import os
import random
import sys
from datetime import datetime, timedelta, date
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

fake = Faker()
Faker.seed(42)
random.seed(42)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "vyom"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "hms_db"),
}

# ─── Data Constants ──────────────────────────────────────────────────────────
DEPARTMENTS = [
    ("Cardiology", "Main Building", 2),
    ("Neurology", "Main Building", 3),
    ("Orthopedics", "Main Building", 1),
    ("Pediatrics", "East Wing", 1),
    ("Oncology", "West Wing", 2),
    ("Dermatology", "East Wing", 2),
    ("Gastroenterology", "Main Building", 4),
    ("Pulmonology", "West Wing", 1),
    ("Ophthalmology", "East Wing", 3),
    ("ENT", "East Wing", 3),
    ("Urology", "West Wing", 2),
    ("Nephrology", "West Wing", 3),
    ("Psychiatry", "North Wing", 1),
    ("Emergency Medicine", "Main Building", 0),
    ("General Surgery", "Main Building", 1),
]

SPECIALIZATIONS = {
    1: "Cardiology", 2: "Neurology", 3: "Orthopedics", 4: "Pediatrics",
    5: "Oncology", 6: "Dermatology", 7: "Gastroenterology",
    8: "Pulmonology", 9: "Ophthalmology", 10: "ENT",
    11: "Urology", 12: "Nephrology", 13: "Psychiatry",
    14: "Emergency Medicine", 15: "General Surgery",
}

ROOM_TYPES = ["general", "semi_private", "private", "icu"]
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
GENDERS = ["M", "F", "O"]
APPOINTMENT_STATUSES = ["scheduled", "completed", "cancelled", "no_show"]
PAYMENT_METHODS = ["cash", "card", "insurance", "online"]
PAYMENT_STATUSES = ["pending", "partial", "paid"]

DIAGNOSES = [
    "Hypertension", "Type 2 Diabetes", "Upper Respiratory Infection",
    "Migraine", "Osteoarthritis", "Anxiety Disorder", "Gastritis",
    "Asthma", "Conjunctivitis", "Sinusitis", "Urinary Tract Infection",
    "Chronic Kidney Disease", "Depression", "Fracture", "Appendicitis",
    "Pneumonia", "Bronchitis", "Eczema", "Psoriasis", "Anemia",
    "Heart Failure", "Atrial Fibrillation", "Epilepsy", "COPD",
    "Allergic Rhinitis", "Gastroesophageal Reflux", "Hepatitis",
    "Thyroid Disorder", "Lupus", "Rheumatoid Arthritis",
]

PRESCRIPTIONS = [
    "Metformin 500mg twice daily", "Lisinopril 10mg once daily",
    "Amoxicillin 500mg three times daily for 7 days",
    "Ibuprofen 400mg as needed", "Omeprazole 20mg before breakfast",
    "Albuterol inhaler as needed", "Sertraline 50mg once daily",
    "Atorvastatin 20mg at bedtime", "Metoprolol 25mg twice daily",
    "Prednisone 10mg tapering dose", "Gabapentin 300mg three times daily",
    "Levothyroxine 50mcg before breakfast", "Warfarin 5mg once daily",
    "Clopidogrel 75mg once daily", "Amlodipine 5mg once daily",
    None,  # Some records have no prescription
]

NUM_DOCTORS = 200
NUM_PATIENTS = 100_000
NUM_ROOMS = 300
NUM_APPOINTMENTS = 500_000
NUM_MEDICAL_RECORDS = 400_000
NUM_BILLING = 500_000


def progress(label: str, current: int, total: int):
    """Print progress bar."""
    pct = current / total * 100
    bar_len = 40
    filled = int(bar_len * current // total)
    bar = "█" * filled + "░" * (bar_len - filled)
    sys.stdout.write(f"\r  {label}: {bar} {pct:5.1f}% ({current:,}/{total:,})")
    sys.stdout.flush()
    if current == total:
        print()


async def copy_from_csv(conn, table: str, columns: list[str], buffer: io.StringIO):
    """Bulk insert via COPY FROM STDIN."""
    data_bytes = buffer.getvalue().encode("utf-8")
    await conn.copy_to_table(
        table,
        source=io.BytesIO(data_bytes),
        schema_name="hms",
        columns=columns,
        format="csv",
    )


async def generate():
    print("=" * 60)
    print("  Hospital Management System — Data Generator")
    print("=" * 60)

    conn = await asyncpg.connect(**DB_CONFIG)

    # Set search path
    await conn.execute("SET search_path TO hms, public")

    # Clean existing data for a fresh generation
    print("  Truncating existing tables...")
    await conn.execute("""
        TRUNCATE TABLE billing, medical_records, appointments, rooms, patients, doctors, departments RESTART IDENTITY CASCADE;
    """)

    # ─── 1. Departments ──────────────────────────────────────────────────
    print("\n[1/7] Generating Departments...")
    for name, building, floor in DEPARTMENTS:
        await conn.execute("""
            INSERT INTO departments (name, building, floor_number, phone_extension)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (name) DO NOTHING
        """, name, building, floor, f"x{random.randint(100, 999)}")
    print(f"  ✓ {len(DEPARTMENTS)} departments inserted")

    # Fetch actual department IDs from database
    dept_rows = await conn.fetch("SELECT department_id FROM departments ORDER BY department_id")
    dept_ids = [r["department_id"] for r in dept_rows]

    # ─── 2. Doctors ──────────────────────────────────────────────────────
    print(f"\n[2/7] Generating {NUM_DOCTORS:,} Doctors...")
    buf = io.StringIO()
    used_emails = set()
    for i in range(NUM_DOCTORS):
        dept_id = random.choice(dept_ids)
        first = fake.first_name()
        last = fake.last_name()
        email = f"dr.{first.lower()}.{last.lower()}.{i}@hospital.org"
        while email in used_emails:
            email = f"dr.{first.lower()}.{last.lower()}.{random.randint(1000,9999)}@hospital.org"
        used_emails.add(email)
        phone = fake.phone_number()[:20]
        spec = SPECIALIZATIONS.get(dept_id % len(SPECIALIZATIONS) + 1, "General Medicine")
        hire = fake.date_between(start_date="-15y", end_date="-1y")
        buf.write(f"{first},{last},{email},{phone},{spec},{dept_id},active,{hire}\n")
        if (i + 1) % 50 == 0:
            progress("Doctors", i + 1, NUM_DOCTORS)

    await copy_from_csv(conn, "doctors", [
        "first_name", "last_name", "email", "phone",
        "specialization", "department_id", "availability_status", "hire_date"
    ], buf)
    progress("Doctors", NUM_DOCTORS, NUM_DOCTORS)

    # ─── 3. Patients ─────────────────────────────────────────────────────
    print(f"\n[3/7] Generating {NUM_PATIENTS:,} Patients...")
    buf = io.StringIO()
    used_emails.clear()
    batch_size = 10_000
    for i in range(NUM_PATIENTS):
        first = fake.first_name()
        last = fake.last_name()
        dob = fake.date_of_birth(minimum_age=1, maximum_age=95)
        gender = random.choice(GENDERS)
        email = f"{first.lower()}.{last.lower()}.{i}@email.com"
        phone = fake.phone_number()[:20]
        address = fake.address().replace("\n", ", ").replace('"', "'")
        blood = random.choice(BLOOD_GROUPS)
        ec_name = fake.name()
        ec_phone = fake.phone_number()[:20]

        # CSV escaping: wrap address in quotes
        buf.write(
            f'{first},{last},{dob},{gender},{email},{phone},'
            f'"{address}",{blood},{ec_name},{ec_phone}\n'
        )

        if (i + 1) % batch_size == 0:
            progress("Patients", i + 1, NUM_PATIENTS)

    await copy_from_csv(conn, "patients", [
        "first_name", "last_name", "date_of_birth", "gender",
        "email", "phone", "address", "blood_group",
        "emergency_contact_name", "emergency_contact_phone"
    ], buf)
    progress("Patients", NUM_PATIENTS, NUM_PATIENTS)

    # ─── 4. Rooms ────────────────────────────────────────────────────────
    print(f"\n[4/7] Generating {NUM_ROOMS:,} Rooms...")
    buf = io.StringIO()
    for i in range(NUM_ROOMS):
        dept_id = random.choice(dept_ids)
        room_type = random.choice(ROOM_TYPES)
        if room_type == "icu":
            total_beds = random.randint(1, 3)
            rate = random.uniform(800, 2000)
        elif room_type == "private":
            total_beds = 1
            rate = random.uniform(400, 800)
        elif room_type == "semi_private":
            total_beds = random.randint(2, 4)
            rate = random.uniform(200, 400)
        else:  # general
            total_beds = random.randint(4, 10)
            rate = random.uniform(80, 200)

        occupied = random.randint(0, total_beds)
        room_num = f"{dept_id:02d}{chr(65 + i % 26)}{i // 26 + 1:02d}"
        buf.write(f"{room_num},{dept_id},{room_type},{total_beds},{occupied},{rate:.2f}\n")

    await copy_from_csv(conn, "rooms", [
        "room_number", "department_id", "room_type",
        "total_beds", "occupied_beds", "daily_rate"
    ], buf)
    progress("Rooms", NUM_ROOMS, NUM_ROOMS)

    # ─── 5. Appointments ─────────────────────────────────────────────────
    # Disable the validation trigger for bulk insert (past dates needed)
    print(f"\n[5/7] Generating {NUM_APPOINTMENTS:,} Appointments...")
    await conn.execute("ALTER TABLE hms.appointments DISABLE TRIGGER trg_validate_appointment_time")
    await conn.execute("ALTER TABLE hms.appointments DISABLE TRIGGER trg_update_doctor_availability")

    buf = io.StringIO()
    # Generate appointments spread across 2 years
    start_date = datetime(2024, 1, 1, 8, 0)
    batch_size = 50_000
    doctor_slots = {}  # Track (doctor_id, datetime) to avoid unique violations

    for i in range(NUM_APPOINTMENTS):
        patient_id = random.randint(1, NUM_PATIENTS)
        doctor_id = random.randint(1, NUM_DOCTORS)

        # Random date in 2-year range, business hours (8-17), half-hour slots
        days_offset = random.randint(0, 730)
        hour = random.randint(8, 17)
        minute = random.choice([0, 30])
        appt_dt = start_date + timedelta(days=days_offset, hours=hour - 8, minutes=minute)

        # Skip Sundays
        if appt_dt.weekday() == 6:
            appt_dt += timedelta(days=1)

        # Ensure unique (doctor_id, datetime)
        slot_key = (doctor_id, appt_dt)
        attempts = 0
        while slot_key in doctor_slots and attempts < 5:
            minute = random.choice([0, 30])
            hour = random.randint(8, 17)
            appt_dt = start_date + timedelta(
                days=random.randint(0, 730), hours=hour - 8, minutes=minute
            )
            if appt_dt.weekday() == 6:
                appt_dt += timedelta(days=1)
            slot_key = (doctor_id, appt_dt)
            attempts += 1

        if slot_key in doctor_slots:
            continue  # Skip this one to avoid violations

        doctor_slots[slot_key] = True

        duration = random.choice([15, 30, 30, 30, 45, 60])
        status = random.choices(
            APPOINTMENT_STATUSES, weights=[15, 60, 15, 10]
        )[0]
        reason = random.choice(DIAGNOSES)

        buf.write(
            f"{patient_id},{doctor_id},{appt_dt.isoformat()},{duration},{status},"
            f'"{reason}"\n'
        )

        if (i + 1) % batch_size == 0:
            progress("Appointments", i + 1, NUM_APPOINTMENTS)

    await copy_from_csv(conn, "appointments", [
        "patient_id", "doctor_id", "appointment_datetime",
        "duration_minutes", "status", "reason"
    ], buf)
    progress("Appointments", NUM_APPOINTMENTS, NUM_APPOINTMENTS)

    # Re-enable triggers
    await conn.execute("ALTER TABLE hms.appointments ENABLE TRIGGER trg_validate_appointment_time")
    await conn.execute("ALTER TABLE hms.appointments ENABLE TRIGGER trg_update_doctor_availability")

    # ─── 6. Medical Records ──────────────────────────────────────────────
    print(f"\n[6/7] Generating {NUM_MEDICAL_RECORDS:,} Medical Records...")

    # Get actual appointment IDs for valid FK references
    appt_ids = await conn.fetch(
        "SELECT appointment_id, patient_id, doctor_id FROM appointments "
        "WHERE status = 'completed' LIMIT $1", NUM_MEDICAL_RECORDS
    )

    buf = io.StringIO()
    for i, appt in enumerate(appt_ids):
        diagnosis = random.choice(DIAGNOSES)
        prescription = random.choice(PRESCRIPTIONS) or ""
        notes = fake.sentence(nb_words=12).replace('"', "'") if random.random() > 0.3 else ""

        buf.write(
            f'{appt["patient_id"]},{appt["doctor_id"]},{appt["appointment_id"]},'
            f'"{diagnosis}","{prescription}","{notes}"\n'
        )

        if (i + 1) % 50_000 == 0:
            progress("Medical Records", i + 1, len(appt_ids))

    actual_records = len(appt_ids)
    await copy_from_csv(conn, "medical_records", [
        "patient_id", "doctor_id", "appointment_id",
        "diagnosis", "prescription", "notes"
    ], buf)
    progress("Medical Records", actual_records, actual_records)

    # ─── 7. Billing ──────────────────────────────────────────────────────
    print(f"\n[7/7] Generating {NUM_BILLING:,} Billing records...")

    # Get appointment IDs for billing
    all_appt_ids = await conn.fetch(
        "SELECT appointment_id, patient_id FROM appointments LIMIT $1",
        NUM_BILLING
    )

    buf = io.StringIO()
    for i, appt in enumerate(all_appt_ids):
        total = round(random.uniform(50, 5000), 2)
        pay_status = random.choices(PAYMENT_STATUSES, weights=[20, 15, 65])[0]

        if pay_status == "paid":
            paid = total
        elif pay_status == "partial":
            paid = round(random.uniform(10, total - 1), 2)
        else:
            paid = 0.0

        method = random.choice(PAYMENT_METHODS) if paid > 0 else ""
        bill_date = fake.date_time_between(start_date="-2y", end_date="now")
        paid_date = bill_date + timedelta(days=random.randint(0, 30)) if pay_status == "paid" else ""

        buf.write(
            f'{appt["patient_id"]},{appt["appointment_id"]},'
            f'{total},{paid},{pay_status},{method},{bill_date},{paid_date}\n'
        )

        if (i + 1) % 50_000 == 0:
            progress("Billing", i + 1, len(all_appt_ids))

    actual_bills = len(all_appt_ids)
    await copy_from_csv(conn, "billing", [
        "patient_id", "appointment_id", "total_amount", "paid_amount",
        "payment_status", "payment_method", "bill_date", "paid_date"
    ], buf)
    progress("Billing", actual_bills, actual_bills)

    # ─── Refresh materialized view ───────────────────────────────────────
    print("\n  Refreshing materialized view...")
    await conn.execute("REFRESH MATERIALIZED VIEW hms.mv_department_statistics")

    # ─── Update table statistics ─────────────────────────────────────────
    print("  Analyzing tables for query planner...")
    await conn.execute("ANALYZE")

    # ─── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  DATA GENERATION COMPLETE")
    print("=" * 60)

    tables = [
        "departments", "doctors", "patients", "rooms",
        "appointments", "medical_records", "billing",
    ]
    for t in tables:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t:25s} → {count:>10,} rows")

    await conn.close()
    print("\n  ✓ Done!")


if __name__ == "__main__":
    asyncio.run(generate())
