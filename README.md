# Attendify: Student Attendance Management System with Face Recognition

Attendify is a modern, web-based attendance management system that uses face recognition to automate the process for students and teachers.

## Features

- **Admin Control**: Manage students, teachers, courses, and subjects.
- **Smart Attendance**: One-click face recognition via webcam to mark students as present.
- **Manual Attendance**: Fail-safe manual marking for sessions.
- **Reports**: Generate detailed attendance reports and export to CSV.
- **Student Portal**: Students can view their attendance percentage and logs.

## Technology Stack

- **Frontend**: HTML, CSS (Modern dark/glass theme), Vanilla JavaScript.
- **Backend**: Python (Flask REST API).
- **Face Recognition**: OpenCV and `face_recognition` (dlib-based).
- **Database**: MySQL.

## Setup Instructions

### 1. Database Setup
1. Create a MySQL database (e.g., `attendance_db`).
2. Run the SQL schema provided in the `implementation_plan.md` or let the backend initialize it automatically on first run.

### 2. Backend Setup
1. Navigate to the `backend/` directory.
2. Create a `.env` file from `.env.example` and fill in your DB credentials and a `SECRET_KEY`.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the API:
   ```bash
   python app.py
   ```

### 3. Frontend Setup
1. Open `frontend/assets/js/api.js` and update `API_BASE_URL` if your backend is running on a different port/URL.
2. Use a local server (like VS Code Live Server) to open `frontend/index.html`.

## Deployment

### Frontend (Vercel)
1. Push the `frontend/` folder to a GitHub repository.
2. Link the repository to Vercel.
3. Use the provided `vercel.json` to proxy API requests to your hosted backend.

### Backend (Render/Railway)
1. Push the `backend/` folder to GitHub.
2. Create a new Web Service on Render and link the repository.
3. Add your environment variables in the Render/Railway dashboard.
4. Set the build command to `pip install -r requirements.txt` and start command to `gunicorn app:app`.

## Default Admin Credentials
- **Username**: `admin`
- **Password**: `admin123`
