# backend/database.py
import sqlite3
import json
import bcrypt

DATABASE_NAME = '/tmp/chatbot_memory.db' # Deployment-ready path

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Create users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Create profiles table, linked to users
    conn.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            username TEXT PRIMARY KEY,
            gre_score INTEGER,
            toefl_score INTEGER,
            sop TEXT,
            lor TEXT,
            cgpa REAL,
            research INTEGER,
            FOREIGN KEY (username) REFERENCES users (username)
        )
    ''')
    # Create feedback table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            rating INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users (username)
        )
    ''')
    conn.commit()
    conn.close()

def add_feedback(username, question, answer, rating):
    try:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO feedback (username, question, answer, rating) VALUES (?, ?, ?, ?)',
            (username, question, answer, rating)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

def register_user(username, password):
    conn = get_db_connection()
    try:
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Username already exists
    finally:
        conn.close()

def check_user(username, password):
    conn = get_db_connection()
    user = conn.execute('SELECT password FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return True
    return False

def save_profile(username, profile_data):
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT OR REPLACE INTO profiles (username, gre_score, toefl_score, sop, lor, cgpa, research)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            username,
            profile_data.get('gre_score'),
            profile_data.get('toefl_score'),
            profile_data.get('sop'),
            profile_data.get('lor'),
            profile_data.get('cgpa'),
            profile_data.get('research')
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving profile: {e}")
        return False
    finally:
        conn.close()

def load_profile(username):
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM profiles WHERE username = ?', (username,)).fetchone()
    conn.close()
    if profile:
        return dict(profile) # Convert the sqlite3.Row object to a dict
    return None