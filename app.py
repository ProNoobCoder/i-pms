# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecret")

# PostgreSQL database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Upload directory
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database model
class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(100), nullable=False)
    cleaner = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    before_photo = db.Column(db.String(200), nullable=False)
    after_photo = db.Column(db.String(200), nullable=False)

# Routes
@app.route('/', methods=['GET', 'POST'])
def enter_hostname():
    if request.method == 'POST':
        hostname = request.form['hostname']
        session['hostname'] = hostname
        return redirect(url_for('upload'))
    return render_template('enter_hostname.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        cleaner = request.form['cleaner']
        hostname = request.form['hostname']
        before_file = request.files['before']
        after_file = request.files['after']

        if not all([cleaner, hostname, before_file, after_file]):
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

    # GET method — fetch hostname from session safely
    hostname = session.get('hostname')
    return render_template('index.html', hostname=hostname)

@app.route('/take_photo/<stage>', methods=['GET', 'POST'])
def take_photo(stage):
    if request.method == 'POST':
        photo = request.files['photo']
        if not photo:
            flash("No photo uploaded.")
            return redirect(request.url)

        hostname = session.get('hostname') or 'unknown'
        today = datetime.now().strftime("%Y-%m-%d")

        filename = secure_filename(f"{hostname}_{stage}.jpg")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        photo.save(filepath)
        watermark(filepath, hostname)

        flash(f"{stage.capitalize()} photo saved.")
        return redirect(url_for('upload'))

    return render_template('take_photo.html', stage=stage)

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('enter_hostname'))

# Helper: Add watermark
def watermark(image_path, hostname):
    img = Image.open(image_path).convert("RGBA")
    txt = Image.new("RGBA", img.size, (255,255,255,0))
    draw = ImageDraw.Draw(txt)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(font_path):
        font_path = "/Library/Fonts/Arial.ttf"  # fallback for macOS
    font = ImageFont.truetype(font_path, 32)
    text = f"{hostname} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    draw.text((10, 10), text, font=font, fill=(255, 0, 0, 180))
    watermarked = Image.alpha_composite(img, txt)
    watermarked.convert("RGB").save(image_path, "JPEG")

# Run the app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
