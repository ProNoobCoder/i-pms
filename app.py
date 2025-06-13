import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Replace with a strong secret key

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# PostgreSQL Connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )

# Check file extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Add watermark
def add_watermark(image_path, hostname):
    img = Image.open(image_path).convert("RGBA")
    watermark = Image.new("RGBA", img.size)
    draw = ImageDraw.Draw(watermark)
    
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_size = 36
    font = ImageFont.truetype(font_path, font_size)

    text = f"Host: {hostname} | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    draw.text((10, 10), text, fill=(255, 0, 0, 150), font=font)
    
    combined = Image.alpha_composite(img, watermark)
    combined = combined.convert("RGB")
    combined.save(image_path)

@app.route('/', methods=['GET', 'POST'])
def enter_hostname():
    if request.method == 'POST':
        hostname = request.form['hostname'].strip().upper()
        if hostname:
            return redirect(url_for('index', hostname=hostname))
        else:
            flash('Hostname is required.')
    return render_template('enter_hostname.html')

@app.route('/index', methods=['GET', 'POST'])
def index():
    hostname = request.args.get('hostname', '')
    if request.method == 'POST':
        cleaner = request.form['cleaner'].strip()
        hostname = request.form['hostname'].strip().upper()

        before = request.files.get('before')
        after = request.files.get('after')

        if not (before and allowed_file(before.filename)):
            flash('Valid before photo is required.')
            return redirect(request.url)
        if not (after and allowed_file(after.filename)):
            flash('Valid after photo is required.')
            return redirect(request.url)

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        before_filename = secure_filename(f"{hostname}_before_{timestamp}.jpg")
        after_filename = secure_filename(f"{hostname}_after_{timestamp}.jpg")

        before_path = os.path.join(app.config['UPLOAD_FOLDER'], before_filename)
        after_path = os.path.join(app.config['UPLOAD_FOLDER'], after_filename)

        before.save(before_path)
        after.save(after_path)

        add_watermark(before_path, hostname)
        add_watermark(after_path, hostname)

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO pms_records (hostname, cleaner, date, before_img, after_img)
                VALUES (%s, %s, %s, %s, %s)
            """, (hostname, cleaner, datetime.now(), before_filename, after_filename))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            flash(f'Database error: {e}')
            return redirect(request.url)

        return redirect(url_for('success'))

    return render_template('index.html', hostname=hostname)

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/photo/<stage>', methods=['GET', 'POST'])
def take_photo(stage):
    if request.method == 'POST':
        photo = request.files.get('photo')
        if not (photo and allowed_file(photo.filename)):
            flash('Valid photo is required.')
            return redirect(request.url)

        filename = secure_filename(f"{stage}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        photo.save(photo_path)

        flash(f"{stage.capitalize()} photo uploaded successfully.")
        return redirect(url_for('success'))

    return render_template('take_photo.html', stage=stage)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    return redirect(url_for('enter_hostname'))

if __name__ == '__main__':
    app.run(debug=True)
