from flask import Flask, request, jsonify
import MySQLdb.cursors
from flask_mysqldb import MySQL
import config as cg

app = Flask(__name__)
app.config.from_object(cg)

mysql = MySQL(app)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    user_type = data.get('user_type')
    email = data.get('email')
    password = data.get('password')
    # Additional fields based on user type
    name = data.get('name')
    branch = data.get('branch', '')
    year = data.get('year', '')
    subject = data.get('subject', '').upper()
    sem = data.get('sem', '')

    if user_type not in ['student', 'teacher']:
        return jsonify({'success': False, 'message': 'Invalid user type'}), 400

    table_name = 'student_auth' if user_type == 'student' else 'teacher_auth'

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        if user_type == 'student':
            cursor.execute('INSERT INTO {} (name, email, password, branch, year, sem) VALUES (%s, %s, %s, %s, %s, %s)'.format(table_name), (name, email, password, branch, year, sem))
        else:  # teacher
            cursor.execute('INSERT INTO {} (name, email, password, subject) VALUES (%s, %s, %s, %s)'.format(table_name), (name, email, password, subject))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'success': True, 'message': 'Registration successful'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5002)