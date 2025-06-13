import os
import zipfile
import io
from datetime import datetime
from flask import Flask, request, render_template, redirect, flash, send_file, url_for
from flask_sqlalchemy import SQLAlchemy
from PIL import Image, ImageDraw, ImageFont
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Configure PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://localhost/ipms')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), unique=True, nullable=False)
    cleaner = db.Column(db.String(255), nullable=False)
    date = db.Column(db.String(50), nullable=False)

db.create_all()

def compress_image(image, quality=60):
    img = Image.open(image)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    return buffer

def add_watermark(image_bytes, hostname):
    image = Image.open(image_bytes).convert("RGB")
    draw = ImageDraw.Draw(image)

    # Try to load a font
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except:
        font = ImageFont.load_default()

    text = f"{hostname}"
    draw.text((10, 10), text, fill="red", font=font)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=60)
    buffer.seek(0)
    return buffer

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        cleaner = request.form.get("cleaner")
        hostname = request.form.get("hostname")
        before_file = request.files.get("before")
        after_file = request.files.get("after")

        if not all([cleaner, hostname, before_file, after_file]):
            flash("⚠️ All fields are required.")
            return redirect(url_for("index"))

        existing = Device.query.filter_by(hostname=hostname).first()
        if existing:
            flash(f'⚠️ This PC has already been serviced by "{existing.cleaner}".')
            return redirect(url_for("index"))

        today = datetime.now().strftime("%Y-%m-%d")

        before_bytes = add_watermark(compress_image(before_file), hostname)
        after_bytes = add_watermark(compress_image(after_file), hostname)

        # Create zip
        zip_filename = f"{secure_filename(hostname)}.zip"
        zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr(f"{hostname}_before.jpg", before_bytes.read())
            zipf.writestr(f"{hostname}_after.jpg", after_bytes.read())

        new_device = Device(hostname=hostname, cleaner=cleaner, date=today)
        db.session.add(new_device)
        db.session.commit()

        flash("✅ Uploaded and saved successfully.")
        return send_file(zip_path, as_attachment=True)

    return render_template("index.html")
