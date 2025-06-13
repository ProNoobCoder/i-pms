from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import os
import io
import psycopg2
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = "static/photos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# PostgreSQL connection
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Add watermark and compress image
def add_watermark(image_path, text):
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    width, height = img.size
    draw.text((10, height - 20), text, font=font, fill="white")
    img = img.convert("RGB")
    img.save(image_path, format="JPEG", quality=70)  # Compress to 70% quality

# Home page (login cleaner name)
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form.get("username")
        if username:
            session["user"] = username
            return redirect(url_for("enter_hostname"))
    return render_template("index.html")

# Hostname entry
@app.route("/enter", methods=["GET", "POST"])
def enter_hostname():
    if "user" not in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        hostname = request.form.get("hostname")
        if hostname and hostname.startswith("IWSD") and len(hostname) == 9 and hostname[4:].isdigit():
            session["hostname"] = hostname
            return redirect(url_for("take_before"))
        else:
            flash("Hostname must start with 'IWSD' followed by 5 numbers.")
    return render_template("enter_hostname.html")

# Before photo capture
@app.route("/take_before", methods=["GET", "POST"])
def take_before():
    if request.method == "POST":
        file = request.files["photo"]
        if file:
            hostname = session.get("hostname")
            filename = f"{hostname}(before).jpg"
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(path)
            add_watermark(path, f"{hostname}(before)")
            session["before_photo"] = filename
            return redirect(url_for("take_after"))
    return render_template("take_photo.html", stage="before")

# After photo capture
@app.route("/take_after", methods=["GET", "POST"])
def take_after():
    if request.method == "POST":
        file = request.files["photo"]
        if file:
            hostname = session.get("hostname")
            filename = f"{hostname}(after).jpg"
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(path)
            add_watermark(path, f"{hostname}(after)")
            session["after_photo"] = filename

            # Save to DB
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO pms_logs (hostname, status, date) VALUES (%s, %s, %s)",
                            (hostname, session.get("user"), datetime.now())
                        )
                        conn.commit()
            except Exception as e:
                flash("Error saving to database: " + str(e))
                return redirect(url_for("enter_hostname"))

            return redirect(url_for("download_photos"))
    return render_template("take_photo.html", stage="after")

# Download compressed before & after photos
@app.route("/download")
def download_photos():
    hostname = session.get("hostname")
    before_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{hostname}(before).jpg")
    after_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{hostname}(after).jpg")

    # Combine both images into a ZIP in-memory
    import zipfile
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(before_path, arcname=f"{hostname}(before).jpg")
        zip_file.write(after_path, arcname=f"{hostname}(after).jpg")
    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{hostname}_PMS_Photos.zip"
    )

@app.route("/success")
def success():
    return render_template("success.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
