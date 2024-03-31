from flask import Flask, request, jsonify
import MySQLdb.cursors
from flask_mysqldb import MySQL
import config as cg

app = Flask(__name__)
app.config.from_object(cg)

mysql = MySQL(app)

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        user_type = data.get('user_type')  # Expecting 'student' or 'teacher'

        if user_type not in ['student', 'teacher']:
            return jsonify({'success': False, 'message': 'Invalid user type'}), 400

        table_name = 'student_login' if user_type == 'student' else 'teacher_login'

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(f'SELECT id, email, name FROM {table_name} WHERE email = %s AND password = %s', (email, password,))
        account = cursor.fetchone()
        cursor.close()

        if account:
            return jsonify({'success': True, 'message': 'Login successful', 'user': account})
        else:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    except Exception as e:
        app.logger.error(f'Error: {e}')
        return jsonify({'success': False, 'message': 'Internal Server Error'}), 500

if __name__ == '__main__':
    app.run(port=5001)