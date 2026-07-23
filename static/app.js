/**
 * Frontend Controller
 * Interface state management, tab routing, and REST API integration.
 */

const HMS = (() => {
    const state = {
        currentTab: 'dashboard',
        pagination: {
            patients: { offset: 0, limit: 50 },
            doctors: { offset: 0, limit: 50 },
            appointments: { offset: 0, limit: 50 },
            billing: { offset: 0, limit: 50 },
        },
    };

    // ─── API Helper ─────────────────────────────────────────────────────
    async function api(url, options = {}) {
        try {
            const resp = await fetch(url, {
                headers: { 'Content-Type': 'application/json' },
                ...options,
            });
            if (!resp.ok) {
                const text = await resp.text();
                let detail = text;
                try {
                    const parsed = JSON.parse(text);
                    detail = parsed.detail || text;
                } catch (e) {}
                throw new Error(detail);
            }
            const data = await resp.json();
            return data;
        } catch (err) {
            toast(err.message, 'error');
            throw err;
        }
    }

    // ─── Toast Notifications ────────────────────────────────────────────
    function toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const el = document.createElement('div');
        el.className = `toast toast-${type}`;
        el.textContent = message;
        container.appendChild(el);
        setTimeout(() => el.remove(), 4000);
    }

    // ─── Format Helpers ─────────────────────────────────────────────────
    function formatDate(val) {
        if (!val) return '—';
        const d = new Date(val);
        return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    }

    function formatDateTime(val) {
        if (!val) return '—';
        const d = new Date(val);
        return d.toLocaleDateString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    }

    function formatCurrency(val) {
        if (val == null) return '—';
        const num = Number(val);
        if (isNaN(num)) return '—';
        return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function formatCurrencyCompact(val) {
        if (val == null) return '—';
        const num = Number(val);
        if (isNaN(num)) return '—';
        if (num >= 10000000) {
            return '₹' + (num / 10000000).toFixed(2) + ' Cr';
        } else if (num >= 100000) {
            return '₹' + (num / 100000).toFixed(2) + ' Lakh';
        }
        return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function formatNumber(val) {
        if (val == null) return '—';
        return Number(val).toLocaleString('en-IN');
    }

    function statusBadge(val) {
        if (!val) return '—';
        return `<span class="status status-${val}">${val.replace('_', ' ')}</span>`;
    }

    function occBadge(val) {
        if (!val) return '—';
        return `<span class="status occ-${val}">${val}</span>`;
    }

    // ─── Table Builder ──────────────────────────────────────────────────
    function populateTable(tableId, rows, columns) {
        const tbody = document.querySelector(`#${tableId} tbody`);
        if (!rows || rows.length === 0) {
            tbody.innerHTML = `<tr><td colspan="${columns.length}" style="text-align:center;color:var(--text-muted);padding:30px;">No data found</td></tr>`;
            return;
        }
        tbody.innerHTML = rows.map(row =>
            '<tr>' + columns.map(col => `<td>${col.render ? col.render(row) : (row[col.key] ?? '—')}</td>`).join('') + '</tr>'
        ).join('');
    }

    // ─── Tab System ─────────────────────────────────────────────────────
    function initTabs() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(`panel-${tab}`).classList.add('active');
                state.currentTab = tab;
                loadTabData(tab);
            });
        });
    }

    function loadTabData(tab) {
        switch (tab) {
            case 'dashboard': loadDashboard(); break;
            case 'patients': loadPatients(); break;
            case 'doctors': loadDoctors(); break;
            case 'appointments': loadAppointments(); break;
            case 'rooms': loadRooms(); break;
            case 'billing': loadBilling(); break;
            case 'reports': loadReports(); break;
            case 'er-diagram': initMermaid(); break;
            case 'performance': loadPerformanceQueries(); break;
        }
    }

    // ─── Dashboard ──────────────────────────────────────────────────────
    async function loadDashboard() {
        try {
            const stats = await api('/api/admin/dashboard');

            const cards = [
                { icon: '🧑‍🤝‍🧑', value: formatNumber(stats.total_patients), label: 'Total Patients', color: 'blue' },
                { icon: '🩺', value: formatNumber(stats.total_doctors), label: 'Doctors / Consultants', color: 'purple' },
                { icon: '📅', value: formatNumber(stats.appointments_today), label: "Today's OPD Appts", color: 'amber' },
                { icon: '📋', value: formatNumber(stats.total_appointments), label: 'Total OPD Appts', color: 'cyan' },
                { icon: '💳', value: formatNumber(stats.pending_bills), label: 'Pending Claims', color: 'red' },
                { icon: '💰', value: formatCurrencyCompact(stats.total_revenue), label: 'Total Billed (₹)', color: 'green' },
                { icon: '🛏️', value: `${stats.beds_occupied}/${stats.beds_total}`, label: 'Beds Occupied', color: 'amber' },
                { icon: '📊', value: stats.beds_total > 0 ? Math.round(stats.beds_occupied / stats.beds_total * 100) + '%' : '0%', label: 'Bed Occupancy %', color: 'purple' },
            ];

            document.getElementById('dashboard-cards').innerHTML = cards.map(c => `
                <div class="stat-card ${c.color}">
                    <div class="card-icon">${c.icon}</div>
                    <div class="card-value">${c.value}</div>
                    <div class="card-label">${c.label}</div>
                </div>
            `).join('');

            // Update header stats
            document.getElementById('hdr-patients').textContent = formatNumber(stats.total_patients);
            document.getElementById('hdr-doctors').textContent = formatNumber(stats.total_doctors);
            document.getElementById('hdr-appointments').textContent = formatNumber(stats.total_appointments);
            document.getElementById('hdr-revenue').textContent = formatCurrencyCompact(stats.total_revenue);

            // Load department stats from materialized view
            const deptStats = await api('/api/admin/views/department-stats');
            populateTable('table-dept-stats', deptStats, [
                { key: 'department_name' },
                { key: 'building' },
                { key: 'total_doctors', render: r => formatNumber(r.total_doctors) },
                { key: 'active_doctors', render: r => formatNumber(r.active_doctors) },
                { key: 'total_rooms', render: r => formatNumber(r.total_rooms) },
                { key: 'total_beds', render: r => formatNumber(r.total_beds) },
                { key: 'occupied_beds', render: r => formatNumber(r.occupied_beds) },
                { key: 'appointments_last_30d', render: r => formatNumber(r.appointments_last_30d) },
                { key: 'revenue_last_30d', render: r => formatCurrency(r.revenue_last_30d) },
            ]);

            // Set header for dept stats table
            const thead = document.querySelector('#table-dept-stats thead tr');
            thead.innerHTML = '<th>Department</th><th>Building</th><th>Doctors</th><th>Active</th><th>Rooms</th><th>Beds</th><th>Occupied</th><th>Appts (30d)</th><th>Revenue (30d)</th>';

        } catch (e) {
            console.error('Dashboard load failed:', e);
        }
    }

    // ─── Patients ───────────────────────────────────────────────────────
    async function loadPatients() {
        const p = state.pagination.patients;
        const search = document.getElementById('patient-search')?.value || '';
        const params = new URLSearchParams({ limit: p.limit, offset: p.offset });
        if (search) params.set('search', search);

        const rows = await api(`/api/patients?${params}`);
        const count = await api('/api/patients/count');
        document.getElementById('patients-count').textContent = formatNumber(count.count);

        populateTable('table-patients', rows, [
            { key: 'patient_id', render: r => `<span class="cell-id">#${r.patient_id}</span>` },
            { key: 'name', render: r => `${r.first_name} ${r.last_name}` },
            { key: 'date_of_birth', render: r => formatDate(r.date_of_birth) },
            { key: 'gender' },
            { key: 'email', render: r => r.email || '—' },
            { key: 'phone', render: r => r.phone || '—' },
            { key: 'blood_group', render: r => r.blood_group || '—' },
            { key: 'registered_at', render: r => formatDate(r.registered_at) },
        ]);

        renderPagination('patients', p.offset, p.limit, count.count);
    }

    async function submitPatient() {
        const form = document.getElementById('form-patient');
        const data = Object.fromEntries(new FormData(form));
        await api('/api/patients', { method: 'POST', body: JSON.stringify(data) });
        toast('Patient registered successfully', 'success');
        form.reset();
        loadPatients();
    }

    // ─── Doctors ────────────────────────────────────────────────────────
    async function loadDoctors() {
        const p = state.pagination.doctors;
        const rows = await api(`/api/doctors?limit=${p.limit}&offset=${p.offset}`);
        const count = await api('/api/doctors/count');
        document.getElementById('doctors-count').textContent = formatNumber(count.count);

        // Load departments for the form select
        const depts = await api('/api/departments');
        const select = document.getElementById('doc-dept-select');
        select.innerHTML = depts.map(d => `<option value="${d.department_id}">${d.name}</option>`).join('');

        populateTable('table-doctors', rows, [
            { key: 'doctor_id', render: r => `<span class="cell-id">#${r.doctor_id}</span>` },
            { key: 'name', render: r => `Dr. ${r.first_name} ${r.last_name}` },
            { key: 'specialization' },
            { key: 'department_name' },
            { key: 'availability_status', render: r => statusBadge(r.availability_status) },
            { key: 'email' },
            { key: 'hire_date', render: r => formatDate(r.hire_date) },
        ]);

        renderPagination('doctors', p.offset, p.limit, count.count);
    }

    async function submitDoctor() {
        const form = document.getElementById('form-doctor');
        const data = Object.fromEntries(new FormData(form));
        data.department_id = parseInt(data.department_id);
        await api('/api/doctors', { method: 'POST', body: JSON.stringify(data) });
        toast('Doctor added successfully', 'success');
        form.reset();
        loadDoctors();
    }

    // ─── Appointments ───────────────────────────────────────────────────
    async function loadAppointments() {
        const p = state.pagination.appointments;
        const rows = await api(`/api/appointments?limit=${p.limit}&offset=${p.offset}`);
        const count = await api('/api/appointments/count');
        document.getElementById('appointments-count').textContent = formatNumber(count.count);

        populateTable('table-appointments', rows, [
            { key: 'appointment_id', render: r => `<span class="cell-id">#${r.appointment_id}</span>` },
            { key: 'patient_name' },
            { key: 'doctor_name', render: r => `Dr. ${r.doctor_name}` },
            { key: 'specialization' },
            { key: 'appointment_datetime', render: r => formatDateTime(r.appointment_datetime) },
            { key: 'duration_minutes', render: r => `<span class="cell-mono">${r.duration_minutes} min</span>` },
            { key: 'status', render: r => statusBadge(r.status) },
            { key: 'reason', render: r => r.reason || '—' },
        ]);

        renderPagination('appointments', p.offset, p.limit, count.count);
    }

    async function bookAppointment() {
        const form = document.getElementById('form-appointment');
        const data = Object.fromEntries(new FormData(form));
        data.patient_id = parseInt(data.patient_id);
        data.doctor_id = parseInt(data.doctor_id);
        data.duration_minutes = parseInt(data.duration_minutes);

        const result = await api('/api/appointments/book', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        toast(result.status_message, 'success');
        form.reset();
        loadAppointments();
    }

    async function bookAppointmentRaw() {
        const form = document.getElementById('form-appointment');
        const data = Object.fromEntries(new FormData(form));
        data.patient_id = parseInt(data.patient_id);
        data.doctor_id = parseInt(data.doctor_id);
        data.duration_minutes = parseInt(data.duration_minutes);

        const result = await api('/api/appointments/book/raw', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        toast(result.status_message, 'success');
        form.reset();
        loadAppointments();
    }

    // ─── Rooms ──────────────────────────────────────────────────────────
    async function loadRooms() {
        const rows = await api('/api/rooms/occupancy');
        populateTable('table-rooms', rows, [
            { key: 'room_number', render: r => `<span class="cell-mono">${r.room_number}</span>` },
            { key: 'department_name' },
            { key: 'room_type' },
            { key: 'total_beds', render: r => `<span class="cell-mono">${r.total_beds}</span>` },
            { key: 'occupied_beds', render: r => `<span class="cell-mono">${r.occupied_beds}</span>` },
            { key: 'available_beds', render: r => `<span class="cell-mono">${r.available_beds}</span>` },
            { key: 'occupancy_rate_pct', render: r => `<span class="cell-mono">${r.occupancy_rate_pct}%</span>` },
            { key: 'occupancy_level', render: r => occBadge(r.occupancy_level) },
            { key: 'daily_rate', render: r => formatCurrency(r.daily_rate) },
        ]);
    }

    async function admitPatient() {
        const form = document.getElementById('form-admit');
        const data = Object.fromEntries(new FormData(form));
        data.patient_id = parseInt(data.patient_id);
        data.room_id = parseInt(data.room_id);
        data.doctor_id = parseInt(data.doctor_id);

        const result = await api('/api/rooms/admit', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        toast(result.status_message, 'success');
        form.reset();
        loadRooms();
    }

    function dischargePrompt() {
        const patientId = prompt('Enter Patient ID to discharge:');
        const roomId = prompt('Enter Room ID:');
        if (patientId && roomId) {
            api('/api/rooms/discharge', {
                method: 'POST',
                body: JSON.stringify({
                    patient_id: parseInt(patientId),
                    room_id: parseInt(roomId),
                }),
            }).then(result => {
                toast(result.status_message, 'success');
                loadRooms();
            });
        }
    }

    // ─── Billing ────────────────────────────────────────────────────────
    async function loadBilling() {
        const p = state.pagination.billing;
        const rows = await api(`/api/billing?limit=${p.limit}&offset=${p.offset}`);
        const count = await api('/api/billing/count');
        document.getElementById('billing-count').textContent = formatNumber(count.count);

        populateTable('table-billing', rows, [
            { key: 'bill_id', render: r => `<span class="cell-id">#${r.bill_id}</span>` },
            { key: 'patient_name' },
            { key: 'total_amount', render: r => `<span class="cell-mono">${formatCurrency(r.total_amount)}</span>` },
            { key: 'paid_amount', render: r => `<span class="cell-mono">${formatCurrency(r.paid_amount)}</span>` },
            { key: 'outstanding', render: r => `<span class="cell-mono">${formatCurrency(r.total_amount - r.paid_amount)}</span>` },
            { key: 'payment_status', render: r => statusBadge(r.payment_status) },
            { key: 'payment_method', render: r => r.payment_method || '—' },
            { key: 'bill_date', render: r => formatDate(r.bill_date) },
        ]);

        renderPagination('billing', p.offset, p.limit, count.count);
    }

    async function makePayment() {
        const form = document.getElementById('form-payment');
        const data = Object.fromEntries(new FormData(form));
        data.bill_id = parseInt(data.bill_id);
        data.paid_amount = parseFloat(data.paid_amount);

        const result = await api('/api/billing/pay', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        toast(`Payment processed. Status: ${result.payment_status}`, 'success');
        form.reset();
        loadBilling();
    }

    // ─── Reports ────────────────────────────────────────────────────────
    async function loadReports() {
        const revenue = await api('/api/admin/views/revenue');
        populateTable('table-revenue', revenue, [
            { key: 'department_name' },
            { key: 'month', render: r => `<span class="cell-mono">${r.month}</span>` },
            { key: 'total_bills', render: r => formatNumber(r.total_bills) },
            { key: 'total_billed', render: r => formatCurrency(r.total_billed) },
            { key: 'total_collected', render: r => formatCurrency(r.total_collected) },
            { key: 'outstanding_amount', render: r => formatCurrency(r.outstanding_amount) },
            { key: 'collection_rate_pct', render: r => `<span class="cell-mono">${r.collection_rate_pct}%</span>` },
        ]);

        const doctorLoad = await api('/api/admin/views/doctor-load');
        populateTable('table-doctor-load', doctorLoad, [
            { key: 'doctor_name', render: r => `Dr. ${r.doctor_name}` },
            { key: 'specialization' },
            { key: 'department_name' },
            { key: 'availability_status', render: r => statusBadge(r.availability_status) },
            { key: 'upcoming_appointments', render: r => formatNumber(r.upcoming_appointments) },
            { key: 'completed_appointments', render: r => formatNumber(r.completed_appointments) },
            { key: 'cancelled_appointments', render: r => formatNumber(r.cancelled_appointments) },
            { key: 'total_appointments', render: r => formatNumber(r.total_appointments) },
            { key: 'avg_duration_minutes', render: r => r.avg_duration_minutes ? `${r.avg_duration_minutes} min` : '—' },
        ]);
    }

    // ─── ER Diagram (Mermaid.js) ────────────────────────────────────────
    let mermaidInitialized = false;
    const erDiagramCode = `erDiagram
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
        string name
        string building
        int floor_number
        string phone_extension
        string created_at
    }
    DOCTORS {
        int doctor_id PK
        string first_name
        string last_name
        string email
        string phone
        string specialization
        int department_id FK
        string availability_status
        string hire_date
    }
    PATIENTS {
        int patient_id PK
        string first_name
        string last_name
        string date_of_birth
        string gender
        string email
        string phone
        string address
        string blood_group
        string emergency_contact_name
        string emergency_contact_phone
        string registered_at
    }
    ROOMS {
        int room_id PK
        string room_number
        int department_id FK
        string room_type
        int total_beds
        int occupied_beds
        float daily_rate
    }
    APPOINTMENTS {
        int appointment_id PK
        int patient_id FK
        int doctor_id FK
        string appointment_datetime
        int duration_minutes
        string status
        string reason
        string created_at
    }
    MEDICAL_RECORDS {
        int record_id PK
        int patient_id FK
        int doctor_id FK
        int appointment_id FK
        string diagnosis
        string prescription
        string notes
        string created_at
    }
    BILLING {
        int bill_id PK
        int patient_id FK
        int appointment_id FK
        float total_amount
        float paid_amount
        string payment_status
        string payment_method
        string bill_date
        string paid_date
    }
    PATIENT_AUDIT_LOG {
        int log_id PK
        int patient_id FK
        int room_id FK
        string action
        string details
        string logged_at
    }`;

    async function initMermaid() {
        if (mermaidInitialized) return;
        const container = document.getElementById('er-diagram-container');
        if (!container) return;

        if (typeof mermaid === 'undefined') {
            container.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>Mermaid.js library loading... Please refresh.</p></div>';
            return;
        }

        try {
            mermaid.initialize({
                startOnLoad: false,
                theme: 'dark',
            });
            const { svg } = await mermaid.render('er-diagram-rendered-svg', erDiagramCode);
            container.innerHTML = svg;
            mermaidInitialized = true;
        } catch (err) {
            console.error('Mermaid render error:', err);
            container.innerHTML = `<div class="empty-state"><div class="icon">❌</div><p>Mermaid Render Error: ${err.message || err}</p></div>`;
        }
    }

    // ─── Performance (EXPLAIN ANALYZE) ──────────────────────────────────
    async function loadPerformanceQueries() {
        const queries = await api('/api/admin/explain');
        const sidebar = document.getElementById('perf-query-list');
        const keys = Object.keys(queries);

        sidebar.innerHTML = Object.entries(queries).map(([key, q]) => `
            <button class="perf-query-btn" data-key="${key}" onclick="HMS.runExplain('${key}')">
                <strong>${q.title}</strong><br>
                <small style="color:var(--text-muted)">${q.description.substring(0, 80)}...</small>
            </button>
        `).join('');

        // Auto-run the first query so results show immediately
        if (keys.length > 0) {
            runExplain(keys[0]);
        }
    }

    async function runExplain(queryKey) {
        // Highlight active button
        document.querySelectorAll('.perf-query-btn').forEach(b => b.classList.remove('active'));
        document.querySelector(`.perf-query-btn[data-key="${queryKey}"]`)?.classList.add('active');

        const content = document.getElementById('perf-result');
        content.innerHTML = '<div class="loading"><span class="spinner"></span> Running EXPLAIN ANALYZE...</div>';

        try {
            const result = await api(`/api/admin/explain/${queryKey}`);

            // Highlight plan nodes
            const planHtml = result.explain_analyze.map(line => {
                let styled = line
                    .replace(/(Index Scan|Index Only Scan|Bitmap Index Scan|Bitmap Heap Scan)/g, '<span class="node-index">$1</span>')
                    .replace(/(Seq Scan)/g, '<span class="node-seq">$1</span>')
                    .replace(/(actual time=[\d.]+\.\.[\d.]+)/g, '<span class="node-time">$1</span>')
                    .replace(/(Execution Time: [\d.]+ ms)/g, '<span class="node-time">$1</span>')
                    .replace(/(Planning Time: [\d.]+ ms)/g, '<span class="node-time">$1</span>');
                return styled;
            }).join('\n');

            content.innerHTML = `
                <div class="perf-section-title">Query — ${result.title}</div>
                <p style="font-size:12px;color:var(--text-secondary);margin-bottom:12px">${result.description}</p>
                
                <div class="perf-section-title">SQL</div>
                <div class="sql-block">${result.sql}</div>
                
                <div class="perf-section-title">EXPLAIN ANALYZE Output</div>
                <div class="plan-block">${planHtml}</div>
                
                <div class="perf-section-title">Result Summary</div>
                <p style="font-size:13px;color:var(--text-primary)">
                    Rows returned: <span class="cell-mono">${result.result_count}</span>
                </p>
                ${result.sample_results.length > 0 ? `
                    <div style="margin-top:12px">
                        <div class="perf-section-title">Sample Results (first 5)</div>
                        <div class="sql-block" style="color:var(--text-primary);font-size:11px">${JSON.stringify(result.sample_results, null, 2)}</div>
                    </div>
                ` : ''}
            `;
        } catch (e) {
            content.innerHTML = `<div class="empty-state"><div class="icon">❌</div><p>${e.message}</p></div>`;
        }
    }

    // ─── Materialized View Refresh ──────────────────────────────────────
    async function refreshMaterialized() {
        toast('Refreshing materialized view...', 'info');
        await api('/api/admin/views/refresh-materialized', { method: 'POST' });
        toast('Materialized view refreshed', 'success');
        loadDashboard();
    }

    // ─── Pagination ─────────────────────────────────────────────────────
    function renderPagination(entity, offset, limit, total) {
        const container = document.getElementById(`pagination-${entity}`);
        if (!container) return;

        const currentPage = Math.floor(offset / limit) + 1;
        const totalPages = Math.ceil(total / limit);

        if (totalPages <= 1) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = `
            <button class="btn btn-secondary btn-sm" ${currentPage <= 1 ? 'disabled' : ''} 
                    onclick="HMS.paginate('${entity}', ${offset - limit})">‹ Prev</button>
            <span class="page-info">Page ${currentPage} of ${totalPages}</span>
            <button class="btn btn-secondary btn-sm" ${currentPage >= totalPages ? 'disabled' : ''} 
                    onclick="HMS.paginate('${entity}', ${offset + limit})">Next ›</button>
        `;
    }

    function paginate(entity, newOffset) {
        state.pagination[entity].offset = Math.max(0, newOffset);
        loadTabData(entity);
    }

    // ─── Patient Search ─────────────────────────────────────────────────
    function initSearch() {
        const searchInput = document.getElementById('patient-search');
        if (searchInput) {
            let timeout;
            searchInput.addEventListener('input', () => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    state.pagination.patients.offset = 0;
                    loadPatients();
                }, 300);
            });
        }
    }

    // ─── Init ───────────────────────────────────────────────────────────
    function init() {
        initTabs();
        initSearch();
        loadDashboard();
    }

    document.addEventListener('DOMContentLoaded', init);

    // ─── Public API ─────────────────────────────────────────────────────
    return {
        submitPatient,
        submitDoctor,
        bookAppointment,
        bookAppointmentRaw,
        admitPatient,
        dischargePrompt,
        makePayment,
        refreshMaterialized,
        runExplain,
        paginate,
    };
})();
