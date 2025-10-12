import sqlite3
import json
import bcrypt

DATABASE_NAME = 'chatbot_memory.db'

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
            password TEXT NOT NULL,
            profile TEXT
        )
    ''')
    # --- NEW: Create feedback table ---
    conn.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            rating INTEGER NOT NULL, -- 1 for up, -1 for down
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# --- NEW: Function to add feedback to the database ---
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

# --- (All other functions are the same) ---
def register_user(username, password):
    # ... (same as before)
    conn = get_db_connection()
    if conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
        conn.close()
        return False
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
    conn.commit()
    conn.close()
    return True

def check_user(username, password):
    # ... (same as before)
    conn = get_db_connection()
    user = conn.execute('SELECT password FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return True
    return False

def save_profile(username, profile_data):
    # ... (same as before)
    conn = get_db_connection()
    conn.execute('UPDATE users SET profile = ? WHERE username = ?', (json.dumps(profile_data), username))
    conn.commit()
    conn.close()

def load_profile(username):
    # ... (same as before)
    conn = get_db_connection()
    user = conn.execute('SELECT profile FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if user and user['profile']:
        return json.loads(user['profile'])
    return None