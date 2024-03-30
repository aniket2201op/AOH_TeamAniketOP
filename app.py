import os
from functools import wraps
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, send_file
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
import cv2
import pytesseract
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from flask_cors import CORS
import qrcode
from io import BytesIO
from PIL import Image


error = 'error.html'
# Placeholder for loaded Excel data
excel_data = None

def load_excel(file_path):
    # Load Excel data using pandas
    return pd.read_excel(file_path)

ALLOWED_EXTENSIONS = set(['png','jpg','jpeg','gif','tiff','tif'])
sheet_ext = set(['xlsx', 'xls',])



app = Flask(__name__)
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

def extract_roll_numbers(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur,0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(binary, kernel, iterations=2)
    hImg, wImg = dilated.shape
    cong = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789,'
    text = pytesseract.image_to_string(dilated, config=cong)
    return [roll.strip() for roll in text.replace('\n', ',').split(',')]

def save_to_excel(attendance_data, date, filename):
    excel_path = f"static/upload_sheet/{filename}.xlsx"

    if not os.path.exists(excel_path):
        # Create a DataFrame with roll numbers from 1 to 100
        df = pd.DataFrame({'Roll Number': range(1, 101)})
        df[date] = 'A'  # Initially mark all students as absent
    else:
        df = pd.read_excel(excel_path)

    if date not in df.columns:
        df[date] = 'A'  # Initially mark all students as absent

    for roll_number in attendance_data['Roll Number']:
        # Update the existing row for the roll number
        df.loc[df[df['Roll Number'] == roll_number].index, date] = 'P'  # Present

    # Sort the columns by date, keeping 'Roll Number' fixed
    cols = ['Roll Number'] + sorted(df.columns.drop('Roll Number'), key=pd.to_datetime)
    df = df[cols]

    df.to_excel(excel_path, index=False)

def allowed_img(filename):
	return '.' in filename and \
			filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_sheet(filename):
	return '.' in filename and \
			filename.rsplit('.', 1)[1].lower() in sheet_ext


app.secret_key = '1234'
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '@Aniket2201',
    'database': 'ved'
}
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '@Aniket2201'
app.config['MYSQL_DB'] = 'ved'

mysql = MySQL(app)
def accept_attendance(subject):
    flag= True
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('UPDATE attendance_validation SET approval=%s WHERE subject=%s', (flag, subject))
    mysql.connection.commit()
    cursor.close()
    


@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'username1' in request.form and 'password1' in request.form:
        email = request.form['username1']
        password = request.form['password1']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM student_login WHERE email = %s AND password =%s', (email, password,))
        account = cursor.fetchone()
        cursor.close()
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['name']
            
            return render_template('student.html')       
        else:
            msg = 'Incorrect E-mail / password !'
    elif request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        email = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM teacher_login WHERE email = %s AND password =%s', (email, password,))
        account = cursor.fetchone()
        cursor.close()
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['name']
            
            if account['email'] == 'admin@gmail.com':
                return render_template('admin.html')
            else: 
                return render_template('home.html') 
        else:
            msg = 'Incorrect E-mail / password !'

    return render_template('teacher_login.html', msg=msg)
   

    



@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    msg = ''
    
    if request.method == 'POST':
        name1 = request.form['name1']
        password1 = request.form['password1']
        email1 = request.form['email1']
        branch1 = request.form['branch1']
        year1 = request.form['year1']
        uniq_number = request.form['uniq_number']
        sem1 = request.form['sem1'] 
    
        if name1 and password1 :
            cursor1 = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor1.execute('SELECT * FROM student_login WHERE email = %s', (email1,))
            account1 = cursor1.fetchone()
            cursor1.execute('SELECT * FROM student_auth WHERE email = %s', (email1,))
            account2 = cursor1.fetchone()
                
            if  account1 or account2:
                msg = 'Account already exists!'
                return render_template('teacher_register.html',var1, msg=msg)
            elif not re.match(r'[^@]+@[^@]+\.[^@]+', email1):
                msg = 'Invalid email address!'
                return render_template('teacher_register.html',var1, msg=msg)
            elif not re.match(r'[A-Za-z0-9]+', name1):
                msg = 'Username must contain only characters and numbers!'
                return render_template('teacher_register.html',var1, msg=msg)
            elif not name1 or not password1 or not email1:
                msg = 'Please fill out the form!'
                return render_template('teacher_register.html',var1, msg=msg)
            else:
                cursor1.execute('INSERT INTO student_auth VALUES (NULL, %s, %s, %s, %s, %s, %s, %s)', ( name1, email1, branch1, year1, sem1, uniq_number, password1))
                mysql.connection.commit()
                cursor1.close()
            msg = 'Request for Authentication has been sent!'
        return render_template('teacher_login.html', msg=msg)

  
    return render_template('teacher_register.html', msg=msg)

    

@app.route('/teacher_register', methods=['GET','POST'])
def teacher_register():
    msg=''
    
    if request.method == 'POST':
        name2 = request.form['name2']
        password2 = request.form['password2']
        email2 = request.form['email2']
        branch2 = request.form['branch2']
        year2 = request.form['year2']
        subject = request.form['subject']
        subject1 = subject.upper()
        sem2 = request.form['sem2']  # Added line
        

        if name2 and password2 :
            cursor1 = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor1.execute('SELECT * FROM teacher_auth WHERE email = %s', (email2,)) 
            account1 = cursor1.fetchone()   
            cursor1.execute('SELECT * FROM teacher_login WHERE email = %s', (email2,))    
            account2 = cursor1.fetchone()
            if  account1 or account2:
                msg = 'Account already exists!'
                render_template(var1, msg=msg)
            elif not re.match(r'[^@]+@[^@]+\.[^@]+', email2):
                msg = 'Invalid email address!'
                render_template(var1, msg=msg)
            elif not re.match(r'[A-Za-z0-9]+', name2):
                msg = 'Username must contain only characters and numbers!'
                render_template(var1, msg=msg)
            elif not name2 or not password2 or not email2:
                msg = 'Please fill out the form!'
                render_template(var1, msg=msg)
            else:
                cursor1.execute('INSERT INTO teacher_auth VALUES (NULL, %s, %s, %s, %s, %s, %s, %s)', ( name2, email2, branch2, year2, sem2, subject1, password2))

                mysql.connection.commit()
                cursor1.close()
            msg = 'Request for Authentication has been sent!'
            return render_template('teacher_login.html', msg=msg)
    
    return render_template('teacher_register.html', msg=msg)


@app.route('/home')
def home():
	return render_template('home.html')


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
                    return render_template('user_profile.html', message='File uploaded successfully')

            elif 'prn' in request.form:
                if excel_data is not None:
                    prn = int(request.form.get('prn'))  # Convert PRN to int

                # Search for the user with the given PRN
                    user = excel_data[excel_data['PRN'] == prn].to_dict(orient='records')

                    return render_template('user_profile.html', user=user)
                else:
                    return render_template('user_profile')
        except Exception as e:
            render_template(error,error_msg=str(e))

    return render_template('user_profile.html')

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
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
                # Save the file to the specified folder
            file.save(os.path.join(upload_folder, file.filename))
                # Additional processing if needed
            return render_template("attendance.html", msg='File uploaded successfully')

    return render_template('attendance.html')
			

@app.route('/update_profile', methods=['GET', 'POST'])
@loggedin_required
def update_profile():
    msg=''

    if 'loggedin' in session:
        user_id = session['id']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM teacher_login WHERE id = %s", (user_id,))
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
                    'UPDATE register SET branch=%s, year=%s, subject=%s, sem=%s WHERE id=%s',
                    (user_data['branch'], user_data['year'],
                     user_data['subject'], user_data['sem'], user_id))
                mysql.connection.commit()
                msg = 'Updated Successfully'

            elif action == 'Delete':
                # Delete user data from the database
                cursor.execute('UPDATE teacher_login SET subject=NULL, branch=NULL, year=NULL, sem= NULL WHERE id=%s', (user_id,))
                mysql.connection.commit()
                msg = 'Deleted Successfully'


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
                msg = 'Added Successfully'

            cursor.close()
            return render_template('update_profile.html', data= user_data, msg = msg)

        return render_template('update_profile.html', data = user_data, msg=msg)
    else:
        return redirect(url_for('home'))
			

@app.route('/model/<int:session_id>', methods=['GET', 'POST'])
def model(session_id):
    session_id_from_url = request.args.get('session_id')
        # Check if session_id_from_url is provided, if not, use session_id from URL parameter
    if session_id_from_url is not None:
        session_id = session_id_from_url
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT subject FROM teacher_login WHERE id = %s", (session_id,))
    user_data = cursor.fetchone()
    cursor.close()
        # **************
    subjects = user_data['subject'].split(', ') if user_data and 'subject' in user_data else []

    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        if file.filename != '' and file.mimetype.startswith('image'):
            file_path = 'uploads/' + file.filename
            file.save(file_path)
            roll_numbers = extract_roll_numbers(file_path)
            print(file_path)
            return render_template('ocr.html', roll_numbers=roll_numbers,image_path=file_path, data=subjects)
    return render_template('ocr.html', data=subjects)

    

@app.route('/confirm_numbers/<int:session_id>', methods=['POST'])
def confirm_numbers(session_id):
    session_id_from_url = request.args.get('session_id')
    if session_id_from_url is not None:
        session_id = session_id_from_url

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT subject FROM teacher_login WHERE id = %s", (session_id,))
    user_data = cursor.fetchone()
    cursor.close()
    subjects = user_data['subject'].split(', ') if user_data and 'subject' in user_data else []

    confirmed_numbers = request.form.getlist('confirmedNumbers')
    attendance_date = request.form.get('attendance_date')
        # ************
    filename1 = request.form.get('filename')
    filename1 += f'_{session_id}'
    
    attendance_data = pd.DataFrame({'Roll Number': [int(num) for num in confirmed_numbers]})
    save_to_excel(attendance_data, attendance_date, filename1) 

    return render_template('ocr.html', attendance_data=attendance_data, data=subjects)


@app.route('/new_sheet')
@loggedin_required
def render():
	return render_template('attendance.html')

# @app.route('/change_password', methods=['GET', 'POST'])
# @loggedin_required
# def change_password():
#     if 'loggedin' in session:
#         if request.method == 'POST':
#             current_password = request.form['current_password']
#             new_password = request.form['new_password']
#             confirm_password = request.form['confirm_password']

#             cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
#             cursor.execute('SELECT * FROM teacher_login WHERE id = %s', (session['id'],))
#             user = cursor.fetchone()

#             if user and user['password'] == current_password:
#if new_password == confirm_password:
#                     try:
#                         cursor.execute('UPDATE teacher_login SET password = %s WHERE id = %s', (new_password, session['id']))
#                         mysql.connection.commit()
#                         msg = 'Password updated successfully, Login again'
#                         return render_template('login.html', msg=msg)
#                     except Exception as e:
#                         msg = 'Error updating password: ' + str(e)
#                 else:
#                     msg = 'New password and confirm password do not match'
#             else:
#                 msg = 'Current password is incorrect'
#             return render_template('change_pwd.html', msg=msg)
#     return render_template('change_pwd.html')

# Newly Added
def get_teacher():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM teacher_login')
    teacher = cursor.fetchall()
    cursor.close()
    return teacher

def get_students():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM student_login')
    student = cursor.fetchall()
    cursor.close()
    return student


def authenticate_teacher():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM teacher_auth')  # Replace 'users' with your actual table name
    teachers = cursor.fetchall()
    cursor.close()
    return teachers

def authenticate_student():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM student_auth')  # Replace 'users' with your actual table name
    students = cursor.fetchall()
    cursor.close()
    return students

@app.route('/authenticate/<int:user_id>', methods=['POST'])
def authenticate_user(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM teacher_auth WHERE id = %s', (user_id,))
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
    cursor.execute('SELECT * FROM student_auth WHERE id = %s', (user_id,))
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
    return render_template('user_details.html', teacher=teacher, student=student, auth_teacher=auth_teacher, auth_student=auth_student)


@app.route('/logout')
def logout():
	session.pop('loggedin', None)
	session.pop('id', None)
	session.pop('username', None)
	return redirect(url_for('login'))



@app.route('/teacher_dashboard', methods=['GET', 'POST'])
@loggedin_required
def teacher_dashboard():
    if 'loggedin' in session:
        user_id = session['id']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT subject FROM teacher_login WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        cursor.close()
        subjects = user_data['subject'].split(', ') if user_data and 'subject' in user_data else []
        current_date = datetime.now().strftime('%Y-%m-%d')
        return render_template('teacher_dashboard.html', subjects=subjects, date=current_date, user_id=user_id)




@app.route('/student_dashboard', methods=['GET'])
@loggedin_required
def student_dashboard():
    if 'loggedin' in session:
        user_id = session['id']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT unique_number FROM student_login WHERE id = %s", (user_id,))
        roll_number = cursor.fetchone()
        cursor.close()
        return render_template('student_dashboard.html', roll_number)



@app.route('/generate_qr_with_location', methods=['POST'])
def generate_qr_with_location():
    data = request.get_json()
    subject = data['subject']
    date = data['date']  # Use the date from the request
    latitude = data['latitude']
    longitude = data['longitude']
    user_id = data['user_id']
    accept_attendance(subject)
    qr_data = f"User_id: {user_id}, Subject: {subject}, Date: {date}, Latitude: {latitude}, Longitude: {longitude}"
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
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
        print(subject)

        if value['approval'] != '0':
            user_id = session['id']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT unique_number FROM student_login WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            cursor.close()
            if row is not None:
                roll_number = row['unique_number']
                # print("Roll number:", roll_number)
                
                attendance_data = pd.DataFrame({'Roll Number': [int(roll_number)]})
                # print(attendance_data)
                filename = f"{subject}_{teacher_id}"
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
    subject = request.json.get('subject')
    
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
    user_id = session['id']

    if subject:
        filename = f"{subject}_{user_id}"

        file_path = os.path.join('static', 'upload_sheet', f'{filename}.xlsx')
        try:
            df = pd.read_excel(file_path)
        except FileNotFoundError:
            return jsonify({'error': f'Attendance sheet for {subject} not found'})

        current_date = datetime.now().strftime('%Y-%m-%d')
        print(current_date)
        if current_date in df.columns:
            present_entries = df.loc[df[current_date] == "P", 'Roll Number']
            present_values = present_entries.tolist()
            return jsonify({'present_values': present_values})
        else:
            return jsonify({'error': 'No present entries for today'})
    else:
        return jsonify({'error': 'Subject not provided'})



if __name__ == '__main__':
    app.run(debug=True)


