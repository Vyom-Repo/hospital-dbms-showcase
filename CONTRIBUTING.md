# Contributing to Hospital DBMS Showcase

Thank you for your interest in contributing to **Hospital DBMS Showcase**!

This project demonstrates advanced PostgreSQL techniques, raw SQL queries, and high-performance concurrency control with FastAPI.

---

## 🛠️ Code Style Guidelines

- **Python**: Follow PEP 8 guidelines. Format code with `black` and check imports with `isort`.
- **SQL**: Write standard, clean uppercase SQL keywords (`SELECT`, `INSERT`, `UPDATE`, `JOIN`).
- **Frontend**: Maintain vanilla HTML, CSS variables, and modern JavaScript without heavy framework dependencies.

---

## 🌿 Branch Naming

Use descriptive branch names:
- `feature/add-indexing-benchmark`
- `fix/concurrency-deadlock-prevention`
- `docs/update-explain-analyze-guide`

---

## 🔄 Contribution Workflow

1. **Fork the Repository**: Create your personal fork on GitHub.
2. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Commit Changes**: Use semantic commit messages:
   - `feat: add partial index for room occupancy`
   - `fix: correct transaction rollback in fn_admit_patient`
   - `docs: update architecture diagram in README`
4. **Push and Create Pull Request**: Submit your PR targeting the `main` branch.

---

## 📋 Reporting Issues

- Search existing issues before creating a new one.
- Provide step-by-step reproduction steps, environment details (OS, PostgreSQL version, Python version), and log tracebacks.
