# System Architecture — Hospital DBMS Showcase

This document details the multi-tier database-centric architecture of the **Hospital DBMS Showcase**.

---

## 🏛️ Architecture Flow

```mermaid
graph TD
    UI[Browser Single-Page App\nHTML / CSS / JS / Mermaid.js] -->|HTTP REST Requests| API[FastAPI Server\nPython 3.11+]
    API -->|Async Pool Connection| POOL[asyncpg Connection Pool\nMin: 5, Max: 20]
    POOL -->|Raw SQL Queries| PG[(PostgreSQL Database\nhms_db)]

    subgraph PostgreSQL DBMS Engine
        PG --> TBL[3NF Relational Tables\n7 Core Entities + Audit Log]
        PG --> IDX[Indexes\nComposite B-Tree & Partial Indexes]
        PG --> TRG[Triggers\nAppointment, Status, Audit]
        PG --> FN[Stored Procedures\nFOR UPDATE Lock Procedures]
        PG --> VW[Views & Materialized Views\nMV Department Statistics]
    end
```

---

## 🔒 Concurrency & Transaction Control Architecture

1. **Row-Level Locking (`SELECT FOR UPDATE`)**:
   - Doctor schedule slot conflicts are locked at row-level inside atomic transaction blocks.
   - Bed allocation locks `hms.rooms` row before updating `occupied_beds` count.

2. **Atomic Multi-Table Transactions**:
   - `fn_admit_patient` executes room lock, bed counter increment, appointment creation, medical record initialization, and billing record creation in a single transaction block.

3. **Materialized View Concurrent Refreshes**:
   - `mv_department_statistics` supports `REFRESH MATERIALIZED VIEW CONCURRENTLY` to provide instantaneous analytical reads without blocking write transactions.
