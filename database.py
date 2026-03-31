import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'attendance_db'),
            port=int(os.getenv('DB_PORT', 3306))
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def init_db():
    conn = get_db_connection()
    if conn is None:
        print("Could not connect to database during initialization.")
        return
    
    cursor = conn.cursor()
    
    # Create tables based on the schema
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        role ENUM('admin', 'teacher', 'student') NOT NULL,
        full_name VARCHAR(100) NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INT AUTO_INCREMENT PRIMARY KEY,
        course_name VARCHAR(100) UNIQUE NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INT AUTO_INCREMENT PRIMARY KEY,
        subject_name VARCHAR(100) NOT NULL,
        course_id INT NOT NULL,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        course_id INT NOT NULL,
        face_encoding LONGTEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL,
        subject_id INT NOT NULL,
        teacher_id INT NOT NULL,
        date DATE NOT NULL,
        status ENUM('Present', 'Absent') NOT NULL,
        method ENUM('Manual', 'FaceRecognition') DEFAULT 'Manual',
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
        FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    
    # Check if admin user exists, if not create default
    cursor.execute("SELECT * FROM users WHERE role = 'admin'")
    if not cursor.fetchone():
        # password is 'admin123' - in production this should be hashed
        import bcrypt
        hashed = bcrypt.hashpw('admin123'.encode('utf8'), bcrypt.gensalt()).decode('utf8')
        cursor.execute("INSERT INTO users (username, password, email, role, full_name) VALUES (%s, %s, %s, %s, %s)",
                       ('admin', hashed, 'admin@example.com', 'admin', 'Default Admin'))
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
