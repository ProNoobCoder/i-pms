from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import os
import zipfile

app = Flask(__name__)
app.secret_key = 'secretkey'

# Configs
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ZIP_FOLDER'] = 'static/zips'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['ZIP_FOLDER'], exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.jzhmkxvmqifhbpuvoerv:iloveanjingforever@aws-0-us-east-2.pooler.supabase.com:6543/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Entry(db.Model):
    __tablename__ = 'entry'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(100))
    cleaner = db.Column(db.String(100))
    date = db.Column(db.String(20))
    before_photo = db.Column(db.String(200))
    after_photo = db.Column(db.String(200))

# Add watermark
def watermark(image_path, text):
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((10, 10), text, font=font, fill="white")
    image.save(image_path)

# Cleaner name input
@app.route('/enter_cleaner', methods=['GET', 'POST'])
def enter_cleaner():
    if request.method == 'POST':
        session['cleaner'] = request.form['cleaner']
        return redirect(url_for('upload'))
    return render_template('enter_cleaner.html')

# Upload route (hostname + photos)
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    cleaner = session.get('cleaner')
    if not cleaner:
        return redirect(url_for('enter_cleaner'))

    if request.method == 'POST':
        hostname = request.form['hostname']
        session['hostname'] = hostname  # Save in session

        before_file = request.files['before']
        after_file = request.files['after']

        if not all([hostname, before_file, after_file]):
            flash("All fields are required")
            return redirect(url_for('upload'))

        today = datetime.now().strftime("%Y-%m-%d")
        before_filename = secure_filename(f"{hostname}_before.jpg")
        after_filename = secure_filename(f"{hostname}_after.jpg")

        before_path = os.path.join(app.config['UPLOAD_FOLDER'], before_filename)
        after_path = os.path.join(app.config['UPLOAD_FOLDER'], after_filename)

        before_file.save(before_path)
        after_file.save(after_path)

        watermark(before_path, hostname)
        watermark(after_path, hostname)

        entry = Entry(
            hostname=hostname,
            cleaner=cleaner,
            date=today,
            before_photo=before_filename,
            after_photo=after_filename
        )
        db.session.add(entry)
        db.session.commit()

        # Zip creation
        zip_path = os.path.join(app.config['ZIP_FOLDER'], f"{hostname}.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.write(before_path, arcname=before_filename)
            zipf.write(after_path, arcname=after_filename)

        return redirect(url_for('download', filename=f"{hostname}.zip"))

    return render_template('index.html', cleaner=cleaner)

# Download ZIP
@app.route('/download/<filename>')
def download(filename):
    path = os.path.join(app.config['ZIP_FOLDER'], filename)
    return send_file(path, as_attachment=True)

# Logout = new cleaner
@app.route('/logout')
def logout():
    session.pop('cleaner', None)
    session.pop('hostname', None)
    return redirect(url_for('enter_cleaner'))

# Home (redirect to cleaner)
@app.route('/')
def home():
    return redirect(url_for('enter_cleaner'))

if __name__ == '__main__':
    app.run(debug=True)
