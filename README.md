"# code-quest-back" 
Here is a clear, step-by-step guide formatted in Markdown. You can copy this directly into your `README.md` file or keep it as a personal reference.

# Project Setup Guide

This project uses **uv**, a fast Python package and project manager. It replaces the traditional `pip` and `requirements.txt` workflow with a more automated, `npm`-like experience.

---

## 🛠 Prerequisites

Before running the project, you need to install the following tools:

1. **Git**: To clone the repository.
2. **uv**: The project manager. Run this command in your PowerShell (Windows):
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

```


*Note: After installing `uv`, restart your terminal or VS Code.*

---

## 🚀 Step-by-Step Setup

Follow these steps to get the project running on a new machine:

### 1. Clone the Repository

```bash
git clone <https://github.com/yamanecode/code-quest-back>
cd code-quest-back

```

### 2. Sync the Environment

This single command creates a virtual environment (`.venv`), downloads the correct Python version, and installs all exact dependencies from `uv.lock`.

```bash
uv sync

```

### 3. Setup Environment Variables

If you have a `.env` file for your database credentials or API keys, ensure it is created in the root directory.

* *Note: Do not commit your actual `.env` file to Git.*

### 4. Run Database Migrations

Since we use **SQLAlchemy** and **Alembic**, you need to update your local database to the latest schema:

```bash
uv run alembic upgrade head

```

### 5. Start the Application

To start the FastAPI server (or your main script):

```bash
uv run uvicorn main:app --reload

```

---

## 🏗 Development Workflow

If you need to make changes to the project structure:

* **Adding a new package**: Instead of `pip install`, use:
```bash
uv add <package-name>

```


*(This automatically updates `pyproject.toml` and `uv.lock`)*
* **Database Changes**:
1. Modify your SQLAlchemy models in Python.
2. Generate a migration script:
```bash
uv run alembic revision --autogenerate -m "description of change"

```


3. Apply the change:
```bash
uv run alembic upgrade head

```





---

## 📂 Important Files

* `pyproject.toml`: The project manifest (Like `package.json`).
* `uv.lock`: The exact version lockfile (Like `package-lock.json`).
* `alembic.ini`: Configuration for database migrations.
* `.python-version`: Tells `uv` exactly which version of Python to use.

