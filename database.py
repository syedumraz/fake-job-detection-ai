import sqlite3
import hashlib
from datetime import datetime

DB_NAME = 'job_detection.db'

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10.0)  # Add timeout to prevent locking
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_title TEXT NOT NULL,
            company_name TEXT NOT NULL,
            job_description TEXT NOT NULL,
            salary TEXT,
            location TEXT,
            prediction TEXT NOT NULL,
            confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            dark_mode INTEGER DEFAULT 0,
            compact_view INTEGER DEFAULT 0,
            email_notifications INTEGER DEFAULT 1,
            sms_notifications INTEGER DEFAULT 0,
            profile_public INTEGER DEFAULT 1,
            show_activity_status INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS csv_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS training_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            algorithm TEXT NOT NULL,
            accuracy REAL NOT NULL,
            precision REAL NOT NULL,
            recall REAL NOT NULL,
            f1_score REAL NOT NULL,
            training_samples INTEGER NOT NULL,
            features INTEGER NOT NULL,
            confusion_matrix TEXT NOT NULL,
            trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_otp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            phone TEXT,
            otp TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            device_token TEXT UNIQUE NOT NULL,
            device_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inbox_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            message_type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            otp TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users (username)
        )
    ''')

    conn.commit()
    conn.close()

def migrate_db():
    """Migrate database schema to add new columns if they don't exist"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if profile_public column exists in user_preferences
        cursor.execute("PRAGMA table_info(user_preferences)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'profile_public' not in columns:
            cursor.execute('ALTER TABLE user_preferences ADD COLUMN profile_public INTEGER DEFAULT 1')
        
        if 'show_activity_status' not in columns:
            cursor.execute('ALTER TABLE user_preferences ADD COLUMN show_activity_status INTEGER DEFAULT 1')

        # Add status column to users if it doesn't exist
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [column[1] for column in cursor.fetchall()]
        if 'status' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'Active'")
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database migration error (may be harmless): {e}")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, phone=None, email=None):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (username, password, phone, email) VALUES (?, ?, ?, ?)',
                      (username, hash_password(password), phone, email))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def user_exists(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return user is not None

def verify_user(username, password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                  (username, hash_password(password)))
    user = cursor.fetchone()
    conn.close()
    if user and dict(user).get('status', 'Active') == 'Inactive':
        return False
    return user is not None

def get_user_status(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    return result['status'] if result and result['status'] else 'Active'

def update_user_status(username, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET status = ? WHERE username = ?', (status, username))
    conn.commit()
    conn.close()
    return True

def get_user_id(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_user_email(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT email FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def save_job_detection(username, job_title, company_name, job_description, salary, location, prediction, confidence):
    user_id = get_user_id(username)
    if not user_id:
        return False
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO job_detections 
        (user_id, job_title, company_name, job_description, salary, location, prediction, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, job_title, company_name, job_description, salary, location, prediction, confidence))
    conn.commit()
    conn.close()
    return True

def get_user_detections(username, limit=10):
    user_id = get_user_id(username)
    if not user_id:
        return []
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM job_detections 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (user_id, limit))
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]

def get_user_profile(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, phone, created_at, status FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return None
    
    user_dict = dict(user)
    cursor.execute('SELECT COUNT(*) as total FROM job_detections WHERE user_id = ?', (user_dict['id'],))
    user_dict['total_detections'] = cursor.fetchone()[0]
    
    conn.close()
    return user_dict

def log_activity(username, activity_type, description):
    user_id = get_user_id(username)
    if not user_id:
        return False
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO user_activities (user_id, activity_type, description) VALUES (?, ?, ?)',
                  (user_id, activity_type, description))
    conn.commit()
    conn.close()
    return True

def get_user_activities(username, limit=4):
    user_id = get_user_id(username)
    if not user_id:
        return []
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT activity_type, description, created_at 
        FROM user_activities 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (user_id, limit))
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]

def get_user_preferences(username):
    user_id = get_user_id(username)
    if not user_id:
        return {'dark_mode': 0, 'compact_view': 0, 'email_notifications': 1, 'sms_notifications': 0, 'profile_public': 1, 'show_activity_status': 1}
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT dark_mode, compact_view, email_notifications, sms_notifications, profile_public, show_activity_status FROM user_preferences WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return dict(result)
    return {'dark_mode': 0, 'compact_view': 0, 'email_notifications': 1, 'sms_notifications': 0, 'profile_public': 1, 'show_activity_status': 1}

def save_user_preferences(username, dark_mode, compact_view, email_notifications=1, sms_notifications=0, profile_public=1, show_activity_status=1):
    user_id = get_user_id(username)
    if not user_id:
        return False
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_preferences (user_id, dark_mode, compact_view, email_notifications, sms_notifications, profile_public, show_activity_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, dark_mode, compact_view, email_notifications, sms_notifications, profile_public, show_activity_status))
    conn.commit()
    conn.close()
    return True

def update_username(old_username, new_username):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET username = ? WHERE username = ?', (new_username, old_username))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_password(username, new_password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET password = ? WHERE username = ?', (hash_password(new_password), username))
    conn.commit()
    conn.close()
    return True

def save_csv_upload(username, filename, original_filename):
    user_id = get_user_id(username)
    if not user_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO csv_uploads (user_id, filename, original_filename) VALUES (?, ?, ?)',
                  (user_id, filename, original_filename))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def get_user_csvs(username):
    user_id = get_user_id(username)
    if not user_id:
        return []
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, filename, original_filename, uploaded_at FROM csv_uploads WHERE user_id = ? ORDER BY uploaded_at DESC', (user_id,))
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]

def update_csv_filename(csv_id, new_filename):
    conn = get_db()
    conn.execute('UPDATE csv_uploads SET filename = ? WHERE id = ?', (new_filename, csv_id))
    conn.commit()
    conn.close()

def delete_csv_upload(csv_id, username):
    user_id = get_user_id(username)
    if not user_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT filename FROM csv_uploads WHERE id = ? AND user_id = ?', (csv_id, user_id))
    row = cursor.fetchone()
    if row:
        cursor.execute('DELETE FROM csv_uploads WHERE id = ?', (csv_id,))
        conn.commit()
    conn.close()
    return row['filename'] if row else None

def save_training_metrics(algorithm, accuracy, precision, recall, f1_score, training_samples, features, confusion_matrix):
    """Save training metrics to the database (global, not user-specific)"""
    import json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO training_metrics 
        (algorithm, accuracy, precision, recall, f1_score, training_samples, features, confusion_matrix)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (algorithm, accuracy, precision, recall, f1_score, training_samples, features, json.dumps(confusion_matrix)))
    conn.commit()
    conn.close()
    return True

def get_latest_training_metrics():
    """Get the latest training metrics"""
    import json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, algorithm, accuracy, precision, recall, f1_score, training_samples, features, confusion_matrix, trained_at
        FROM training_metrics
        ORDER BY trained_at DESC
        LIMIT 1
    ''')
    result = cursor.fetchone()
    conn.close()
    
    if result:
        row_dict = dict(result)
        row_dict['confusion_matrix'] = json.loads(row_dict['confusion_matrix'])
        return row_dict
    return None

def get_all_training_metrics(limit=10):
    """Get all training metrics"""
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, algorithm, accuracy, precision, recall, f1_score, training_samples, features, confusion_matrix, trained_at
            FROM training_metrics
            ORDER BY trained_at DESC
            LIMIT ?
        ''', (limit,))
        results = cursor.fetchall()
        conn.close()
        
        return [
            {**dict(row), 'confusion_matrix': json.loads(row['confusion_matrix'])}
            for row in results
        ]
    except Exception as e:
        print(f"Error getting training metrics: {e}")
        return []

def get_training_statistics():
    """Get overall training statistics"""
    import json
    conn = get_db()
    cursor = conn.cursor()
    
    # Get total training count
    cursor.execute('SELECT COUNT(*) as total_trainings FROM training_metrics')
    total = cursor.fetchone()['total_trainings']
    
    # Get average metrics
    cursor.execute('''
        SELECT 
            AVG(accuracy) as avg_accuracy,
            AVG(precision) as avg_precision,
            AVG(recall) as avg_recall,
            AVG(f1_score) as avg_f1,
            SUM(training_samples) as total_samples
        FROM training_metrics
    ''')
    stats = cursor.fetchone()
    
    # Get most used algorithm
    cursor.execute('''
        SELECT algorithm, COUNT(*) as count
        FROM training_metrics
        GROUP BY algorithm
        ORDER BY count DESC
        LIMIT 1
    ''')
    algo = cursor.fetchone()
    
    conn.close()
    
def get_training_statistics():
    """Get overall training statistics"""
    import json
    conn = get_db()
    cursor = conn.cursor()
    
    # Get total training count
    cursor.execute('SELECT COUNT(*) as total_trainings FROM training_metrics')
    total = cursor.fetchone()['total_trainings']
    
    # Get average metrics
    cursor.execute('''
        SELECT 
            AVG(accuracy) as avg_accuracy,
            AVG(precision) as avg_precision,
            AVG(recall) as avg_recall,
            AVG(f1_score) as avg_f1,
            SUM(training_samples) as total_samples
        FROM training_metrics
    ''')
    stats = cursor.fetchone()
    
    # Get most used algorithm
    cursor.execute('SELECT algorithm, COUNT(*) as count FROM training_metrics GROUP BY algorithm ORDER BY count DESC LIMIT 1')
    algo = cursor.fetchone()
    
    conn.close()
    
    return {
        'total_trainings': total,
        'avg_accuracy': round(stats['avg_accuracy'] * 100, 2) if stats['avg_accuracy'] else 0,
        'avg_precision': round(stats['avg_precision'] * 100, 2) if stats['avg_precision'] else 0,
        'avg_recall': round(stats['avg_recall'] * 100, 2) if stats['avg_recall'] else 0,
        'avg_f1': round(stats['avg_f1'] * 100, 2) if stats['avg_f1'] else 0,
        'total_samples': int(stats['total_samples']) if stats['total_samples'] else 0,
        'most_used_algorithm': algo['algorithm'] if algo else 'None'
    }

def save_contact_info(username, email, phone):
    """Save email and phone to user profile"""
    user_id = get_user_id(username)
    if not user_id:
        return False
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET email = ?, phone = ? WHERE id = ?', (email, phone, user_id))
    conn.commit()
    conn.close()
    return True

def get_contact_info(username):
    """Get email and phone from user profile"""
    user_id = get_user_id(username)
    if not user_id:
        return {'email': '', 'phone': ''}
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT email, phone FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {'email': result['email'] or '', 'phone': result['phone'] or ''}
    return {'email': '', 'phone': ''}

def send_notification(username, event_type, message, email_body=None, sms_body=None):
    """Send email and/or WhatsApp notifications based on user preferences"""
    try:
        preferences = get_user_preferences(username)
        contact_info = get_contact_info(username)
        
        # Send email notification
        if preferences.get('email_notifications') and contact_info.get('email'):
            send_email(contact_info['email'], event_type, email_body or message)
        
        # Send WhatsApp notification (replacing SMS)
        if preferences.get('sms_notifications') and contact_info.get('phone'):
            send_sms(contact_info['phone'], sms_body or message)
            
        return True
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False

def send_email(to_email, subject, body):
    """Send email using SMTP (Gmail)"""
    try:
        import os
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Load environment variables
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        
        if not sender_email or not sender_password:
            print(f"[EMAIL] Credentials not configured. Email not sent to {to_email}")
            return False
        
        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = sender_email
        message['To'] = to_email
        
        # Create HTML email
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="background-color: #f5f5f5; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #667eea;">{subject}</h2>
                    <div style="background-color: white; padding: 20px; border-radius: 4px; margin-top: 10px;">
                        <pre style="white-space: pre-wrap; word-wrap: break-word;">{body}</pre>
                    </div>
                    <footer style="margin-top: 20px; color: #999; font-size: 12px;">
                        <p>Job Detection AI System</p>
                    </footer>
                </div>
            </body>
        </html>
        """
        
        message.attach(MIMEText(html_body, 'html'))
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
        
        print(f"[EMAIL SENT] To: {to_email} | Subject: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email to {to_email}: {str(e)}")
        return False

def send_otp_email(to_email, otp, username='User'):
    """Send OTP email directly (for registration - user doesn't exist yet)"""
    try:
        import os
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Load environment variables
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        
        if not sender_email or not sender_password:
            print(f"[OTP EMAIL] SMTP credentials not configured. OTP not sent to {to_email}")
            return False
        
        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = 'Your OTP for Job Detection AI Registration'
        message['From'] = sender_email
        message['To'] = to_email
        
        # Create HTML email with OTP
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="background-color: #f5f5f5; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #667eea;">Your OTP for Job Detection AI</h2>
                    <div style="background-color: white; padding: 20px; border-radius: 4px; margin-top: 10px;">
                        <p>Hello {username},</p>
                        <p>Your One-Time Password (OTP) for registration is:</p>
                        <div style="background-color: #f0f0f0; padding: 15px; border-radius: 4px; text-align: center; margin: 20px 0;">
                            <p style="font-size: 32px; font-weight: bold; color: #667eea; margin: 0; letter-spacing: 5px;">{otp}</p>
                        </div>
                        <p style="color: #999; font-size: 14px;">This OTP will expire in 10 minutes.</p>
                        <p style="color: #d9534f;">Do not share this OTP with anyone.</p>
                    </div>
                    <footer style="margin-top: 20px; color: #999; font-size: 12px;">
                        <p>Job Detection AI System</p>
                        <p>If you did not request this OTP, please ignore this email.</p>
                    </footer>
                </div>
            </body>
        </html>
        """
        
        message.attach(MIMEText(html_body, 'html'))
        
        # Send email
        print(f"[OTP EMAIL] Connecting to {smtp_server}:{smtp_port}")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            print(f"[OTP EMAIL] STARTTLS successful, logging in as {sender_email}")
            server.login(sender_email, sender_password)
            print(f"[OTP EMAIL] Login successful, sending to {to_email}")
            server.send_message(message)
        
        print(f"[OTP EMAIL SENT] To: {to_email} | OTP: {otp}")
        return True
    except Exception as e:
        print(f"[OTP EMAIL ERROR] Failed to send OTP to {to_email}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def send_otp_firebase(phone, otp, username='User'):
    """Save OTP to user inbox for later retrieval"""
    try:
        return save_otp_to_inbox(username, otp)
    except Exception as e:
        print(f"[OTP INBOX ERROR] {str(e)}")
        return False


def save_otp_to_inbox(username, otp):
    """Save OTP message to user inbox"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        message_body = f"Your OTP for registration is: {otp}\n\nThis OTP will expire in 10 minutes.\n\nDo not share this with anyone."
        
        cursor.execute('''
            INSERT INTO inbox_messages (username, message_type, title, body, otp)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, 'otp', 'OTP Verification Code', message_body, otp))
        
        conn.commit()
        conn.close()
        
        print(f"[INBOX] OTP message saved for {username}")
        return True
        
    except Exception as e:
        print(f"[INBOX ERROR] Failed to save OTP to inbox: {str(e)}")
        return False


def get_inbox_messages(username, unread_only=False):
    """Retrieve inbox messages for a user"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if unread_only:
            cursor.execute('''
                SELECT id, message_type, title, body, otp, is_read, created_at
                FROM inbox_messages
                WHERE username = ? AND is_read = 0
                ORDER BY created_at DESC
                LIMIT 50
            ''', (username,))
        else:
            cursor.execute('''
                SELECT id, message_type, title, body, otp, is_read, created_at
                FROM inbox_messages
                WHERE username = ?
                ORDER BY created_at DESC
                LIMIT 100
            ''', (username,))
        
        messages = cursor.fetchall()
        conn.close()
        
        return messages
        
    except Exception as e:
        print(f"[INBOX ERROR] Failed to retrieve messages: {str(e)}")
        return []


def mark_message_as_read(message_id):
    """Mark a message as read"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE inbox_messages
            SET is_read = 1
            WHERE id = ?
        ''', (message_id,))
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"[INBOX ERROR] Failed to mark message as read: {str(e)}")
        return False


def delete_inbox_message(message_id):
    """Delete a message from inbox"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM inbox_messages WHERE id = ?', (message_id,))
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"[INBOX ERROR] Failed to delete message: {str(e)}")
        return False

def send_otp_sms(phone, otp, username='User'):
    """Send OTP via SMS using Twilio"""
    try:
        import os
        from twilio.rest import Client
        
        # Load Twilio credentials
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not account_sid or not auth_token or not twilio_phone:
            print(f"[OTP SMS] Twilio credentials not configured")
            return False
        
        # Initialize Twilio client
        client = Client(account_sid, auth_token)
        
        # Format phone number
        if not phone.startswith('+'):
            phone = '+91' + phone.lstrip('0')  # Default to India
        
        # Create SMS message
        message_body = f"Your Job Detection AI OTP is: {otp}\n\nThis OTP will expire in 10 minutes.\nDo not share this with anyone."
        
        print(f"[OTP SMS] Sending to {phone}")
        message = client.messages.create(
            body=message_body,
            from_=twilio_phone,
            to=phone
        )
        
        print(f"[OTP SMS SENT] To: {phone} | SID: {message.sid}")
        return True
        
    except Exception as e:
        print(f"[OTP SMS ERROR] Failed to send SMS to {phone}: {str(e)}")
        return False

# SMS FEATURE REMOVED - Commented out
# def send_sms(phone, message):
#     """Send SMS via Firebase using REST API"""
#     try:
#         import os
#         import requests
#         
#         # Firebase web API key (from .env)
#         firebase_api_key = os.getenv('FIREBASE_API_KEY')
#         firebase_project_id = os.getenv('FIREBASE_PROJECT_ID')
#         
#         if not firebase_api_key or not firebase_project_id:
#             print("[SMS] Firebase API key or Project ID not configured")
#             return False
#         
#         # Firebase Phone Authentication SMS endpoint
#         # This sends a verification code via SMS to the phone number
#         url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode?key={firebase_api_key}"
#         
#         payload = {
#             "phoneNumber": phone,
#             "recaptchaToken": ""  # Empty for testing
#         }
#         
#         response = requests.post(url, json=payload)
#         result = response.json()
#         
#         if response.status_code == 200 and 'sessionInfo' in result:
#             print(f"[SMS] Firebase SMS sent to {phone}")
#             return True
#         else:
#             print(f"[SMS] Firebase SMS failed: {result.get('error', {}).get('message', 'Unknown error')}")
#             return False
#             
#     except ImportError:
#         print("[SMS] Requests library not installed")
#         return False
#     except Exception as e:
#         print(f"[SMS] Error sending Firebase SMS: {str(e)}")
#         return False
#     except Exception as e:
#         print(f"[FCM ERROR] Failed to send OTP via Firebase: {str(e)}")
#         return False

def send_sms(phone, message):
    """SMS feature disabled - returns False"""
    print("[SMS] SMS feature is disabled")
    return False

def send_whatsapp_with_template(phone, event_type, content_sid, content_variables=None):
    """Send WhatsApp message using Twilio Content Template"""
    try:
        import os
        import json
        from twilio.rest import Client
        
        # Load Twilio credentials
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        whatsapp_from = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        
        if not account_sid or not auth_token:
            print(f"[WhatsApp] Twilio credentials not configured. WhatsApp template not sent to {phone}")
            return False
        
        # Format phone number for WhatsApp
        if not phone.startswith('whatsapp:'):
            if not phone.startswith('+'):
                phone = '+91' + phone.lstrip('0')
            phone = f'whatsapp:{phone}'
        
        # Initialize Twilio client
        client = Client(account_sid, auth_token)
        
        # Prepare content variables
        variables = json.dumps(content_variables) if content_variables else '{}'
        
        # Send WhatsApp message with template
        whatsapp_message = client.messages.create(
            from_=whatsapp_from,
            content_sid=content_sid,
            content_variables=variables,
            to=phone
        )
        
        print(f"[WhatsApp TEMPLATE SENT] To: {phone} | Template: {event_type} | SID: {whatsapp_message.sid}")
        return True
        
    except Exception as e:
        print(f"[WhatsApp TEMPLATE ERROR] Failed to send template to {phone}: {str(e)}")
        return False

def generate_otp():
    """Generate a random 6-digit OTP"""
    import random
    return str(random.randint(100000, 999999))

def save_otp(username, phone, otp):
    """Save OTP for registration verification"""
    from datetime import datetime, timedelta
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if OTP already exists for this username
    cursor.execute('SELECT id FROM user_otp WHERE username = ?', (username,))
    existing = cursor.fetchone()
    
    # OTP expires in 10 minutes
    expires_at = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
    
    if existing:
        # Update existing OTP
        cursor.execute('''
            UPDATE user_otp 
            SET phone = ?, otp = ?, attempts = 0, verified = 0, created_at = CURRENT_TIMESTAMP, expires_at = ?
            WHERE username = ?
        ''', (phone, otp, expires_at, username))
    else:
        # Insert new OTP
        cursor.execute('''
            INSERT INTO user_otp (username, phone, otp, attempts, verified, expires_at)
            VALUES (?, ?, ?, 0, 0, ?)
        ''', (username, phone, otp, expires_at))
    
    conn.commit()
    conn.close()
    return True

def verify_otp(username, otp):
    """Verify OTP and return result with attempt count"""
    from datetime import datetime
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT otp, attempts, expires_at, verified
        FROM user_otp
        WHERE username = ?
    ''', (username,))
    
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return {'success': False, 'message': 'OTP not found. Please register again.', 'attempts': 0}
    
    otp_data = dict(result)
    current_attempts = otp_data['attempts']
    
    # Check if OTP has already been verified
    if otp_data['verified'] == 1:
        conn.close()
        return {'success': False, 'message': 'OTP already verified. Please login.', 'attempts': current_attempts}
    
    # Check if OTP expired
    expires_at = datetime.strptime(otp_data['expires_at'], '%Y-%m-%d %H:%M:%S')
    if datetime.now() > expires_at:
        conn.close()
        return {'success': False, 'message': 'OTP expired. Please regenerate.', 'attempts': current_attempts}
    
    # Check if maximum attempts exceeded
    if current_attempts >= 2:
        conn.close()
        return {'success': False, 'message': 'Maximum attempts exceeded. Please regenerate OTP.', 'attempts': current_attempts, 'max_attempts': True}
    
    # Verify OTP
    if otp_data['otp'] == otp:
        # Mark as verified
        cursor.execute('UPDATE user_otp SET verified = 1 WHERE username = ?', (username,))
        conn.commit()
        conn.close()
        return {'success': True, 'message': 'OTP verified successfully!', 'attempts': current_attempts}
    else:
        # Increment attempts
        cursor.execute('UPDATE user_otp SET attempts = attempts + 1 WHERE username = ?', (username,))
        conn.commit()
        conn.close()
        new_attempts = current_attempts + 1
        if new_attempts >= 2:
            return {'success': False, 'message': f'Invalid OTP. This was your last attempt.', 'attempts': new_attempts, 'max_attempts': True}
        else:
            return {'success': False, 'message': f'Invalid OTP. You have {2 - new_attempts} attempt(s) left.', 'attempts': new_attempts}

def is_otp_verified(username):
    """Check if OTP is verified for a username"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT verified FROM user_otp WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result['verified'] == 1:
        return True
    return False

def delete_otp(username):
    """Delete OTP record after account creation"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_otp WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    return True

def delete_user(username):
    """Delete user account and all associated data"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get user_id
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user_row = cursor.fetchone()
        
        if not user_row:
            conn.close()
            return {'success': False, 'message': 'User not found'}
        
        user_id = user_row['id']
        
        # Delete all associated data
        cursor.execute('DELETE FROM job_detections WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM user_activities WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM user_preferences WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM csv_uploads WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM user_otp WHERE username = ?', (username,))
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return {'success': True, 'message': 'User account and all data deleted successfully'}
    except Exception as e:
        conn.close()
        return {'success': False, 'message': f'Failed to delete user: {str(e)}'}

def register_device_token(phone, device_token, device_name=None):
    """Register a device token for Firebase Cloud Messaging"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO user_devices (phone, device_token, device_name)
            VALUES (?, ?, ?)
        ''', (phone, device_token, device_name or 'Unknown Device'))
        conn.commit()
        conn.close()
        return {'success': True, 'message': 'Device registered successfully'}
    except Exception as e:
        conn.close()
        return {'success': False, 'message': f'Failed to register device: {str(e)}'}

def get_device_tokens(phone):
    """Get all device tokens for a phone number"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT device_token FROM user_devices WHERE phone = ?', (phone,))
    results = cursor.fetchall()
    conn.close()
    return [row['device_token'] for row in results]

def delete_device_token(device_token):
    """Remove a device token"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_devices WHERE device_token = ?', (device_token,))
    conn.commit()
    conn.close()
    return True

def delete_otp(username):
    """Delete OTP record after account creation"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_otp WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    return True
