from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import bcrypt
import jwt
import datetime
import os
import json
from functools import wraps
from database import get_db_connection, init_db
from face_utils import get_face_encodings, compare_faces
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_jwt_secret_key_123')

# JWT Authentication Decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            # In a real app, query user from DB to ensure they still exist
            current_user = data
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# ----------------- Auth Endpoints -----------------

@app.route('/api/login', methods=['POST'])
def login():
    auth = request.json
    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'message': 'Missing credentials'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (auth['username'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user and bcrypt.checkpw(auth['password'].encode('utf8'), user['password'].encode('utf8')):
        token = jwt.encode({
            'user_id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            'token': token,
            'role': user['role'],
            'full_name': user['full_name'],
            'user_id': user['id']
        })
    
    return jsonify({'message': 'Invalid username or password'}), 401

# ----------------- Student Management -----------------

@app.route('/api/students', methods=['GET'])
@token_required
def get_students(current_user):
    # Only admin and teachers can list students
    if current_user['role'] not in ['admin', 'teacher']:
        return jsonify({'message': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Join with user and course info
    query = """
        SELECT s.id, u.username, u.email, u.full_name, c.course_name, s.course_id, s.face_encoding IS NOT NULL as face_registered
        FROM students s
        JOIN users u ON s.user_id = u.id
        JOIN courses c ON s.course_id = c.id
    """
    cursor.execute(query)
    students = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(students)

@app.route('/api/students', methods=['POST'])
@token_required
def register_student(current_user):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.json # username, password, email, full_name, course_id
    hashed_pw = bcrypt.hashpw(data['password'].encode('utf8'), bcrypt.gensalt()).decode('utf8')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Create user record
        cursor.execute("INSERT INTO users (username, password, email, role, full_name) VALUES (%s, %s, %s, %s, %s)",
                       (data['username'], hashed_pw, data['email'], 'student', data['full_name']))
        user_id = cursor.lastrowid
        
        # Create student record
        cursor.execute("INSERT INTO students (user_id, course_id) VALUES (%s, %s)", (user_id, data['course_id']))
        
        conn.commit()
        return jsonify({'message': 'Student registered successfully', 'id': cursor.lastrowid}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# ----------------- Face Data Registration -----------------

@app.route('/api/students/<int:student_id>/register-face', methods=['POST'])
@token_required
def register_face(current_user, student_id):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.json # image (base64)
    if 'image' not in data:
        return jsonify({'message': 'No image provided'}), 400
    
    encoding = get_face_encodings(data['image'])
    if not encoding:
        return jsonify({'message': 'No face detected in image'}), 400
    
    encoding_json = json.dumps(encoding)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE students SET face_encoding = %s WHERE id = %s", (encoding_json, student_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'message': 'Face registered successfully'})

# ----------------- Attendance Logic -----------------

@app.route('/api/attendance/manual', methods=['POST'])
@token_required
def mark_attendance_manual(current_user):
    if current_user['role'] not in ['admin', 'teacher']:
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.json # student_id, subject_id, date, status, teacher_id
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if attendance already exists for this day/student/subject
    cursor.execute("SELECT id FROM attendance WHERE student_id = %s AND subject_id = %s AND date = %s",
                   (data['student_id'], data['subject_id'], data['date']))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute("UPDATE attendance SET status = %s WHERE id = %s", (data['status'], existing[0]))
    else:
        cursor.execute("INSERT INTO attendance (student_id, subject_id, teacher_id, date, status, method) VALUES (%s, %s, %s, %s, %s, %s)",
                       (data['student_id'], data['subject_id'], current_user['user_id'], data['date'], data['status'], 'Manual'))
    
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Attendance marked successfully'})

@app.route('/api/attendance/face-recognition', methods=['POST'])
@token_required
def mark_attendance_face_recognition(current_user):
    if current_user['role'] not in ['admin', 'teacher']:
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.json # image (base64), subject_id, date
    frame_image = data.get('image')
    
    # Get all students with registered faces for the course associated with this subject
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get course_id for the subject
    cursor.execute("SELECT course_id FROM subjects WHERE id = %s", (data['subject_id'],))
    subject = cursor.fetchone()
    if not subject:
        return jsonify({'message': 'Subject not found'}), 404
    
    # Get known encodings for students in that course
    cursor.execute("SELECT id, face_encoding FROM students WHERE course_id = %s AND face_encoding IS NOT NULL", (subject['course_id'],))
    known_students = cursor.fetchall()
    
    known_encodings = {}
    for ks in known_students:
        known_encodings[ks['id']] = json.loads(ks['face_encoding'])
    
    if not known_encodings:
        return jsonify({'message': 'No registered face data for this course'}), 400
    
    # Compare faces
    recognized_ids = compare_faces(known_encodings, frame_image)
    
    # Mark recognized students as present
    marked_count = 0
    for sid in recognized_ids:
        # Check if already present
        cursor.execute("SELECT id FROM attendance WHERE student_id = %s AND subject_id = %s AND date = %s",
                       (sid, data['subject_id'], data['date']))
        existing = cursor.fetchone()
        
        if not existing:
            cursor.execute("INSERT INTO attendance (student_id, subject_id, teacher_id, date, status, method) VALUES (%s, %s, %s, %s, %s, %s)",
                           (sid, data['subject_id'], current_user['user_id'], data['date'], 'Present', 'FaceRecognition'))
            marked_count += 1
            
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({
        'recognized_ids': recognized_ids,
        'marked_present_count': marked_count
    })

# ----------------- Course & Subject Endpoints -----------------

@app.route('/api/courses', methods=['GET'])
@token_required
def get_courses(current_user):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM courses")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)

@app.route('/api/courses', methods=['POST'])
@token_required
def create_course(current_user):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO courses (course_name) VALUES (%s)", (data['course_name'],))
        conn.commit()
        return jsonify({'message': 'Course created', 'id': cursor.lastrowid}), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/api/subjects', methods=['GET'])
@token_required
def get_subjects(current_user):
    course_id = request.args.get('course_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if course_id:
        cursor.execute("SELECT * FROM subjects WHERE course_id = %s", (course_id,))
    else:
        cursor.execute("SELECT s.*, c.course_name FROM subjects s JOIN courses c ON s.course_id = c.id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)

@app.route('/api/subjects', methods=['POST'])
@token_required
def create_subject(current_user):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO subjects (subject_name, course_id) VALUES (%s, %s)", 
                       (data['subject_name'], data['course_id']))
        conn.commit()
        return jsonify({'message': 'Subject created', 'id': cursor.lastrowid}), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# ----------------- Report Endpoints -----------------

@app.route('/api/reports/attendance', methods=['GET'])
@token_required
def get_attendance_report(current_user):
    subject_id = request.args.get('subject_id')
    date = request.args.get('date')
    student_id = request.args.get('student_id')
    
    # If student role, they can only see their own attendance
    if current_user['role'] == 'student':
        # Need to find their student_id
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM students WHERE user_id = %s", (current_user['user_id'],))
        std = cursor.fetchone()
        student_id = std['id']
    else:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

    query = """
        SELECT a.id, a.date, a.status, a.method, u.full_name as student_name, sub.subject_name
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        JOIN subjects sub ON a.subject_id = sub.id
        WHERE 1=1
    """
    params = []
    if subject_id:
        query += " AND a.subject_id = %s"
        params.append(subject_id)
    if date:
        query += " AND a.date = %s"
        params.append(date)
    if student_id:
        query += " AND a.student_id = %s"
        params.append(student_id)
        
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)

if __name__ == '__main__':
    # Initialize DB (create tables)
    init_db()
    app.run(debug=True, port=int(os.getenv('PORT', 5000)))
