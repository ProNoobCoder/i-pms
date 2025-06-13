import os
import zipfile
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from PIL import Image, ImageDraw, ImageFont
import psycopg2
from io import BytesIO

app = Flask(__name__)
app.secret_key = "your_secret_key"

# PostgreSQL connection URL (from environment variable)
DATABASE_URL = os.getenv("DATABASE_URL")

# Create directory for storing photos
PHOTO_DIR = "static/photos"
os.makedirs(PHOTO_DIR, exist_ok=True)

# Compress images to reduce file size
def compress_image(image_path):
    img = Image.open(image_path)
    img.save(image_path, optimize=True, quality=50)

# Add watermark to image
def add_watermark(image_path, text):
    img = Image.open(image_path).convert("RGBA")
    watermark_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_layer)
    font = ImageFont.load_default()

    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    x = img.width - text_w - 10
    y = img.height - text_h - 10
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 180))

    watermarked = Image.alpha_composite(img, watermark_layer).convert("RGB")
    watermarked.save(image_path)
    compress_image(image_path)

# Get DB connection
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user = request.form.get("user")
        if user:
            session["user"] = user
            return redirect(url_for("enter_hostname"))
    return render_template("index.html")

@app.route("/enter", methods=["GET", "POST"])
def enter_hostname():
    if "user" not in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        hostname = request.form.get("hostname")
        if hostname and hostname.startswith("IWSD") and len(hostname) == 9 and hostname[4:].isdigit():
            session["hostname"] = hostname

            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT status FROM pms_logs WHERE hostname = %s", (hostname,))
                        result = cur.fetchone()
                        if result:
                            serviced_by = result[0]
                            flash(f"⚠️ This PC has already been serviced by {serviced_by}.")
                            return redirect(url_for("enter_hostname"))
            except Exception as e:
                flash("Database error: " + str(e))
                return redirect(url_for("enter_hostname"))

            return redirect(url_for("take_before"))
        else:
            flash("⚠️ Hostname must start with 'IWSD' followed by 5 digits.")
    return render_template("enter_hostname.html")

@app.route("/take_before", methods=["GET", "POST"])
def take_before():
    if request.method == "POST"]:
        file = request.files.get("before_photo")
        if file and file.filename:
            hostname = session.get("hostname")
            filename = f"{hostname}_before.jpg"
            path = os.path.join(PHOTO_DIR, filename)
            file.save(path)
            add_watermark(path, f"{hostname} (before)")
            session["before_path"] = path
            return redirect(url_for("take_after"))
    return render_template("take_before.html")

@app.route("/take_after", methods=["GET", "POST"])
def take_after():
    if request.method == "POST"]:
        file = request.files.get("after_photo")
        if file and file.filename:
            hostname = session.get("hostname")
            after_filename = f"{hostname}_after.jpg"
            after_path = os.path.join(PHOTO_DIR, after_filename)
            file.save(after_path)
            add_watermark(after_path, f"{hostname} (after)")

            # Insert into database
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO pms_logs (hostname, status, timestamp)
                            VALUES (%s, %s, %s)
                            """,
                            (hostname, session.get("user"), datetime.now())
                        )
                        conn.commit()
            except Exception as e:
                flash("❌ Failed to save to database: " + str(e))
                return redirect(url_for("take_after"))

            # Create ZIP and download
            zip_path = os.path.join(PHOTO_DIR, f"{hostname}.zip")
            with zipfile.ZipFile(zip_path, "w") as zipf:
                zipf.write(session["before_path"], os.path.basename(session["before_path"]))
                zipf.write(after_path, os.path.basename(after_path))

            # Clean session
            session.pop("hostname", None)
            session.pop("before_path", None)

            return send_file(zip_path, as_attachment=True)

    return render_template("take_after.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
