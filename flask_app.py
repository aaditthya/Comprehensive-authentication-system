import os
import shutil
import sqlite3
import face_recognition
import pyaudio
import wave
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = '7878'

admin_credentials = {'username': 'admin', 'password': 'admin_password'}
admin = False
username = None
DOCUMENT_DIR = './documents'
IMG_DIR = './images'

conn = sqlite3.connect('data.db')
c = conn.cursor()

# Create tables if not exists
c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                admin INTEGER DEFAULT 0,
                login_attempts INTEGER DEFAULT 0,
                last_login TEXT DEFAULT NULL
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS face_encodings (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                encoding TEXT,
                FOREIGN KEY (username) REFERENCES users (username)
            )''')

conn.commit()
conn.close()

# Function to record and save voice sample
def record_voice_sample(filename):
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    RECORD_SECONDS = 5

    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    frames = []

    print("* Recording voice sample")

    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("* Finished recording")

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

# Routes
@app.route('/facelogin', methods=['GET', 'POST'])
def facelogin():
    global admin, username

    if request.method == 'POST':
        username = request.form['username']
        uploaded_image = request.files['image']
        
        # Save uploaded image
        save_path = IMG_DIR + '/image.png'
        uploaded_image.save(save_path)
        
        # Load and encode the uploaded image
        img = face_recognition.load_image_file(save_path)
        uploaded_encoding = face_recognition.face_encodings(img)
        
        if len(uploaded_encoding) > 0:
            uploaded_encoding_str = ','.join(map(str, uploaded_encoding[0]))
    
            conn = sqlite3.connect('data.db')
            c = conn.cursor()
    
            c.execute("SELECT username, encoding FROM face_encodings")
            rows = c.fetchall()
            for row in rows:
                known_username, known_encoding_str = row
                known_encoding = list(map(float, known_encoding_str.split(',')))
        
            # Compare uploaded encoding with stored encodings
            if face_recognition.compare_faces([known_encoding], uploaded_encoding[0])[0]:
                username = known_username
                c.execute("SELECT admin FROM users WHERE username=?", (username,))
                admin = c.fetchone()[0]
                conn.close()
                print(f"Redirecting user '{username}' to dashboard...")
                return redirect(url_for('dashboard'))
        conn.close()
    return render_template('Facelogin.html')

@app.route('/voicesignup', methods=['GET','POST'])
def voicesignup():
    if request.method == 'POST':
        username = request.form['username']  # Retrieve username from the form
        filename = os.path.join(IMG_DIR, f'{username}.wav')
        record_voice_sample(filename)
        
        # Create user directory
        user_dir = os.path.join(DOCUMENT_DIR, username)
        os.makedirs(user_dir, exist_ok=True)
        
        # Insert the username into the database
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username) VALUES (?)", (username,))
        conn.commit()
        conn.close()
        
        # Redirect to voicelogin route
        return redirect(url_for('voicelogin'))
    return render_template("VoiceSignup.html")


@app.route('/voicelogin', methods=['GET', 'POST'])
def voicelogin():
    global admin, username
    if request.method == 'POST':
        username = request.form['username']
        filename = os.path.join(IMG_DIR, f'{username}.wav')
        if os.path.exists(filename):
            record_voice_sample(filename)
            # Compare voice samples
            if compare_voice_samples(filename):
                admin = check_admin(username)
                print(f"Redirecting user '{username}' to dashboard...")
                return redirect(url_for('dashboard'))
    return render_template('VoiceLogin.html')
def compare_voice_samples(sample):
    return True  
def check_admin(username):
    return False  
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == admin_credentials['username'] and password == admin_credentials['password']:
            # Admin login successful, store login status in session
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard')) 
        else:
            # Admin login failed, display error message
            error_message = 'Invalid username or password'
            return render_template('admin_login.html', error_message=error_message)
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    # Check if admin is logged in
    if 'admin_logged_in' in session and session['admin_logged_in']:
        # Admin is logged in, render dashboard
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        users = c.fetchall()
        conn.close()
        return render_template('admin_dashboard.html', users=users)
    else:
        # Admin is not logged in, redirect to login page
        return redirect(url_for('admin_login'))

@app.route('/facesignup', methods=['GET','POST'])
def facesignup():
    if request.method == 'POST':
        username = request.form['username']
        uploaded_image = request.files['image']
        
        adminState = 'admin' if username.split('@')[0].split('.')[-1] == 'admin' else 'employee'
        
        # Save uploaded image
        save_path = IMG_DIR + '/image.png'
        uploaded_image.save(save_path)
        
        # Load and encode the uploaded image
        img = face_recognition.load_image_file(save_path)
        uploaded_encoding = face_recognition.face_encodings(img)
        
        if len(uploaded_encoding) > 0:
            uploaded_encoding_str = ','.join(map(str, uploaded_encoding[0]))
            
            conn = sqlite3.connect('data.db')
            c = conn.cursor()
            
            c.execute("INSERT INTO users (username, admin) VALUES (?, ?)", (username, adminState))
            c.execute("INSERT INTO face_encodings (username, encoding) VALUES (?, ?)", (username, uploaded_encoding_str))
            conn.commit()
            conn.close()
            
            if username not in os.listdir(DOCUMENT_DIR):
                os.mkdir(f'{DOCUMENT_DIR}/{username}')

            # Redirect to facelogin route
            return redirect(url_for('facelogin'))
            
    return render_template("FaceSignup.html")

@app.route('/imgsignup', methods=['POST', 'GET'])
def imgsignup():
    global selected_images

    if request.method == 'POST':
        data = request.get_json()

        username = data['username']

        conn = sqlite3.connect('data.db')
        c = conn.cursor()

        c.execute("INSERT INTO users (username) VALUES (?)", (username,))
        conn.commit()

        if username.split('@')[0].split('.')[-1] == 'admin':
            adminState = 1
        else:
            adminState = 0

        c.execute("UPDATE users SET admin=? WHERE username=?", (adminState, username))
        conn.commit()
        conn.close()

        if username not in os.listdir(DOCUMENT_DIR):
            os.mkdir(f'{DOCUMENT_DIR}/{username}')

        return jsonify({"redirect_url": url_for('imglogin')})
    
    return render_template('ImageSignup.html')

@app.route('/', methods=['POST', 'GET'])

def main_screen():
    return render_template('main_screen.html')

@app.route('/imglogin', methods=['POST', 'GET'])
def imglogin():

    global admin, username

    if request.method == 'POST':
        data = request.get_json()

        username = data['username']
        
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        
        c.execute("SELECT admin, login_attempts FROM users WHERE username=?", (username,))
        user_data = c.fetchone()
        if user_data:
            admin = user_data[0]
            login_attempts = user_data[1]

            # Update login attempts and last login time
            c.execute("UPDATE users SET login_attempts = login_attempts + 1, last_login = CURRENT_TIMESTAMP WHERE username = ?", (username,))
            conn.commit()

            # Limit login attempts to 3
            if login_attempts >= 3:
                return jsonify({"error": "Maximum login attempts exceeded."})
            
            return jsonify({"redirect_url": url_for('dashboard')})
        else:
            conn.close()
            return jsonify({"error": "User not found."})
        
    return render_template('Imagelogin.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    global admin, username

    conn = sqlite3.connect('data.db')
    c = conn.cursor()

    # Fetch the list of users from the database
    c.execute("SELECT * FROM users")
    users = c.fetchall()

    # Fetch the list of files assigned to the logged-in user
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    user = c.fetchone()
    if user:
        user_admin = True if user[2] == 1 else False
    else:
        user_admin = False

    employee_list = [user[1] for user in users if not user[2]]

    # Fetch the list of files assigned to the logged-in user
    assigned_files = os.listdir(os.path.join(DOCUMENT_DIR, username))

    conn.close()

    return render_template('Dashboard.html', assigned_files=assigned_files, user="Admin" if user_admin else "Employee")


@app.route('/fileview', methods=['POST', 'GET'])
def fileview():
    global username

    if request.method == 'POST':
        data = request.get_json()
        file_name = data.get('fileName')

        print(file_name)
         # Construct the redirect URL
        ROOT_PATH = 'static/'
        path = f'{DOCUMENT_DIR}/{username}/{file_name}'

        shutil.copy(path, ROOT_PATH)

        redirect_url = url_for('dashboard')

        # Return both the redirect URL and the file path in the JSON response
        return jsonify({"redirect_url": redirect_url, "file_path": ROOT_PATH+file_name})

    file_path = request.args.get('path', '')
    return render_template('FileView.html', path=file_path)

@app.route('/uploadfile', methods=['POST','GET'])
def uploadfile():
    if request.method == 'POST':
        uploaded_file = request.files['pdf_doc']
        # print(uploaded_file.filename)
        save_path = f'{DOCUMENT_DIR}/{username}/{uploaded_file.filename}'
        uploaded_file.save(save_path)
        
        return redirect(url_for('dashboard'))
    
    return render_template('UploadFile.html')

@app.route('/assign_file', methods=['POST'])
def assign_file():
    if request.method == 'POST':
        file = request.files['file']
        username = request.form['user']

        # Save the uploaded file to the appropriate directory
        save_path = os.path.join(DOCUMENT_DIR, username, secure_filename(file.filename))
        file.save(save_path)

        return redirect(url_for('admin_dashboard'))

if __name__ == "__main__":
    app.run(debug=True)
