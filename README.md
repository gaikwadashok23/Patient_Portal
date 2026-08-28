# Patient Portal Web App

## Tech Stack

* Backend: Django + Django REST Framework
* Database: SQLite
* Frontend: React + Vite

## Prerequisites

* Python 3.12.14
* Node.js v24.15.0

---

## 1. Clone Repository

```bash
git clone https://github.com/gaikwadashok23/Patient_Portal.git
cd patient-portal
```

## 2. Backend Setup

```bash
cd backend

python -m venv venv
```

### Windows

```bash
conda activate portal_env
```

### macOS/Linux

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run migrations:

```bash
python manage.py migrate
```

Start Django server:

```bash
python manage.py runserver
```

Backend will run at:

```text
http://127.0.0.1:8000/
```

---

## 3. Frontend Setup

Open a **new terminal**:

```bash
cd frontend
npm install
npm run dev
```

Frontend will run at:

```text
http://localhost:5173/
```

Open the frontend URL in your browser.

---

## 4. Run Tests

From the backend directory:

```bash
python manage.py test
```

---

