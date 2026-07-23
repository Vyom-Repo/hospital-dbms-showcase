# Demo Recording Instructions

Follow these steps to record a high-quality GIF demo for the **Hospital DBMS Showcase**:

---

## 📽️ Recommended Tools

- **Lapse / ScreenToGif / Peek / LICEcap** (macOS / Linux / Windows)
- Target resolution: `1280x720` or `1440x900`
- Target frame rate: `15-30 fps`

---

## 🎬 Recording Flow

1. **Dashboard Tab**:
   - Start recording on `http://localhost:8000`.
   - Highlight the **100,000 Patients**, **500,000 Appointments**, and **₹91.63 Cr Revenue** header stats.
   - Click **↻ Refresh MV** to show instant materialized view refresh.

2. **Appointments Tab**:
   - Navigate to **Appointments**.
   - Show the `SELECT ... FOR UPDATE` badge and form.

3. **ER Diagram Tab**:
   - Navigate to **ER Diagram**.
   - Show the rendered Mermaid.js interactive schema diagram.

4. **Performance Tab**:
   - Navigate to **Performance**.
   - Click through **Appointment Conflict Detection**, **Patient Medical History**, and **Monthly Revenue Aggregation**.
   - Show the live **EXPLAIN ANALYZE** timing outputs and index scan confirmations.

5. **Save Animation**:
   - Save output as `docs/demo.gif`.
