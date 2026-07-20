import sqlite3, os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = "nora_flower_pro_2026"

# Dosya yükleme ayarları
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Uploads klasörünü oluştur
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Mail ayarları (şimdilik konsola yazdırma simülasyonu)
MAIL_ENABLED = False  # True yaparsan gerçek mail gönderir
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USERNAME = "your_email@gmail.com"
MAIL_PASSWORD = "your_app_password"
MAIL_RECIPIENT = "admin@noracicek.com"

IBAN_ADRESI = "TR55 0006 4000 0013 3010 4299 08"
HESAP_SAHIBI = "Murat Karaceylan"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nora.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Veritabanı tablolarını güncelle (kargo_no sütunu ekle)
with get_db() as conn:
    conn.execute("CREATE TABLE IF NOT EXISTS urunler (id INTEGER PRIMARY KEY AUTOINCREMENT, baslik TEXT, fiyat INTEGER, eski_fiyat INTEGER DEFAULT 0, img TEXT, detay TEXT, kategori TEXT DEFAULT 'Genel', cok_satan INTEGER DEFAULT 0, stok INTEGER DEFAULT 0)")
    try:
        conn.execute("ALTER TABLE urunler ADD COLUMN stok INTEGER DEFAULT 0")
    except:
        pass
    conn.execute("CREATE TABLE IF NOT EXISTS siparisler (id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT, tel TEXT, adres TEXT, urunler TEXT, toplam INTEGER, tarih TEXT, durum TEXT DEFAULT 'Yeni', kargo_no TEXT DEFAULT '')")
    try:
        conn.execute("ALTER TABLE siparisler ADD COLUMN kargo_no TEXT DEFAULT ''")
    except:
        pass
    conn.execute("CREATE TABLE IF NOT EXISTS kuponlar (id INTEGER PRIMARY KEY AUTOINCREMENT, kod TEXT UNIQUE, oran INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS iletisim (id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT, email TEXT, mesaj TEXT, tarih TEXT)")
    conn.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_mail(subject, body):
    """Mail gönderme (şimdilik konsola yazdır)"""
    if not MAIL_ENABLED:
        print(f"📧 MAIL GÖNDERİLECEK: {subject}\n{body}")
        return True
    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_USERNAME
        msg['To'] = MAIL_RECIPIENT
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Mail gönderilemedi: {e}")
        return False

@app.route('/')
def home():
    with get_db() as conn:
        urunler = conn.execute("SELECT id, baslik, fiyat, CAST(eski_fiyat AS INTEGER) as eski_fiyat, img, detay, kategori, cok_satan, stok FROM urunler ORDER BY cok_satan DESC, id DESC").fetchall()
    kategoriler = sorted(list(set([u['kategori'] for u in urunler if u['kategori']])))
    return render_template('index.html', urunler=urunler, kategoriler=kategoriler, iban=IBAN_ADRESI, sahip=HESAP_SAHIBI)

@app.route('/ara')
def ara():
    q = request.args.get('q', '').strip()
    with get_db() as conn:
        if q:
            urunler = conn.execute("SELECT id, baslik, fiyat, CAST(eski_fiyat AS INTEGER) as eski_fiyat, img, detay, kategori, cok_satan, stok FROM urunler WHERE baslik LIKE ? OR detay LIKE ?", (f'%{q}%', f'%{q}%')).fetchall()
        else:
            urunler = conn.execute("SELECT id, baslik, fiyat, CAST(eski_fiyat AS INTEGER) as eski_fiyat, img, detay, kategori, cok_satan, stok FROM urunler ORDER BY id DESC").fetchall()
    kategoriler = sorted(list(set([u['kategori'] for u in urunler if u['kategori']])))
    return render_template('index.html', urunler=urunler, kategoriler=kategoriler, iban=IBAN_ADRESI, sahip=HESAP_SAHIBI, arama=q)

@app.route('/urun/<int:id>')
def urun_detay(id):
    with get_db() as conn:
        urun = conn.execute("SELECT id, baslik, fiyat, CAST(eski_fiyat AS INTEGER) as eski_fiyat, img, detay, kategori, cok_satan, stok FROM urunler WHERE id=?", (id,)).fetchone()
    if not urun:
        return "Ürün bulunamadı", 404
    return render_template('detay.html', cicek=urun)

@app.route('/iletisim', methods=['GET', 'POST'])
def iletisim():
    if request.method == 'POST':
        ad = request.form.get('ad')
        email = request.form.get('email')
        mesaj = request.form.get('mesaj')
        if ad and email and mesaj:
            tarih = datetime.now().strftime("%d.%m.%Y %H:%M")
            with get_db() as conn:
                conn.execute("INSERT INTO iletisim (ad, email, mesaj, tarih) VALUES (?,?,?,?)", (ad, email, mesaj, tarih))
                conn.commit()
            return render_template('basarili.html', mesaj="Mesajınız başarıyla gönderildi. En kısa sürede dönüş yapacağız.")
    return render_template('iletisim.html')

@app.route('/kupon-kontrol', methods=['POST'])
def kupon_kontrol():
    kod = request.get_json().get('kod', '').upper()
    with get_db() as conn:
        res = conn.execute("SELECT oran FROM kuponlar WHERE kod=?", (kod,)).fetchone()
    return jsonify({"ok": True, "oran": res['oran']}) if res else jsonify({"ok": False})

@app.route('/siparis-ver', methods=['POST'])
def siparis_ver():
    data = request.get_json()
    sepet = data.get('sepet', [])
    if not sepet:
        return jsonify({"hata": "Sepet boş"}), 400

    with get_db() as conn:
        for item in sepet:
            urun = conn.execute("SELECT stok FROM urunler WHERE baslik=?", (item['ad'],)).fetchone()
            if not urun or urun['stok'] < item['adet']:
                return jsonify({"hata": f"{item['ad']} ürününden yeterli stok yok!"}), 400
        for item in sepet:
            conn.execute("UPDATE urunler SET stok = stok - ? WHERE baslik=?", (item['adet'], item['ad']))
        tarih = datetime.now().strftime("%d.%m.%Y %H:%M")
        urunler_str = ", ".join([f"{x['ad']} x{x['adet']}" for x in sepet])
        toplam = data.get('toplam', 0)
        cur = conn.cursor()
        cur.execute("INSERT INTO siparisler (ad, tel, adres, urunler, toplam, tarih, kargo_no) VALUES (?,?,?,?,?,?,?)",
                    (data['musteri']['ad'], data['musteri']['tel'], data['musteri']['adres'], urunler_str, toplam, tarih, ''))
        sip_id = cur.lastrowid
        conn.commit()

    # Mail bildirimi (konsola yazdırma)
    mail_body = f"""
    Yeni Sipariş #{sip_id}
    Müşteri: {data['musteri']['ad']}
    Telefon: {data['musteri']['tel']}
    Adres: {data['musteri']['adres']}
    Ürünler: {urunler_str}
    Toplam: {toplam} TL
    Tarih: {tarih}
    """
    send_mail(f"Yeni Sipariş #{sip_id}", mail_body)

    return jsonify({"id": sip_id})

@app.route('/siparis-detay/<int:id>')
def siparis_detay(id):
    with get_db() as conn:
        sip = conn.execute("SELECT * FROM siparisler WHERE id=?", (id,)).fetchone()
    if not sip:
        return "Sipariş bulunamadı", 404
    return render_template('siparis_detay.html', siparis=sip)

@app.route('/panel')
def panel():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    with get_db() as conn:
        urunler = conn.execute("SELECT * FROM urunler ORDER BY id DESC").fetchall()
        siparisler = conn.execute("SELECT * FROM siparisler ORDER BY id DESC").fetchall()
        kuponlar = conn.execute("SELECT * FROM kuponlar").fetchall()
        iletisimler = conn.execute("SELECT * FROM iletisim ORDER BY id DESC").fetchall()
        stats = {
            "toplam_siparis": len(siparisler),
            "ciro": sum([s['toplam'] for s in siparisler]),
            "toplam_urun": len(urunler),
            "toplam_mesaj": len(iletisimler)
        }
    return render_template('panel.html', urunler=urunler, siparisler=siparisler, kuponlar=kuponlar, iletisimler=iletisimler, stats=stats)

@app.route('/grafik-verisi')
def grafik_verisi():
    with get_db() as conn:
        data = conn.execute("""
            SELECT DATE(tarih) as gun, COUNT(*) as adet, SUM(toplam) as ciro
            FROM siparisler
            WHERE tarih >= DATE('now', '-7 days')
            GROUP BY DATE(tarih)
            ORDER BY gun
        """).fetchall()
    gunler = [d['gun'] for d in data]
    adetler = [d['adet'] for d in data]
    cirolar = [d['ciro'] or 0 for d in data]
    return jsonify({"gunler": gunler, "adetler": adetler, "cirolar": cirolar})

@app.route('/urun-ekle', methods=['POST'])
def urun_ekle():
    cs = 1 if request.form.get('cok_satan') == '1' else 0
    stok = int(request.form.get('stok', 0))
    
    # Dosya yükleme
    img_url = request.form.get('img', '')
    if 'resim' in request.files:
        file = request.files['resim']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Benzersiz isim oluştur
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            img_url = url_for('static', filename=f'uploads/{filename}')
    
    with get_db() as conn:
        conn.execute("INSERT INTO urunler (baslik, fiyat, eski_fiyat, img, detay, kategori, cok_satan, stok) VALUES (?,?,?,?,?,?,?,?)",
                     (request.form['baslik'], request.form['fiyat'], request.form.get('eski_fiyat', 0), img_url,
                      request.form['detay'], request.form['kategori'], cs, stok))
        conn.commit()
    return redirect(url_for('panel'))

@app.route('/urun-duzenle/<int:id>', methods=['POST'])
def urun_duzenle(id):
    cs = 1 if request.form.get('cok_satan') == '1' else 0
    stok = int(request.form.get('stok', 0))
    
    # Dosya yükleme
    img_url = request.form.get('img', '')
    if 'resim' in request.files:
        file = request.files['resim']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            img_url = url_for('static', filename=f'uploads/{filename}')
    
    with get_db() as conn:
        conn.execute("UPDATE urunler SET baslik=?, fiyat=?, eski_fiyat=?, img=?, detay=?, kategori=?, cok_satan=?, stok=? WHERE id=?",
                     (request.form['baslik'], request.form['fiyat'], request.form.get('eski_fiyat', 0), img_url,
                      request.form['detay'], request.form['kategori'], cs, stok, id))
        conn.commit()
    return redirect(url_for('panel'))

@app.route('/kargo-guncelle/<int:id>', methods=['POST'])
def kargo_guncelle(id):
    kargo_no = request.form.get('kargo_no', '').strip()
    with get_db() as conn:
        conn.execute("UPDATE siparisler SET kargo_no=? WHERE id=?", (kargo_no, id))
        conn.commit()
    return redirect(url_for('panel'))

@app.route('/kupon-ekle', methods=['POST'])
def kupon_ekle():
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO kuponlar (kod, oran) VALUES (?,?)", (request.form['kod'].upper(), request.form['oran']))
        conn.commit()
    return redirect(url_for('panel'))

@app.route('/kupon-sil/<int:id>')
def kupon_sil(id):
    with get_db() as conn:
        conn.execute("DELETE FROM kuponlar WHERE id=?", (id,))
        conn.commit()
    return redirect(url_for('panel'))

@app.route('/siparis-sorgula/<int:id>')
def siparis_sorgula(id):
    with get_db() as conn:
        res = conn.execute("SELECT * FROM siparisler WHERE id=?", (id,)).fetchone()
    if res:
        d = dict(res)
        return jsonify({"ok": True, "ad": d['ad'], "durum": d['durum'], "toplam": d['toplam'], "urunler": d['urunler']})
    return jsonify({"ok": False})

@app.route('/durum-guncelle/<int:id>', methods=['POST'])
def durum_guncelle(id):
    with get_db() as conn:
        conn.execute("UPDATE siparisler SET durum=? WHERE id=?", (request.form.get('durum'), id))
        conn.commit()
    return redirect(url_for('panel'))

@app.route('/urun-sil/<int:id>')
def urun_sil(id):
    with get_db() as conn:
        conn.execute("DELETE FROM urunler WHERE id=?", (id,))
        conn.commit()
    return redirect(url_for('panel'))

@app.route('/siparis-sil/<int:id>')
def siparis_sil(id):
    with get_db() as conn:
        conn.execute("DELETE FROM siparisler WHERE id=?", (id,))
        conn.commit()
    return redirect(url_for('panel'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == "NORA" and password == "nora2026":
            session['logged_in'] = True
            return redirect(url_for('panel'))
        else:
            return render_template('login.html', hata="Kullanıcı adı veya şifre hatalı!")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)