from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import os

app = Flask(__name__)
app.secret_key = 'secretkey'  # Replace this with a real secret in production

# Configure upload folder
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# PostgreSQL (from Supabase)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.jzhmkxvmqifhbpuvoerv:iloveanjingforever@aws-0-us-east-2.pooler.supabase.com:6543/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Model (must match existing table in Supabase)
class Entry(db.Model):
    __tablename__ = 'entry'  # Explicit to avoid issues
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(100))
    cleaner = db.Column(db.String(100))
    date = db.Column(db.String(20))
    before_photo = db.Column(db.String(200))
    after_photo = db.Column(db.String(200))

# Watermark function
def watermark(image_path, text):
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((10, 10), text, font=font, fill="white")
    image.save(image_path)

# Home route: upload form
@app.route('/')
def index():
    hostname = session.get('hostname', '')
    return render_template('index.html', hostname=hostname)

# Enter hostname
@app.route('/enter_hostname', methods=['GET', 'POST'])
def enter_hostname():
    if request.method == 'POST':
        session['hostname'] = request.form['hostname']
        return redirect(url_for('upload'))
    return render_template('enter_hostname.html')

# Upload photo route
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    hostname = session.get('hostname')
    if not hostname:
        flash("Please enter hostname first.")
        return redirect(url_for('enter_hostname'))

    if request.method == 'POST':
        cleaner = request.form['cleaner']
        before_file = request.files['before']
        after_file = request.files['after']

        if not all([cleaner, before_file, after_file]):
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

        return redirect(url_for('success'))

    return render_template('index.html', hostname=hostname)

# Success page
@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/logout')
def logout():
    session.pop('hostname', None)
    return redirect(url_for('enter_hostname'))

# Run app
if __name__ == '__main__':
    app.run(debug=True)
