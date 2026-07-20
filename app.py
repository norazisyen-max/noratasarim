import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'nora_flower_pro_2026')

# Cloudinary ayarları
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

# PostgreSQL bağlantısı
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS urunler (
            id SERIAL PRIMARY KEY,
            baslik TEXT NOT NULL,
            fiyat INTEGER NOT NULL,
            eski_fiyat INTEGER DEFAULT 0,
            img TEXT,
            detay TEXT,
            kategori TEXT DEFAULT 'Genel',
            cok_satan INTEGER DEFAULT 0,
            stok INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS siparisler (
            id SERIAL PRIMARY KEY,
            ad TEXT NOT NULL,
            tel TEXT NOT NULL,
            adres TEXT NOT NULL,
            urunler TEXT,
            toplam INTEGER,
            tarih TEXT,
            durum TEXT DEFAULT 'Yeni',
            kargo_no TEXT DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kuponlar (
            id SERIAL PRIMARY KEY,
            kod TEXT UNIQUE,
            oran INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS iletisim (
            id SERIAL PRIMARY KEY,
            ad TEXT NOT NULL,
            email TEXT NOT NULL,
            mesaj TEXT NOT NULL,
            tarih TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

IBAN_ADRESI = "TR55 0006 4000 0013 3010 4299 08"
HESAP_SAHIBI = "Murat Karaceylan"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def upload_to_cloudinary(file):
    result = cloudinary.uploader.upload(file)
    return result.get('secure_url')

@app.route('/')
def home():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, baslik, fiyat, eski_fiyat, img, detay, kategori, cok_satan, stok FROM urunler ORDER BY cok_satan DESC, id DESC")
    urunler = cur.fetchall()
    conn.close()
    kategoriler = sorted(list(set([u['kategori'] for u in urunler if u['kategori']])))
    return render_template('index.html', urunler=urunler, kategoriler=kategoriler, iban=IBAN_ADRESI, sahip=HESAP_SAHIBI)

@app.route('/ara')
def ara():
    q = request.args.get('q', '').strip()
    conn = get_db()
    cur = conn.cursor()
    if q:
        cur.execute("SELECT id, baslik, fiyat, eski_fiyat, img, detay, kategori, cok_satan, stok FROM urunler WHERE baslik ILIKE %s OR detay ILIKE %s", (f'%{q}%', f'%{q}%'))
    else:
        cur.execute("SELECT id, baslik, fiyat, eski_fiyat, img, detay, kategori, cok_satan, stok FROM urunler ORDER BY id DESC")
    urunler = cur.fetchall()
    conn.close()
    kategoriler = sorted(list(set([u['kategori'] for u in urunler if u['kategori']])))
    return render_template('index.html', urunler=urunler, kategoriler=kategoriler, iban=IBAN_ADRESI, sahip=HESAP_SAHIBI, arama=q)

@app.route('/urun/<int:id>')
def urun_detay(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, baslik, fiyat, eski_fiyat, img, detay, kategori, cok_satan, stok FROM urunler WHERE id=%s", (id,))
    urun = cur.fetchone()
    conn.close()
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
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO iletisim (ad, email, mesaj, tarih) VALUES (%s,%s,%s,%s)", (ad, email, mesaj, tarih))
            conn.commit()
            conn.close()
            return render_template('basarili.html', mesaj="Mesajınız başarıyla gönderildi. En kısa sürede dönüş yapacağız.")
    return render_template('iletisim.html')

@app.route('/kupon-kontrol', methods=['POST'])
def kupon_kontrol():
    kod = request.get_json().get('kod', '').upper()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT oran FROM kuponlar WHERE kod=%s", (kod,))
    res = cur.fetchone()
    conn.close()
    if res:
        return jsonify({"ok": True, "oran": res['oran']})
    return jsonify({"ok": False})

@app.route('/siparis-ver', methods=['POST'])
def siparis_ver():
    data = request.get_json()
    sepet = data.get('sepet', [])
    if not sepet:
        return jsonify({"hata": "Sepet boş"}), 400

    conn = get_db()
    cur = conn.cursor()
    for item in sepet:
        cur.execute("SELECT stok FROM urunler WHERE baslik=%s", (item['ad'],))
        urun = cur.fetchone()
        if not urun or urun['stok'] < item['adet']:
            conn.close()
            return jsonify({"hata": f"{item['ad']} ürününden yeterli stok yok!"}), 400
    for item in sepet:
        cur.execute("UPDATE urunler SET stok = stok - %s WHERE baslik=%s", (item['adet'], item['ad']))
    tarih = datetime.now().strftime("%d.%m.%Y %H:%M")
    urunler_str = ", ".join([f"{x['ad']} x{x['adet']}" for x in sepet])
    toplam = data.get('toplam', 0)
    musteri = data['musteri']
    cur.execute("INSERT INTO siparisler (ad, tel, adres, urunler, toplam, tarih, kargo_no) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (musteri['ad'], musteri['tel'], musteri['adres'], urunler_str, toplam, tarih, ''))
    sip_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return jsonify({"id": sip_id})

@app.route('/siparis-detay/<int:id>')
def siparis_detay(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM siparisler WHERE id=%s", (id,))
    sip = cur.fetchone()
    conn.close()
    if not sip:
        return "Sipariş bulunamadı", 404
    return render_template('siparis_detay.html', siparis=sip)

@app.route('/panel')
def panel():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM urunler ORDER BY id DESC")
    urunler = cur.fetchall()
    cur.execute("SELECT * FROM siparisler ORDER BY id DESC")
    siparisler = cur.fetchall()
    cur.execute("SELECT * FROM kuponlar")
    kuponlar = cur.fetchall()
    cur.execute("SELECT * FROM iletisim ORDER BY id DESC")
    iletisimler = cur.fetchall()
    conn.close()
    stats = {
        "toplam_siparis": len(siparisler),
        "ciro": sum([s['toplam'] for s in siparisler]),
        "toplam_urun": len(urunler),
        "toplam_mesaj": len(iletisimler)
    }
    return render_template('panel.html', urunler=urunler, siparisler=siparisler, kuponlar=kuponlar, iletisimler=iletisimler, stats=stats)

@app.route('/grafik-verisi')
def grafik_verisi():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT DATE(tarih) as gun, COUNT(*) as adet, SUM(toplam) as ciro
        FROM siparisler
        WHERE tarih >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY DATE(tarih)
        ORDER BY gun
    """)
    data = cur.fetchall()
    conn.close()
    gunler = [d['gun'] for d in data]
    adetler = [d['adet'] for d in data]
    cirolar = [d['ciro'] or 0 for d in data]
    return jsonify({"gunler": gunler, "adetler": adetler, "cirolar": cirolar})

@app.route('/urun-ekle', methods=['POST'])
def urun_ekle():
    cs = 1 if request.form.get('cok_satan') == '1' else 0
    stok = int(request.form.get('stok', 0))
    img_url = request.form.get('img', '')
    if 'resim' in request.files:
        file = request.files['resim']
        if file and file.filename and allowed_file(file.filename):
            try:
                img_url = upload_to_cloudinary(file)
            except Exception as e:
                print(f"Cloudinary yükleme hatası: {e}")
                img_url = ''
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO urunler (baslik, fiyat, eski_fiyat, img, detay, kategori, cok_satan, stok) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (request.form['baslik'], request.form['fiyat'], request.form.get('eski_fiyat', 0), img_url,
                 request.form['detay'], request.form['kategori'], cs, stok))
    conn.commit()
    conn.close()
    return redirect(url_for('panel'))

@app.route('/urun-duzenle/<int:id>', methods=['POST'])
def urun_duzenle(id):
    cs = 1 if request.form.get('cok_satan') == '1' else 0
    stok = int(request.form.get('stok', 0))
    img_url = request.form.get('img', '')
    if 'resim' in request.files:
        file = request.files['resim']
        if file and file.filename and allowed_file(file.filename):
            try:
                img_url = upload_to_cloudinary(file)
            except Exception as e:
                print(f"Cloudinary yükleme hatası: {e}")
                img_url = ''
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE urunler SET baslik=%s, fiyat=%s, eski_fiyat=%s, img=%s, detay=%s, kategori=%s, cok_satan=%s, stok=%s WHERE id=%s",
                (request.form['baslik'], request.form['fiyat'], request.form.get('eski_fiyat', 0), img_url,
                 request.form['detay'], request.form['kategori'], cs, stok, id))
    conn.commit()
    conn.close()
    return redirect(url_for('panel'))

@app.route('/kargo-guncelle/<int:id>', methods=['POST'])
def kargo_guncelle(id):
    kargo_no = request.form.get('kargo_no', '').strip()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE siparisler SET kargo_no=%s WHERE id=%s", (kargo_no, id))
    conn.commit()
    conn.close()
    return redirect(url_for('panel'))

@app.route('/kupon-ekle', methods=['POST'])
def kupon_ekle():
    kod = request.form['kod'].upper()
    oran = request.form['oran']
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO kuponlar (kod, oran) VALUES (%s,%s) ON CONFLICT (kod) DO UPDATE SET oran=EXCLUDED.oran", (kod, oran))
    conn.commit()
    conn.close()
    return redirect(url_for('panel'))

@app.route('/kupon-sil/<int:id>')
def kupon_sil(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM kuponlar WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('panel'))

@app.route('/siparis-sorgula/<int:id>')
def siparis_sorgula(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM siparisler WHERE id=%s", (id,))
    res = cur.fetchone()
    conn.close()
    if res:
        return jsonify({"ok": True, "ad": res['ad'], "durum": res['durum'], "toplam": res['toplam'], "urunler": res['urunler']})
    return jsonify({"ok": False})

@app.route('/durum-guncelle/<int:id>', methods=['POST'])
def durum_guncelle(id):
    durum = request.form.get('durum')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE siparisler SET durum=%s WHERE id=%s", (durum, id))
    conn.commit()
    conn.close()
    return redirect(url_for('panel'))

@app.route('/urun-sil/<int:id>')
def urun_sil(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM urunler WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('panel'))

@app.route('/siparis-sil/<int:id>')
def siparis_sil(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM siparisler WHERE id=%s", (id,))
    conn.commit()
    conn.close()
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