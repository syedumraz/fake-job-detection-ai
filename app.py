from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, send_file
from datetime import timedelta, datetime
from ml_model import process_job_post, get_detector_info, retrain_model
from database import init_db, migrate_db, create_user, verify_user, save_job_detection, get_user_detections, get_user_profile, log_activity, get_user_activities, get_user_preferences, save_user_preferences, update_username, update_password, user_exists, save_csv_upload, get_user_csvs, delete_csv_upload, update_csv_filename, save_training_metrics, get_latest_training_metrics, get_all_training_metrics, get_training_statistics, save_contact_info, get_contact_info, send_notification, send_email, generate_otp, save_otp, verify_otp as verify_otp_db, is_otp_verified, delete_otp, send_otp_email, get_user_email, send_sms, delete_user, update_user_status, get_user_status
# SMS/Phone options removed: send_sms, register_device_token, get_device_tokens
import os, csv, uuid
import openpyxl
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# Session Management Constants (in minutes)
SESSION_TIMEOUT = 15  # Total session duration 
SESSION_WARNING_TIME = 13  # Show warning at 13 minutes

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_this'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=SESSION_TIMEOUT)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database on app startup
init_db()
migrate_db()



@app.context_processor
def inject_preferences():
    if 'username' in session:
        return {'user_preferences': get_user_preferences(session['username'])}
    return {'user_preferences': {'dark_mode': 0, 'compact_view': 0, 'email_notifications': 1}}
    # SMS notifications removed

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=SESSION_TIMEOUT)
    
    # Skip session check for login/register routes and static files
    if request.path in [url_for('login'), url_for('register'), url_for('forgot_password'), url_for('check_username'), url_for('check_session_status')] or request.path.startswith('/static/') or request.path.startswith('/uploads/'):
        return
    
    # Check if user is logged in
    if 'username' in session:
        # Update session expiry time
        session.modified = True

@app.route('/')
def index():
    # Redirect to dashboard if logged in, otherwise to login
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if verify_user(username, password):
            # Check if account is inactive
            if get_user_status(username) == 'Inactive':
                error = 'Your account is inactive. Please contact support.'
                return render_template('login.html', error=error)
            # Check if user has email notifications disabled (OTP required at login)
            user_prefs = get_user_preferences(username)
            
            if not user_prefs['email_notifications']:
                # Email notifications disabled - require OTP verification at login
                user_email = get_user_email(username)
                if user_email:
                    # Generate OTP for login verification
                    otp = generate_otp()
                    save_otp(username, None, otp)
                    
                    # Send OTP via email
                    email_sent = send_otp_email(user_email, otp, username)
                    if not email_sent:
                        print(f"[LOGIN OTP] Warning: Failed to send OTP email to {user_email}")
                    else:
                        print(f"[LOGIN OTP] OTP {otp} sent via email to {user_email}")
                    
                    # Store login attempt in session
                    session['login_username'] = username
                    session['login_password'] = password
                    
                    log_activity(username, 'login_attempt', 'Login attempted - OTP verification required')
                    
                    return redirect(url_for('verify_login_otp'))
            
            # Normal login flow (email notifications enabled or no preference set)
            session['username'] = username
            log_activity(username, 'login', 'Logged in')
            
            # Send welcome notification on login
            from datetime import datetime
            email_body = f"""
Welcome back, {username}!

Login Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

You're now connected to your Ai-fake-job system.
            """
            # SMS notification removed
            send_notification(
                username,
                'Welcome Back',
                email_body,
                email_body,
                email_body
            )
            
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password'
            return render_template('login.html', error=error)
    
    return render_template('login.html')

@app.route('/check-username', methods=['POST'])
def check_username():
    username = request.json.get('username')
    exists = user_exists(username)
    return jsonify({'exists': exists})

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username')
        if username and user_exists(username):
            return render_template('forgot_password.html', success='Password reset instructions would be sent to your email')
        else:
            return render_template('forgot_password.html', error='Username not found')
    return render_template('forgot_password.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        email_notifications = 1 if request.form.get('email_notifications') else 0
        # phone = request.form.get('phone', '').strip()  # SMS REMOVED
        phone = None  # SMS REMOVED - Phone field commented out
        error = None
        
        if not username:
            error = 'Username is required'
        elif not email:
            error = 'Email is required'
        elif not password:
            error = 'Password is required'
        elif password != confirm_password:
            error = 'Passwords do not match'
        elif len(username) < 3:
            error = 'Username must be at least 3 characters long'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters long'
        # Phone validation removed - SMS feature disabled
        # elif not phone:
        #     error = 'Phone number is required'
        # elif not phone.startswith('+'):
        #     error = 'Phone number must include country code (e.g., +918197420471)'
        elif '@' not in email or '.' not in email:
            error = 'Please enter a valid email address'
        
        if error:
            return render_template('register.html', error=error)
        
        if user_exists(username):
            error = 'Username already exists'
            return render_template('register.html', error=error)
        
        if email_notifications:
            # Email notifications enabled - require OTP during registration (original flow)
            # Generate OTP
            otp = generate_otp()
            save_otp(username, phone, otp)
            
            # Send OTP via email
            email_sent = send_otp_email(email, otp, username)
            if not email_sent:
                print(f"[OTP] Warning: Failed to send OTP email to {email}")
            else:
                print(f"[OTP] OTP {otp} sent via email to {email}")
            
            print(f"[OTP] OTP {otp} generated for user: {username}")
            
            # Store registration data temporarily in session
            session['reg_username'] = username
            session['reg_email'] = email
            session['reg_password'] = password
            session['reg_phone'] = phone
            
            log_activity(username, 'register_attempt', f'Registration started - OTP verification required')
            
            return redirect(url_for('verify_otp'))
        else:
            # Email notifications disabled - skip OTP during registration, will require OTP at login
            if create_user(username, password, phone, email):
                # Save user preferences with email_notifications disabled
                save_user_preferences(username, 0, 0, email_notifications, 0)
                
                # Log activity
                log_activity(username, 'register_success', 'Account created without registration OTP - OTP required at login')
                
                # Send welcome email
                send_email(email, 'Welcome to Ai-fake-job!', 
                          f'Hello {username},\n\nYour account has been created successfully.\nYou can now login and you will need to verify with OTP at login time.\n\nWelcome to Ai-fake-job!')
                
                success_msg = 'Registration successful! Your account has been created. Please login now - you will need to verify with OTP.'
                return render_template('login.html', success=success_msg)
            else:
                error = 'Failed to create account. Please try again.'
                return render_template('register.html', error=error)
    
    return render_template('register.html')


@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    # Check if user has initiated registration
    if 'reg_username' not in session:
        error = 'Please start registration again'
        return render_template('register.html', error=error)
    
    username = session.get('reg_username')
    phone = session.get('reg_phone')
    
    if request.method == 'POST':
        otp_input = request.form.get('otp', '').strip()
        error = None
        
        if not otp_input:
            error = 'OTP is required'
            return render_template('otp_verification.html', error=error, phone=phone)
        
        # Verify OTP
        result = verify_otp_db(username, otp_input)
        
        if not result['success']:
            error = result['message']
            attempts_left = result.get('attempts', 2)
            max_attempts = result.get('max_attempts', 2)
            
            # If max attempts reached, offer regeneration
            if attempts_left == 0:
                return render_template('otp_verification.html', 
                                       error=error, 
                                       phone=phone,
                                       attempts_exhausted=True,
                                       show_regenerate=True)
            else:
                return render_template('otp_verification.html', 
                                       error=error, 
                                       phone=phone,
                                       attempts_left=attempts_left)
        
        # OTP verified - create account
        password = session.get('reg_password')
        email = session.get('reg_email')
        phone = session.get('reg_phone')
        
        if create_user(username, password, phone, email):
            # Cleanup OTP
            delete_otp(username)
            
            # Clear session
            session.pop('reg_username', None)
            session.pop('reg_email', None)
            session.pop('reg_password', None)
            session.pop('reg_phone', None)
            
            log_activity(username, 'register_success', 'Account created and verified via OTP')
            
            # Send welcome email directly
            send_email(email, 'Welcome to Ai-fake-job!', 
                      f'Hello {username},\n\nYour account has been created successfully.\nYou can now login and start detecting job opportunities.\n\nWelcome to Ai-fake-job!')
            
            success_msg = 'Registration successful! Your account has been created. Please login now.'
            return render_template('login.html', success=success_msg)
        else:
            error = 'Failed to create account. Please try again.'
            return render_template('otp_verification.html', error=error, phone=phone)
    
    # GET request - show OTP verification form
    return render_template('otp_verification.html', phone=phone)


@app.route('/regenerate-otp', methods=['POST'])
def regenerate_otp():
    if 'reg_username' not in session:
        return redirect(url_for('register'))
    
    username = session.get('reg_username')
    phone = session.get('reg_phone')
    email = session.get('reg_email')
    
    # Generate new OTP
    otp = generate_otp()
    save_otp(username, phone, otp)
    
    # Send OTP via Firebase (tries Firebase, falls back to email)
    otp_message = f"Your new OTP for Ai-fake-job registration is: {otp}\n\nThis OTP will expire in 10 minutes.\n\nDo not share this OTP with anyone."
    fcm_sent = send_sms(phone, otp_message)
    
    # If Firebase not available, send via email as fallback
    if not fcm_sent and email:
        print(f"[OTP] Sending new OTP to email as Firebase fallback for user: {username}")
        send_otp_email(email, otp, username)
    
    log_activity(username, 'otp_regenerated', f'New OTP generated and sent via {"FCM" if fcm_sent else "Email"}')
    
    success_msg = 'New OTP has been sent. Check your device notification or email.'
    return render_template('otp_verification.html', phone=phone, success=success_msg)


@app.route('/verify-login-otp', methods=['GET', 'POST'])
def verify_login_otp():
    # Check if user has initiated login with OTP requirement
    if 'login_username' not in session:
        error = 'Please login again'
        return render_template('login.html', error=error)
    
    username = session.get('login_username')
    
    if request.method == 'POST':
        otp_input = request.form.get('otp', '').strip()
        error = None
        
        if not otp_input:
            error = 'OTP is required'
            return render_template('login_otp_verification.html', error=error)
        
        # Verify OTP
        result = verify_otp_db(username, otp_input)
        
        if not result['success']:
            error = result['message']
            attempts_left = result.get('attempts', 2)
            max_attempts = result.get('max_attempts', 2)
            
            # If max attempts reached, offer regeneration
            if attempts_left == 0:
                return render_template('login_otp_verification.html', 
                                       error=error,
                                       attempts_exhausted=True,
                                       show_regenerate=True)
            else:
                return render_template('login_otp_verification.html', 
                                       error=error,
                                       attempts_left=attempts_left)
        
        # OTP verified - complete login
        password = session.get('login_password')
        
        # Cleanup OTP
        delete_otp(username)
        
        # Clear session login attempt variables
        session.pop('login_username', None)
        session.pop('login_password', None)
        
        # Set logged in session
        session['username'] = username
        
        log_activity(username, 'login_success', 'Account verified via login OTP')
        
        # Send welcome notification on login
        from datetime import datetime
        user_email = get_user_email(username)
        email_body = f"""
Welcome back, {username}!

Login Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

You're now connected to your Ai-fake-job system.
        """
        send_notification(
            username,
            'Welcome Back',
            email_body,
            email_body,
            email_body
        )
        
        return redirect(url_for('dashboard'))
    
    # GET request - show login OTP verification form
    return render_template('login_otp_verification.html')


@app.route('/regenerate-login-otp', methods=['POST'])
def regenerate_login_otp():
    if 'login_username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('login_username')
    user_email = get_user_email(username)
    
    if not user_email:
        error = 'Could not retrieve email for OTP'
        return render_template('login_otp_verification.html', error=error)
    
    # Generate new OTP
    otp = generate_otp()
    save_otp(username, None, otp)
    
    # Send OTP via email
    email_sent = send_otp_email(user_email, otp, username)
    
    if not email_sent:
        print(f"[LOGIN OTP] Warning: Failed to send OTP email to {user_email}")
    else:
        print(f"[LOGIN OTP] OTP {otp} sent via email to {user_email}")
    
    log_activity(username, 'login_otp_regenerated', 'New OTP generated and sent via Email')
    
    success_msg = 'New OTP has been sent to your registered email address.'
    return render_template('login_otp_verification.html', success=success_msg)


@app.route('/register-device-token', methods=['POST'])
def route_register_device_token():
    """Register a device token for Firebase Cloud Messaging"""
    data = request.get_json()
    device_token = data.get('device_token')
    phone = data.get('phone')
    device_name = data.get('device_name', 'Unknown Device')
    
    if not device_token or not phone:
        return jsonify({'success': False, 'message': 'Missing device_token or phone'}), 400
    
    result = register_device_token(phone, device_token, device_name)
    return jsonify(result)


@app.route('/firebase-messaging-sw.js')
def firebase_service_worker():
    """Serve Firebase service worker"""
    return send_from_directory(os.path.dirname(__file__), 'firebase-messaging-sw.js', 
                               mimetype='application/javascript')


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    recent_activities = get_user_activities(session['username'], limit=5)
    
    # Get training statistics for dashboard
    training_stats = get_training_statistics()
    latest_metrics = get_latest_training_metrics()
    training_history = get_all_training_metrics(limit=5)
    
    user_prefs = get_user_preferences(session['username'])
    return render_template('dashboard.html', 
                         username=session['username'], 
                         recent_activities=recent_activities,
                         training_stats=training_stats,
                         latest_metrics=latest_metrics,
                         training_history=training_history,
                         user_preferences=user_prefs)

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_data = get_user_profile(session['username'])
    recent_activities = get_user_activities(session['username'], limit=4)
    
    return render_template('profile.html', user=user_data, recent_activities=recent_activities, username=session['username'])

@app.route('/update-profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    new_username = request.json.get('username')
    account_status = request.json.get('accountStatus', 'Active')
    
    # Save status to DB
    update_user_status(session['username'], account_status)
    
    if new_username and new_username != session['username']:
        if update_username(session['username'], new_username):
            session['username'] = new_username
            log_activity(new_username, 'profile', 'Updated account information')
            return jsonify({'success': True, 'username': new_username, 'accountStatus': account_status})
        return jsonify({'success': False, 'message': 'Username already exists'})
    
    log_activity(session['username'], 'profile', 'Updated account information')
    return jsonify({'success': True, 'username': session['username'], 'accountStatus': account_status})

@app.route('/update-password', methods=['POST'])
def update_password_route():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    new_password = request.json.get('newPassword')
    if new_password:
        update_password(session['username'], new_password)
        log_activity(session['username'], 'security', 'Changed password')
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Invalid password'})

@app.route('/update-contact', methods=['POST'])
def update_contact():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    email = request.json.get('email', '')
    phone = request.json.get('phone', '')
    
    # Save contact info to database
    save_contact_info(session['username'], email, phone)
    log_activity(session['username'], 'profile', 'Updated contact information')
    
    return jsonify({'success': True, 'email': email, 'phone': phone, 'country': request.json.get('country')})

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Get current preferences to avoid resetting unsubmitted fields
        current_prefs = get_user_preferences(session['username'])
        
        # Determine which form was submitted based on field presence
        if 'dark_mode' in request.form:
            # Appearance form was submitted
            dark_mode = int(request.form.get('dark_mode', 0))
            compact_view = int(request.form.get('compact_view', 0))
            email_notifications = current_prefs['email_notifications']
            profile_public = current_prefs['profile_public']
            show_activity_status = current_prefs['show_activity_status']
            log_activity(session['username'], 'settings', 'Updated appearance settings')
        elif 'profile_public' in request.form or 'privacy_form' in request.form:
            # Privacy form was submitted
            dark_mode = current_prefs['dark_mode']
            compact_view = current_prefs['compact_view']
            email_notifications = current_prefs['email_notifications']
            profile_public = 1 if request.form.get('profile_public') else 0
            show_activity_status = 1 if request.form.get('show_activity_status') else 0
            log_activity(session['username'], 'settings', 'Updated privacy settings')
        else:
            # Notifications form was submitted
            dark_mode = current_prefs['dark_mode']
            compact_view = current_prefs['compact_view']
            email_notifications = 1 if request.form.get('email_notifications') else 0
            profile_public = current_prefs['profile_public']
            show_activity_status = current_prefs['show_activity_status']
            log_activity(session['username'], 'settings', 'Updated notification settings')
        
        # SMS notifications removed
        sms_notifications = 0  # SMS REMOVED - Always False
        save_user_preferences(session['username'], dark_mode, compact_view, email_notifications, sms_notifications, profile_public, show_activity_status)
        return redirect(url_for('settings'))
    
    preferences = get_user_preferences(session['username'])
    return render_template('settings.html', username=session['username'], preferences=preferences)

@app.route('/api/download-data')
def download_data():
    """Export user data as JSON"""
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        username = session['username']
        user_profile = get_user_profile(username)
        detections = get_user_detections(username, limit=1000)
        activities = get_user_activities(username, limit=1000)
        
        # Prepare export data
        export_data = {
            'user_profile': dict(user_profile) if user_profile else {},
            'job_detections': [dict(d) for d in detections],
            'activities': [dict(a) for a in activities],
            'export_date': datetime.now().isoformat()
        }
        
        # For now, return as JSON for download
        return jsonify(export_data)
    except Exception as e:
        return jsonify({'error': f'Failed to export data: {str(e)}'}), 500

@app.route('/api/delete-account', methods=['POST'])
def delete_account():
    """Delete user account and all associated data"""
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        username = session['username']
        
        # Verify password
        password = request.json.get('password', '')
        if not verify_user(username, password):
            return jsonify({'success': False, 'message': 'Invalid password'}), 401
        
        # Delete user account
        result = delete_user(username)
        if result['success']:
            session.clear()
            log_activity(username, 'account', 'Account deleted')
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/check-session-status', methods=['POST'])
def check_session_status():
    """Check if session is still valid and return time remaining"""
    if 'username' not in session:
        return jsonify({'valid': False, 'message': 'Session expired'}), 401
    
    # Get session creation/modification time
    # Flask doesn't expose this directly, so we use the fact that
    # the session will be sent to the client
    # We'll calculate based on the WARNING and TIMEOUT constants
    
    return jsonify({
        'valid': True,
        'username': session.get('username'),
        'session_timeout': SESSION_TIMEOUT,
        'warning_time': SESSION_WARNING_TIME
    })

@app.route('/job-post-detector', methods=['GET', 'POST'])
def job_post_detector():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    result = None
    if request.method == 'POST':
        job_title = request.form.get('job_title', '')
        company_name = request.form.get('company_name', '')
        job_description = request.form.get('job_description', '')
        salary = request.form.get('salary', '')
        location = request.form.get('location', '')
        
        # Validate inputs
        if not all([job_title, company_name, job_description]):
            error = 'Please fill in all required fields'
            return render_template('job_post_detector.html', username=session['username'], error=error)
        
        result = process_job_post(job_description, job_title, company_name, salary)
        
        if result:
            save_job_detection(
                session['username'],
                job_title,
                company_name,
                job_description,
                salary,
                location,
                result.get('prediction', 'Unknown'),
                result.get('confidence', 0.0)
            )
            log_activity(session['username'], 'detection', f'Analyzed job post: {job_title}')
            
            # Send notification on job detection
            prediction = result.get('prediction', 'Unknown')
            confidence = result.get('confidence', 0.0) * 100
            email_body = f"""
Job Post Analysis Complete!

Job Title: {job_title}
Company: {company_name}
Result: {prediction}
Confidence: {confidence:.2f}%
Location: {location or 'Not specified'}
            """
            sms_body = f"Job Detected: {job_title} at {company_name} | Result: {prediction} ({confidence:.1f}%)"
            send_notification(
                session['username'],
                f'Job Post Analysis - {prediction}',
                sms_body,
                email_body,
                sms_body
            )
    
    # Get model information
    model_info = get_detector_info()
    
    # Get user's detection history
    user_detections = get_user_detections(session['username'], limit=10)
    user_prefs = get_user_preferences(session['username'])
    
    return render_template('job_post_detector.html', username=session['username'], result=result, model_info=model_info, user_detections=user_detections, preferences=user_prefs)

@app.route('/model-info')
def model_info():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    info = get_detector_info()
    user_prefs = get_user_preferences(session['username'])
    return render_template('model_info.html', username=session['username'], model_info=info, user_preferences=user_prefs)

@app.route('/analyse')
def analyse():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_prefs = get_user_preferences(session['username'])
    return render_template('analyse.html', username=session['username'], user_preferences=user_prefs)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    error = None
    ALLOWED = {'.xls', '.xlsx', '.csv'}
    if request.method == 'POST':
        file = request.files.get('csv_file')
        ext = os.path.splitext(file.filename)[1].lower() if file and file.filename else ''
        if not file or not file.filename or ext not in ALLOWED:
            error = 'Only Excel and CSV files (.xls, .xlsx, .csv) are allowed. PDF and other file types are not accepted.'
        else:
            from datetime import datetime
            temp_name = f"temp_{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_name)
            file.save(filepath)
            new_id = save_csv_upload(username, temp_name, file.filename)
            date_str = datetime.now().strftime('%d%m%Y')
            final_name = f"{new_id}{date_str}{ext}"
            final_path = os.path.join(app.config['UPLOAD_FOLDER'], final_name)
            os.rename(filepath, final_path)
            update_csv_filename(new_id, final_name)
            log_activity(username, 'upload', f'Uploaded file: {file.filename}')
            
            # Send notification on successful file upload
            email_body = f"""
Your file has been successfully uploaded!

Filename: {file.filename}
Size: {os.path.getsize(final_path) / 1024:.2f} KB
Upload Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

You can now use this file to train your model!
            """
            sms_body = f"File Uploaded: {file.filename} | Ready for model training"
            send_notification(
                username,
                'File Upload Successful',
                sms_body,
                email_body,
                sms_body
            )
            
            return redirect(url_for('upload'))
    user_csvs = get_user_csvs(username)
    return render_template('upload.html', username=username, user_csvs=user_csvs, error=error)

@app.route('/csv/download/<int:csv_id>')
def csv_download(csv_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    csvs = get_user_csvs(session['username'])
    entry = next((c for c in csvs if c['id'] == csv_id), None)
    if not entry:
        return 'Not found', 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], entry['filename'], as_attachment=True, download_name=entry['original_filename'])

@app.route('/csv/view/<int:csv_id>')
def csv_view(csv_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    csvs = get_user_csvs(session['username'])
    entry = next((c for c in csvs if c['id'] == csv_id), None)
    if not entry:
        return 'Not found', 404
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], entry['filename'])
    ext = os.path.splitext(entry['original_filename'])[1].lower()
    if ext == '.csv':
        with open(filepath, newline='', encoding='utf-8-sig') as f:
            rows = list(csv.reader(f))
    else:
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        rows = [[str(c) if c is not None else '' for c in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
    return jsonify({'filename': entry['original_filename'], 'rows': rows})

@app.route('/csv/update/<int:csv_id>', methods=['POST'])
def csv_update(csv_id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    csvs = get_user_csvs(session['username'])
    entry = next((c for c in csvs if c['id'] == csv_id), None)
    if not entry:
        return jsonify({'success': False, 'message': 'File not found'}), 404
    rows = request.json.get('rows', [])
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], entry['filename'])
    ext = os.path.splitext(entry['original_filename'])[1].lower()
    try:
        if ext == '.csv':
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                csv.writer(f).writerows(rows)
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            for row in rows:
                ws.append(row)
            wb.save(filepath)
        log_activity(session['username'], 'edit', f'Edited file: {entry["original_filename"]}')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/csv/delete/<int:csv_id>', methods=['POST'])
def csv_delete(csv_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    filename = delete_csv_upload(csv_id, session['username'])
    if filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        log_activity(session['username'], 'delete', f'Deleted CSV id {csv_id}')
    return redirect(url_for('upload'))

@app.route('/train-model/<int:csv_id>', methods=['POST'])
def train_model_route(csv_id):
    """Train the ML model with a specific CSV file"""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    # Get the algorithm from the request
    data = request.get_json() or {}
    algorithm = data.get('algorithm', 'knn')
    
    # Get the CSV file from user's uploads
    csvs = get_user_csvs(session['username'])
    entry = next((c for c in csvs if c['id'] == csv_id), None)
    
    if not entry:
        return jsonify({'success': False, 'message': 'File not found'}), 404
    
    # Get the file path
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], entry['filename'])
    
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': 'File does not exist'}), 404
    
    # Check if it's a CSV file
    ext = os.path.splitext(entry['original_filename'])[1].lower()
    
    # Convert Excel to CSV if needed
    temp_csv_path = None
    if ext in ['.xls', '.xlsx']:
        # Create a temporary CSV file
        temp_csv_path = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_train_{uuid.uuid4().hex}.csv')
        try:
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            ws = wb.active
            
            with open(temp_csv_path, 'w', newline='', encoding='utf-8') as f:
                csv_writer = csv.writer(f)
                for row in ws.iter_rows(values_only=True):
                    csv_writer.writerow([str(c) if c is not None else '' for c in row])
            
            wb.close()
            filepath = temp_csv_path
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error converting Excel to CSV: {str(e)}'})
    
    # Retrain the model with specified algorithm
    result = retrain_model(filepath, algorithm=algorithm)
    
    # Clean up temporary CSV if created
    if temp_csv_path and os.path.exists(temp_csv_path):
        os.remove(temp_csv_path)
    
    # Log the activity
    if result['success']:
        log_activity(session['username'], 'training', f'Trained model ({algorithm}) with: {entry["original_filename"]}')
        
        # Save training metrics to database for persistence
        if result.get('metrics'):
            metrics = result['metrics']
            save_training_metrics(
                algorithm=metrics.get('algorithm', algorithm),
                accuracy=metrics.get('accuracy', 0),
                precision=metrics.get('precision', 0),
                recall=metrics.get('recall', 0),
                f1_score=metrics.get('f1_score', 0),
                training_samples=metrics.get('training_samples', 0),
                features=metrics.get('features', 0),
                confusion_matrix=metrics.get('confusion_matrix', [[0, 0], [0, 0]])
            )
            
            # Send notification on successful training
            accuracy_pct = metrics.get('accuracy', 0) * 100
            email_body = f"""
Your model has been successfully trained!

Algorithm: {metrics.get('algorithm', algorithm)}
Accuracy: {accuracy_pct:.2f}%
Precision: {metrics.get('precision', 0) * 100:.2f}%
Recall: {metrics.get('recall', 0) * 100:.2f}%
F1 Score: {metrics.get('f1_score', 0) * 100:.2f}%
Training Samples: {metrics.get('training_samples', 0)}

Your model is now ready for making predictions!
            """
            sms_body = f"Model Training Complete! Accuracy: {accuracy_pct:.2f}% | Algorithm: {metrics.get('algorithm', algorithm)}"
            send_notification(
                session['username'],
                'Model Training Complete',
                sms_body,
                email_body,
                sms_body
            )
        
        # Remove from session since it's now in database
        session.pop('training_metrics', None)
        session.pop('training_csv_id', None)
    
    return jsonify(result)

@app.route('/api/scraped-jobs')
def get_scraped_jobs():
    """Get all scraped job data for dropdown population"""
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    jobs = []
    user_csvs = get_user_csvs(session['username'])
    
    for csv_entry in user_csvs:
        # Check if this is a scraped file (starts with 'extract_')
        if csv_entry['filename'].startswith('extract_'):
            try:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], csv_entry['filename'])
                
                # Read CSV file
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    # Try to detect if it's CSV or Excel
                    if filepath.endswith('.csv'):
                        import csv
                        reader = csv.DictReader(f)
                        for row in reader:
                            # Map LinkedIn columns to expected format
                            job = {
                                'title': row.get('title', ''),
                                'company': row.get('company', ''),
                                'description': row.get('description', ''),
                                'location': row.get('location', ''),
                                'date_posted': row.get('date_posted', ''),
                                'job_link': row.get('job_link', '')
                            }
                            jobs.append(job)
                    else:
                        # Handle Excel files
                        import openpyxl
                        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
                        ws = wb.active
                        headers = [cell.value for cell in ws[1]]
                        
                        for row in ws.iter_rows(min_row=2, values_only=True):
                            row_dict = dict(zip(headers, row))
                            job = {
                                'title': row_dict.get('title', ''),
                                'company': row_dict.get('company', ''),
                                'description': row_dict.get('description', ''),
                                'location': row_dict.get('location', ''),
                                'date_posted': row_dict.get('date_posted', ''),
                                'job_link': row_dict.get('job_link', '')
                            }
                            jobs.append(job)
                        wb.close()
                        
            except Exception as e:
                print(f"Error reading file {csv_entry['filename']}: {e}")
                continue
    
    return jsonify({'jobs': jobs})

@app.route('/extract-data', methods=['POST'])
def extract_data():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401

    payload = request.json or {}
    website = payload.get('website', '').strip().lower()
    page_url = payload.get('url', '').strip()

    if not website or not page_url:
        return jsonify({'success': False, 'message': 'Website and URL are required.'}), 400

    if website != 'linkedin':
        return jsonify({'success': False, 'message': 'Only LinkedIn extraction is supported at this time.'}), 400

    try:
        # Import the scraper function only when needed
        from linkedin_scraper import scrape_linkedin_to_csv
        print(f"DEBUG: Starting extraction for URL: {page_url}")
        
        original_filename = f'linkedin_jobs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        stored_filename = f'extract_{uuid.uuid4().hex}.csv'
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
        print(f"DEBUG: Output path: {output_path}")
        
        count = scrape_linkedin_to_csv(page_url, output_path, max_jobs=50)
        print(f"DEBUG: Scraped {count} jobs")
        
        upload_id = save_csv_upload(session['username'], stored_filename, original_filename)
        print(f"DEBUG: Upload ID: {upload_id}")

        if not upload_id:
            return jsonify({'success': False, 'message': 'Failed to save extracted file metadata.'}), 500

        log_activity(session['username'], 'extract', f'Extracted {count} jobs from LinkedIn to {original_filename}')

        return jsonify({
            'success': True,
            'message': f'Extracted {count} jobs to {original_filename}',
            'filename': original_filename,
            'csv_id': upload_id
        })
    except ImportError as e:
        print(f"DEBUG: Import error: {e}")
        return jsonify({'success': False, 'message': f'Import error: {str(e)}'}), 500
    except Exception as e:
        print(f"DEBUG: General error: {e}")
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        
        # Provide helpful error messages for common scenarios
        if 'timed out' in error_msg.lower() or 'timeout' in error_msg.lower():
            error_msg = ('LinkedIn blocked the request (timeout). This usually happens when LinkedIn detects automated access. '
                        'Try again in a few minutes, or use a different LinkedIn URL. '
                        'You can also extract data from a CSV file instead.')
        elif 'No job cards were found' in error_msg:
            error_msg += ' Try using https://in.linkedin.com/jobs/search/ instead of https://www.linkedin.com/jobs/search/'
        elif 'blocked' in error_msg.lower():
            error_msg = ('LinkedIn has blocked the request. This is a security measure by LinkedIn. '
                        'Try again later, use a VPN, or extract data from a CSV file instead.')
        
        return jsonify({'success': False, 'message': f'Extraction failed: {error_msg}'}), 500

@app.route('/api/training-metrics')
def get_training_metrics():
    """Get all training metrics from database"""
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        metrics = get_all_training_metrics(limit=20)
        return jsonify({'success': True, 'metrics': metrics})
    except Exception as e:
        return jsonify({'error': f'Failed to get metrics: {str(e)}'}), 500


# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    """Redirect invalid routes to login page"""
    return redirect(url_for('login'))

@app.errorhandler(405)
def method_not_allowed(e):
    """Redirect method not allowed to login page"""
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
