from os import path, makedirs, listdir
from functools import wraps
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, send_file
from flask_mysqldb import MySQL
import MySQLdb.cursors
from glob import glob
from re import match
from cv2 import imread, cvtColor, COLOR_BGR2GRAY, GaussianBlur, threshold, THRESH_BINARY_INV, dilate, THRESH_OTSU
import pytesseract
from numpy import ones, uint8
from pandas import read_excel, to_datetime
from pandas import DataFrame as df
from datetime import datetime, timedelta, timezone
from flask_cors import CORS
from qrcode import QRCode, constants
from io import BytesIO
from PIL import Image
import config as cfg
from requests import post, exceptions
from pytz import timezone, utc

excel_data = None

def load_excel(file_path):
    # Load Excel data using pandas
    return read_excel(file_path)

ALLOWED_EXTENSIONS = set(['png','jpg','jpeg','gif','tiff','tif'])
sheet_ext = set(['xlsx', 'xls',])

app = Flask(__name__)
app.config.from_object(cfg)
CORS(app)


UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.permanent_session_lifetime = timedelta(days=1)

pytesseract.pytesseract.tesseract_cmd = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

def is_user_logged_in():
    return 'loggedin' in session

def loggedin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not is_user_logged_in():
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return decorated_view

def qr_scan_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        # Check if the route is protected by loggedin_required
        if 'loggedin' in session:
            buffer_active = session.get('buffer_active', False)
            if buffer_active:
                qr_scan_time = session.get('qr_scan_time')
                if qr_scan_time:
                    duration = timedelta(minutes=5)  # Adjust as needed
                    current_time = datetime.now(timezone.utc)
                    if current_time - qr_scan_time < duration:
                        # If within buffer period, prevent logout
                        return "You cannot log out at the moment. Please try again later."

        return func(*args, **kwargs)
    return decorated_view

def extract_roll_numbers(image_path):
    img = imread(image_path)
    gray = cvtColor(img, COLOR_BGR2GRAY)
    blur = GaussianBlur(gray, (5, 5), 0)
    _, binary = threshold(blur,0, 255, THRESH_BINARY_INV + THRESH_OTSU)
    kernel = ones((2, 2), uint8)
    dilated = dilate(binary, kernel, iterations=2)
    _, _ = dilated.shape
    cong = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789,'
    text = pytesseract.image_to_string(dilated, config=cong)
    return [roll.strip() for roll in text.replace('\n', ',').split(',')]

def save_to_excel(attendance_data, date, filename):
    excel_path = f"static/upload_sheet/{filename}.xlsx"

    if not path.exists(excel_path):
        # Create a DataFrame with roll numbers from 1 to 100
        df1 = df({cfg.roll_number: range(1, 101)})
        df1[date] = 'A'  # Initially mark all students as absent
    else:
        df1 = read_excel(excel_path)

    if date not in df1.columns:
        df1[date] = 'A'  # Initially mark all students as absent

    for roll_number in attendance_data[cfg.roll_number]:
        # Update the existing row for the roll number
        df1.loc[df1[df1['Roll Number'] == roll_number].index, date] = 'P'  # Present

    # Sort the columns by date, keeping 'Roll Number' fixed
    cols = [cfg.roll_number] + sorted(df1.columns.drop(cfg.roll_number), key=to_datetime)
    df1 = df1[cols]

    df1.to_excel(excel_path, index=False)

def allowed_img(filename):
	return '.' in filename and \
			filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_sheet(filename):
	return '.' in filename and \
			filename.rsplit('.', 1)[1].lower() in sheet_ext


@app.route('/some_route')
def some_function():
    app.config['MYSQL_HOST']
    app.config['MYSQL_USER']
    app.config['MYSQL_PASSWORD']
    app.config['MYSQL_DB']

mysql = MySQL(app)
def accept_attendance(subject):
    flag= True
    new_subject = subject.strip()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('UPDATE attendance_validation SET approval=%s WHERE subject=%s', (flag,new_subject))
    mysql.connection.commit()
    cursor.close()
    


@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        user_type = 'student' if 'username1' in request.form else 'teacher'
        email_field = 'username1' if user_type == 'student' else 'username'
        password_field = 'password1' if user_type == 'student' else 'password'

        data = {
            'email': request.form.get(email_field),
            'password': request.form.get(password_field),
            'user_type': user_type
        }

        login_api_url = 'http://localhost:5001/api/login'

        try:
            response = post(login_api_url, json=data)
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('success'):
                    session['loggedin'] = True
                    session['id'] = response_data['user']['id']
                    session['username'] = response_data['user']['name']
                    dashboard_route = 'student' if user_type == 'student' else 'home'
                    return redirect(url_for(dashboard_route))
                else:
                    msg = response_data.get('message', 'Login failed')
            else:
                msg = 'Failed to connect to the login API'
        except exceptions.RequestException as e:
            msg = str(e)

    return render_template(cfg.teacher_login, msg=msg)
   
@app.route('/logout')
def logout():
	session.pop('loggedin', None)
	session.pop('id', None)
	session.pop('username', None)
	return redirect(url_for('login'))

    
@app.route('/logout_student')
def logout_student():
    buffer_active = session.get('buffer_active', False)
    if buffer_active:
        qr_scan_time = session.get('qr_scan_time')
        if qr_scan_time:
            # Convert qr_scan_time to a timezone-aware datetime object in UTC
            qr_scan_time = qr_scan_time.replace(tzinfo=utc)

            # Get the current time in India timezone
            current_time = datetime.now(timezone('Asia/Kolkata'))

            duration = timedelta(minutes=1)  # Adjust as needed
            if current_time - qr_scan_time < duration:
                msg = "You cannot log out at the moment. Please try again later."
                return render_template(cfg.student, msg= msg)
            else:
                session['buffer_active'] = False
                session.pop('loggedin', None)
                session.pop('id', None)
                session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        data = {
            'user_type': 'student',
            'name': request.form['name1'],
            'email': request.form['email1'],
            'password': request.form['password1'],
            'branch': request.form['branch1'],
            'year': request.form['year1'],
            'sem': request.form['sem1']
        }
        registration_api_url = 'http://localhost:5002/api/register'
        response = post(registration_api_url, json=data)
        return handle_response(response)
    return render_template(cfg.teacher_register)

@app.route('/teacher_register', methods=['GET', 'POST'])
def teacher_register():
    if request.method == 'POST':
        data = {
            'user_type': 'teacher',
            'name': request.form['name2'],
            'email': request.form['email2'],
            'password': request.form['password2'],
            'subject': request.form['subject']
        }
        registration_api_url = 'http://localhost:5002/api/register'
        response = post(registration_api_url, json=data)
        return handle_response(response)
    return render_template(cfg.teacher_register)

def handle_response(response):
    if response.status_code == 200:
        response_data = response.json()
        if response_data.get('success'):
            flash('Registration successful. Please log in.')
            return redirect(url_for('login'))
        else:
            flash(response_data.get('message', 'Registration failed'))
    else:
        flash('Failed to connect to the registration API')
    return redirect(url_for('home'))

# @app.route('/student_register', methods=['GET', 'POST'])
# def student_register():
#     msg = ''
    
#     if request.method == 'POST':
#         name1 = request.form['name1']
#         password1 = request.form['password1']
#         email1 = request.form['email1']
#         branch1 = request.form['branch1']
#         year1 = request.form['year1']
#         uniq_number = request.form['uniq_number']
#         sem1 = request.form['sem1'] 
    
#         if name1 and password1 :
#             cursor1 = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
#             cursor1.execute('SELECT email FROM student_login WHERE email = %s', (email1,))
#             account1 = cursor1.fetchone()
#             cursor1.execute('SELECT email FROM student_auth WHERE email = %s', (email1,))
#             account2 = cursor1.fetchone()
                
#             if  account1 or account2:
#                 msg = cfg.account
#                 return render_template(cfg.teacher_register,var1, msg=msg)
#             elif not match(r'[^@]+@[^@]+\.[^@]+', email1):
#                 msg = cfg.email
#                 return render_template(cfg.teacher_register,var1, msg=msg)
#             elif not match(r'[A-Za-z0-9]+', name1):
#                 msg = cfg.username
#                 return render_template(cfg.teacher_register,var1, msg=msg)
#             elif not name1 or not password1 or not email1:
#                 msg = cfg.form
#                 return render_template(cfg.teacher_register,var1, msg=msg)
#             else:
#                 cursor1.execute('INSERT INTO student_auth VALUES (NULL, %s, %s, %s, %s, %s, %s, %s)', ( name1, email1, branch1, year1, sem1, uniq_number, password1))
#                 mysql.connection.commit()
#                 cursor1.close()
#             msg =cfg.authenticate
#         return render_template(cfg.teacher_login, msg=msg)

  
#     return render_template(cfg.teacher_register, msg=msg)

    

# @app.route('/teacher_register', methods=['GET','POST'])
# def teacher_register():
#     msg=''
    
#     if request.method == 'POST':
#         name2 = request.form['name2']
#         password2 = request.form['password2']
#         email2 = request.form['email2']
#         branch2 = request.form['branch2']
#         year2 = request.form['year2']
#         subject = request.form['subject']
#         subject1 = subject.upper()
#         sem2 = request.form['sem2']  # Added line
        

#         if name2 and password2 :
#             cursor1 = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
#             cursor1.execute('SELECT email FROM teacher_auth WHERE email = %s', (email2,)) 
#             account1 = cursor1.fetchone()   
#             cursor1.execute('SELECT email FROM teacher_login WHERE email = %s', (email2,))    
#             account2 = cursor1.fetchone()
#             if  account1 or account2:
#                 msg = cfg.account
#                 render_template(var1, msg=msg)
#             elif not match(r'[^@]+@[^@]+\.[^@]+', email2):
#                 msg = cfg.email
#                 render_template(var1, msg=msg)
#             elif not match(r'[A-Za-z0-9]+', name2):
#                 msg = cfg.username
#                 render_template(var1, msg=msg)
#             elif not name2 or not password2 or not email2:
#                 msg = cfg.form
#                 render_template(var1, msg=msg)
#             else:
#                 cursor1.execute('INSERT INTO teacher_auth VALUES (NULL, %s, %s, %s, %s, %s, %s, %s)', ( name2, email2, branch2, year2, sem2, subject1, password2))

#                 mysql.connection.commit()
#                 cursor1.close()
#             msg = cfg.authenticate
#             return render_template(cfg.teacher_login, msg=msg)
    
#     return render_template(cfg.teacher_register, msg=msg)


@app.route('/home')
def home():
	return render_template(cfg.home)

@app.route('/student')
def  student():
    return render_template("student.html")

# Route to display user profile
@app.route('/user', methods=['GET', 'POST'])
def user_profile():
    global excel_data

    if request.method == 'POST':
        try:
            if 'file' in request.files:
                file = request.files['file']

                if file.filename != '':
                    file_path = f"{app.config['UPLOAD_FOLDER']}/{file.filename}"
                    file.save(file_path)

                # Load Excel data into memory
                    excel_data = load_excel(file_path)
                    return render_template(cfg.user_profile, message='File uploaded successfully')

            elif 'prn' in request.form:
                if excel_data is not None:
                    prn = int(request.form.get('prn'))  # Convert PRN to int

                # Search for the user with the given PRN
                    user = excel_data[excel_data['PRN'] == prn].to_dict(orient='records')

                    return render_template(cfg.user_profile, user=user)
                else:
                    return render_template(cfg.user_profile)
        except Exception as e:
            render_template(error,error_msg=str(e))

    return render_template(cfg.user_profile)

@app.route('/attendance', methods=['GET', 'POST'])
@loggedin_required
def attendance():   
    if request.method == 'POST':
            # Check if the post request has the file part
        if 'file' not in request.files:
            raise ValueError('No files selected')

        file = request.files['file']

            # If the user does not select a file, the browser also submits an empty part without filename
        if file.filename == '':
            raise ValueError('No files selected')

        if file and allowed_sheet(file.filename):
                # Specify the folder where you want to save the file
            upload_folder = 'static/upload_sheet'
                # Ensure the folder exists, create it if necessary
            if not path.exists(upload_folder):
                makedirs(upload_folder)
                # Save the file to the specified folder
            file.save(path.join(upload_folder, file.filename))
                # Additional processing if needed
            return render_template(cfg.attendance, msg='File uploaded successfully')

    return render_template(cfg.attendance)
			

@app.route('/update_profile', methods=['GET', 'POST'])
@loggedin_required
def update_profile():
    msg=''

    if 'loggedin' in session:
        user_id = session['id']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT id, name, email, branch, year, sem, subject FROM teacher_login WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        

        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'Update':
                # Update user details based on the form data
                
                user_data['branch'] = request.form['branch']
                user_data['year'] = request.form['year']
                user_data['subject'] = request.form['subject']
                user_data['sem'] = request.form['sem']

                # Update the user in the database
                cursor.execute(
                    'UPDATE teacher_login SET branch=%s, year=%s, subject=%s, sem=%s WHERE id=%s',
                    (user_data['branch'], user_data['year'],
                     user_data['subject'], user_data['sem'], user_id))
                mysql.connection.commit()
                msg = cfg.update

            elif action == 'Delete':
                # Delete user data from the database
                cursor.execute('UPDATE teacher_login SET subject=NULL, branch=NULL, year=NULL, sem= NULL WHERE id=%s', (user_id,))
                mysql.connection.commit()
                msg = cfg.delete


            elif action == 'Add':
                # Add new data with concatenation
                new_data1 = str(request.form['year'])
                new_data2 = request.form['branch']
                new_data3 = request.form['subject']
                new_data4 = request.form['sem']
                user1 = str(user_data['year'])
                user1 += f', {new_data1}'
                
                user_data['branch'] += f', {new_data2}'  # Modify as needed
                
                user_data['subject'] += f', {new_data3}'

                user_data['sem'] += f', {new_data4}'

                # Update the user in the database
                cursor.execute('UPDATE teacher_login SET subject=%s, year=%s, branch=%s, sem=%s WHERE id=%s', (user_data['subject'], user1, user_data['branch'],user_data['sem'], user_id))
                mysql.connection.commit()
                msg = cfg.add

            cursor.close()
            return render_template(cfg.update_profile, data= user_data, msg = msg)

        return render_template(cfg.update_profile, data = user_data, msg=msg)
    else:
        return redirect(url_for('home'))
			

@app.route('/model/<int:session_id>', methods=['GET', 'POST'])
def model(session_id):
    session_id_from_url = request.args.get('session_id')
        # Check if session_id_from_url is provided, if not, use session_id from URL parameter
    if session_id_from_url is not None:
        session_id = session_id_from_url
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(cfg.display_subjects, (session_id,))
    user_data = cursor.fetchone()
    cursor.close()
        # **************
    subjects = user_data['subject'].split(',') if user_data and 'subject' in user_data else []

    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        if file.filename != '' and file.mimetype.startswith('image'):
            file_path = 'uploads/' + file.filename
            file.save(file_path)
            roll_numbers = extract_roll_numbers(file_path)
            print(file_path)
            return render_template(cfg.ocr, roll_numbers=roll_numbers,image_path=file_path, data=subjects)
    return render_template(cfg.ocr, data=subjects)

    

@app.route('/confirm_numbers/<int:session_id>', methods=['POST'])
def confirm_numbers(session_id):
    session_id_from_url = request.args.get('session_id')
    if session_id_from_url is not None:
        session_id = session_id_from_url

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(cfg.display_subjects, (session_id,))
    user_data = cursor.fetchone()
    cursor.close()
    subjects = user_data['subject'].split(',') if user_data and 'subject' in user_data else []

    confirmed_numbers = request.form.getlist('confirmedNumbers')
    attendance_date = request.form.get('attendance_date')
        # ************
    filename = request.form.get('filename')
    filename1 = f'{filename}_{session_id}'.strip()
    
    attendance_data = df({cfg.roll_number: [int(num) for num in confirmed_numbers]})
    save_to_excel(attendance_data, attendance_date, filename1) 

    return render_template(cfg.ocr, attendance_data=attendance_data, data=subjects)


@app.route('/new_sheet')
@loggedin_required
def render():
	return render_template(cfg.attendance)

# Newly Added
def get_teacher():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT  FROM teacher_login')
    teacher = cursor.fetchall()
    cursor.close()
    return teacher

def get_students():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT id, name, email, branch, year, sem, subject, password FROM student_login')
    student = cursor.fetchall()
    cursor.close()
    return student


def authenticate_teacher():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT id, name, email, branch, year, sem, subject, password FROM teacher_auth')  # Replace 'users' with your actual table name
    teachers = cursor.fetchall()
    cursor.close()
    return teachers

def authenticate_student():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT id, name, email, branch, year, sem, subject, password FROM student_auth')  # Replace 'users' with your actual table name
    students = cursor.fetchall()
    cursor.close()
    return students

@app.route('/authenticate/<int:user_id>', methods=['POST'])
def authenticate_user(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT id, name, email, branch, year, sem, subject, password FROM teacher_auth WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    if user:
        try:
            cursor.execute('INSERT INTO teacher_login VALUES (NULL, %s, %s, %s, %s, %s, %s, %s)', ( user[1], user[2], user[3], user[4], user[5], user[6], user[7]))
            cursor.execute('DELETE FROM teacher_auth WHERE id = %s', (user_id,))
            mysql.connection.commit()
        except Exception as e:
            return render_template(error, error_msg=str(e))
    cursor.close()
    return redirect(url_for('user_details'))

@app.route('/reject/<int:user_id>', methods=['POST'])
def reject_user(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM teacher_auth WHERE id = %s', (user_id,))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('user_details'))

@app.route('/authenticate_students/<int:user_id>', methods=['POST'])
def authenticate_students(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT id, name, email, branch, year, sem, subject, password FROM student_auth WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    if user:
        try:
            cursor.execute('INSERT INTO student_login VALUES (NULL, %s, %s, %s, %s, %s, %s, %s)', ( user[1], user[2], user[3], user[4], user[5], user[6], user[7]))
            cursor.execute('DELETE FROM student_auth WHERE id = %s', (user_id,))
            mysql.connection.commit()
        except Exception as e:
            return render_template(error, error_msg=str(e))
    cursor.close()
    return redirect(url_for('user_details'))

@app.route('/reject_student/<int:user_id>', methods=['POST'])
def reject_student(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM student_auth WHERE id = %s', (user_id,))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('user_details'))

@app.route('/user-details')
def user_details():
    teacher = get_teacher()
    student = get_students()
    auth_teacher = authenticate_teacher()
    auth_student = authenticate_student()
    return render_template(cfg.user_details, teacher=teacher, student=student, auth_teacher=auth_teacher, auth_student=auth_student)




@app.route('/teacher_dashboard', methods=['GET', 'POST'])
@loggedin_required
def teacher_dashboard():
    if 'loggedin' in session:
        user_id = session['id']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(cfg.display_subjects, (user_id,))
        user_data = cursor.fetchone()
        cursor.close()
        subjects = user_data['subject'].split(',') if user_data and 'subject' in user_data else subjects == []
        current_date = datetime.now().strftime('%Y-%m-%d')
        return render_template(cfg.teacher_dashboard, subjects=subjects, date=current_date, user_id=user_id)




@app.route('/student_dashboard', methods=['GET'])
def student_dashboard():
    if 'loggedin' in session:
        user_id = session.get('id')
        if user_id:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT unique_number FROM student_login WHERE id = %s", (user_id,))
            roll_number = cursor.fetchone()
            cursor.close()
            return render_template(cfg.student, roll_number=roll_number['unique_number'])
        else:
            # Handle case when user_id is not found in session
            return "Error: User ID not found in session"
        



@app.route('/generate_qr_with_location', methods=['POST'])
def generate_qr_with_location():
    data = request.get_json()
    subject = data['subject'].strip()
    print(subject)
    f_date = data['date']  # Use the date from the request
    date_obj = datetime.strptime(f_date, "%d/%m/%Y")

# Format the datetime object into the desired string format
    date = date_obj.strftime("%Y-%m-%d")
    print(date)
    latitude = data['latitude']
    longitude = data['longitude']
    user_id = data['user_id']
    accept_attendance(subject)
    qr_data = f"User_id: {user_id}, Subject: {subject}, Date: {date}, Latitude: {latitude}, Longitude: {longitude}"
    # Generate QR code
    qr = QRCode(
        version=1,
        error_correction=constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')


@app.route('/mark_attendance', methods=['POST'])
@loggedin_required
def mark_attendance():
    msg={}
    if 'loggedin' in session:
        data = request.get_json()
        if not data or 'qr_code_data' not in data:
            return jsonify({"error": "Invalid data format"}), 400

        qr_code_data = data["qr_code_data"]
        
    # Directly access data assuming it's a JSON object
        subject = qr_code_data.get("Subject")
        date = qr_code_data.get("Date")
        teacher_id = qr_code_data.get("User_id")
        
        if not subject:
            return jsonify({"error": "Missing subject in QR code data"}), 400
        if not date:
            return jsonify({"error": "Missing date in QR code data"}), 400

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT approval FROM attendance_validation WHERE subject = %s", (subject,))
        value = cursor.fetchone()

        if value['approval'] != '0':
            user_id = session['id']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT unique_number FROM student_login WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            cursor.close()
            if row is not None:
                roll_number = row['unique_number']
                # print("Roll number:", roll_number)
                
                attendance_data = df({cfg.roll_number: [int(roll_number)]})
                # print(attendance_data)
                filename = f"{subject}_{teacher_id}".strip()
                save_to_excel(attendance_data, date, filename)
                msg = {"message": "Attendance marked successfully!"}
            else:
                print("No row returned for the given user_id.")
        else:
            msg = {"message": "Attendance cannot be marked, either you are not in the Classroom, try again later or Contact your Teacher."}
        return jsonify(msg)

@app.route('/reject_attendance', methods=['POST'])
def reject_attendance():
    # Get user_id from the request JSON data
    subject = request.json.get('subject').strip()
    
    # Update the attendance validation record with the provided user_id
    if subject is not None:
        flag = False
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('UPDATE attendance_validation SET approval = %s WHERE subject = %s', (flag, subject))
        mysql.connection.commit()
        cursor.close()
        return 'Attendance rejected successfully', 200
    else:
        return 'Invalid request. User ID not provided.', 400




@app.route('/get_present_roll_numbers', methods=['POST'])
def get_present_roll_numbers():
    data = request.json
    subject = data.get('subject')
    user_id = session.get('id')  # Make sure to use session.get() to handle potential absence of 'id'

    if subject and user_id:
        filename = f"{subject}_{user_id}".strip()
        print(filename)
        file_path = path.join('static', 'upload_sheet', f'{filename}.xlsx')
        try:
            df1 = read_excel(file_path)
        except FileNotFoundError:
            return jsonify({'error': f'Attendance sheet for {subject} not found'})

        current_date = datetime.now().strftime('%Y-%m-%d')
        # print(current_date)
        if current_date in df1.columns:
            present_entries = df1.loc[df1[current_date] == "P", cfg.roll_number]
            present_values = present_entries.tolist()
            return jsonify({'present_values': present_values})
            print("present here")
        else:
            return jsonify({'error': 'No present entries for today'})
    else:
        return jsonify({'error': 'Subject not provided or user not logged in'})  # Adjust the error message as needed

@app.route('/upload_sheet', methods=['GET','POST'])
@loggedin_required
def upload_sheet():
    if 'loggedin' in session:
        user_id = session['id'] 
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(cfg.display_subjects, (user_id,))
        user_data = cursor.fetchone()
        cursor.close()
        excel_path = "static/upload_sheet/"
        subjects = user_data['subject'].split(',') if user_data and 'subject' in user_data else []
        if request.method == 'POST':
            year = request.form['year']
            dept = request.form['dept']
            subject = request.form['subject']
            file = request.files['file']

            if file and allowed_sheet(file.filename):
                filename = f"{year}_{dept}_{subject}_{user_id}.xlsx"
                filepath = path.join(excel_path, filename)

                file.save(filepath)
                
                
                return render_template(cfg.upload_sheet, subjects=subjects, message="File uploaded successfully.")
            else:
                return render_template(cfg.upload_sheet, subjects=subjects, error="Invalid file format.")
        else:
            return render_template(cfg.upload_sheet, subjects=subjects)

# Route for handling QR code scanning
@app.route('/qr_scan', methods=['POST'])
def qr_scan():
    session['qr_code_scanned'] = True
    ist = timezone('Asia/Kolkata')
    session['qr_scan_time'] = datetime.now(ist)
    session['buffer_active'] = True
    return 'QR code scanned successfully', 200



if __name__ == '__main__':
    app.run(host="0.0.0.0", ssl_context=("cert.pem", "key.pem"))


