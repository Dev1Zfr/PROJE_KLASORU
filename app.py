import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

app = Flask(__name__)
app.secret_key = "123"

database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///ciftlik.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- MODELLER ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Yem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    yem_adi = db.Column(db.String(100), nullable=False)
    stok_kg = db.Column(db.Float, default=0.0)
    tuketimler = db.relationship('YemTuketim', backref='yem', lazy=True, cascade="all, delete-orphan")

class YemTuketim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    yem_id = db.Column(db.Integer, db.ForeignKey('yem.id'), nullable=False)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    harcanan_kg = db.Column(db.Float, nullable=False)
    aciklama = db.Column(db.String(200))

class KiloGecmisi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hayvan_id = db.Column(db.Integer, db.ForeignKey('hayvan.id'), nullable=False)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    kilo = db.Column(db.Float, nullable=False)

class OdemeGecmisi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hisse_id = db.Column(db.Integer, db.ForeignKey('hisse.id'), nullable=False)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    tutar = db.Column(db.Float, nullable=False)
    aciklama_not = db.Column(db.String(200))

class Hisse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hayvan_id = db.Column(db.Integer, db.ForeignKey('hayvan.id'), nullable=False)
    hisse_sira = db.Column(db.Integer, default=1)
    hissedar_adi = db.Column(db.String(100))
    hissedar_tel = db.Column(db.String(20))
    toplam_borc = db.Column(db.Float, default=0.0)
    odemeler = db.relationship('OdemeGecmisi', backref='hisse', lazy=True, cascade="all, delete-orphan")
    @property
    def toplam_odenen(self):
        return sum([o.tutar for o in self.odemeler])
    @property
    def kalan_borc(self):
        return round(max(0.0, self.toplam_borc - self.toplam_odenen), 2)

class Hayvan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kupe_no = db.Column(db.String(50), unique=True, nullable=False)
    grup_adi = db.Column(db.String(100), nullable=True)
    irk = db.Column(db.String(50), nullable=False)
    alis_kg = db.Column(db.Float, nullable=False)
    guncel_kg = db.Column(db.Float, nullable=False)
    alis_fiyati = db.Column(db.Float, nullable=False)
    alis_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    durum = db.Column(db.String(20), default='Mevcut')
    satis_turu = db.Column(db.String(20), default='Normal')
    satis_fiyati = db.Column(db.Float, nullable=True)
    kesim_sirasi = db.Column(db.Integer, nullable=True)
    kesim_durumu = db.Column(db.String(20), default='Bekliyor')
    tartimlar = db.relationship('KiloGecmisi', backref='hayvan', lazy=True, cascade="all, delete-orphan")
    hisseler = db.relationship('Hisse', backref='hayvan', lazy=True, cascade="all, delete-orphan")
    @property
    def gunluk_artis(self):
        gun_farki = (datetime.utcnow() - self.alis_tarihi).days
        if gun_farki == 0: gun_farki = 1
        artis = self.guncel_kg - self.alis_kg
        return round(artis / gun_farki, 3)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return "Bu sayfaya yalnızca yönetici erişebilir!", 403
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        db.session.add(User(username='admin', password='123', is_admin=True))
        db.session.commit()

# --- TEMEL ROTALAR ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user, remember=bool(request.form.get('hatirla')))
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/mevcut')
@login_required
def mevcut():
    hayvanlar = Hayvan.query.filter_by(durum='Mevcut').all()
    gruplar = {}
    for h in hayvanlar:
        g_adi = h.grup_adi if h.grup_adi else "Bireysel Kayıtlar"
        if g_adi not in gruplar: gruplar[g_adi] = []
        gruplar[g_adi].append(h)
    return render_template('mevcut.html', gruplar=gruplar, hayvanlar_sirali=sorted(hayvanlar, key=lambda x: x.gunluk_artis, reverse=True))

@app.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    if request.method == 'POST':
        irk, kg, fiyat = request.form['irk'], float(request.form['alis_kg']), float(request.form['alis_fiyati'])
        if request.form.get('kayit_turu') == 'Toplu':
            for i in range(1, int(request.form['adet']) + 1):
                y = Hayvan(kupe_no=f"{request.form['grup_adi']}-{i}", grup_adi=request.form['grup_adi'], irk=irk, alis_kg=kg, guncel_kg=kg, alis_fiyati=fiyat)
                db.session.add(y); db.session.flush(); db.session.add(KiloGecmisi(hayvan_id=y.id, kilo=kg))
        else:
            y = Hayvan(kupe_no=request.form['kupe_no'], grup_adi="Bireysel Kayıtlar", irk=irk, alis_kg=kg, guncel_kg=kg, alis_fiyati=fiyat)
            db.session.add(y); db.session.flush(); db.session.add(KiloGecmisi(hayvan_id=y.id, kilo=kg))
        db.session.commit()
        return redirect(url_for('mevcut'))
    return render_template('ekle.html')

# --- SATIŞ VE TAHSİLAT ---
@app.route('/satis-yap/<int:id>', methods=['GET', 'POST'])
@login_required
def satis_yap(id):
    hayvan = Hayvan.query.get_or_404(id)
    if request.method == 'POST':
        satis_turu = request.form.get('satis_turu')
        toplam_fiyat = float(request.form.get('satis_fiyati', 0))
        hayvan.satis_turu, hayvan.satis_fiyati, hayvan.durum = satis_turu, toplam_fiyat, 'Satildi'
        if request.form.get('kesim_sirasi'): hayvan.kesim_sirasi = int(request.form.get('kesim_sirasi'))
        
        if satis_turu == 'Kurban':
            for i in range(1, 8):
                if ad := request.form.get(f'hissedar_ad_{i}'):
                    db.session.add(Hisse(hayvan_id=hayvan.id, hisse_sira=i, hissedar_adi=ad, hissedar_tel=request.form.get(f'hissedar_tel_{i}'), toplam_borc=round(toplam_fiyat/7.0, 2)))
        else:
            db.session.add(Hisse(hayvan_id=hayvan.id, hissedar_adi=request.form.get('alici_ad'), hissedar_tel=request.form.get('alici_tel'), toplam_borc=toplam_fiyat))
        db.session.commit()
        return redirect(url_for('satilanlar'))
    return render_template('satis_detay.html', hayvan=hayvan)

@app.route('/satilanlar')
@login_required
def satilanlar():
    q = request.args.get('q', '').strip()
    kurbanlar = Hayvan.query.filter_by(durum='Satildi', satis_turu='Kurban').order_by(Hayvan.kesim_sirasi.asc()).all()
    normal = Hayvan.query.filter_by(durum='Satildi', satis_turu='Normal').all()
    hisseler = Hisse.query.filter(Hisse.hissedar_adi.ilike(f'%{q}%')).all() if q else []
    return render_template('satilanlar.html', kurbanlar=kurbanlar, normal_satilanlar=normal, arama_hisseleri=hisseler, q=q)

@app.route('/odeme-ekle/<int:hisse_id>', methods=['POST'])
@login_required
def odeme_ekle(hisse_id):
    db.session.add(OdemeGecmisi(hisse_id=hisse_id, tutar=float(request.form.get('ek_odeme', 0)), aciklama_not=request.form.get('aciklama_not', '')))
    db.session.commit()
    return redirect(request.referrer)

# --- KESİM EKRANI VE SIRALAMA ---
@app.route('/kesim-ekrani')
def kesim_ekrani():
    return render_template('kesim_ekrani.html', kurbanlar=Hayvan.query.filter_by(durum='Satildi', satis_turu='Kurban').order_by(Hayvan.kesim_sirasi.asc()).all())

@app.route('/kesim-sira-degistir/<int:id>/<yon>', methods=['POST'])
@login_required
def kesim_sira_degistir(id, yon):
    hayvan = Hayvan.query.get_or_404(id)
    kurbanlar = Hayvan.query.filter_by(durum='Satildi', satis_turu='Kurban').order_by(Hayvan.kesim_sirasi.asc()).all()
    try:
        idx = kurbanlar.index(hayvan)
        swap_idx = idx - 1 if yon == 'ust' else idx + 1
        if 0 <= swap_idx < len(kurbanlar):
            hayvan.kesim_sirasi, kurbanlar[swap_idx].kesim_sirasi = kurbanlar[swap_idx].kesim_sirasi, hayvan.kesim_sirasi
            db.session.commit()
    except: pass
    return redirect(request.referrer)

@app.route('/kesildi-isaretle/<int:id>', methods=['POST'])
@login_required
def kesildi_isaretle(id):
    Hayvan.query.get_or_404(id).kesim_durumu = 'Kesildi'
    db.session.commit()
    return redirect(request.referrer)

# --- RASYON YÖNETİMİ ---
@app.route('/rasyon')
@login_required
def rasyon():
    return render_template('rasyon.html', yemler=Yem.query.all(), tuketimler=YemTuketim.query.order_by(YemTuketim.tarih.desc()).limit(20).all())

@app.route('/rasyon/yem-ekle', methods=['POST'])
@login_required
def yem_ekle():
    db.session.add(Yem(yem_adi=request.form.get('yem_adi'), stok_kg=float(request.form.get('stok_kg', 0))))
    db.session.commit()
    return redirect(url_for('rasyon'))

@app.route('/rasyon/yem-harca', methods=['POST'])
@login_required
def yem_harca():
    yem = Yem.query.get_or_404(request.form.get('yem_id'))
    harcanan = float(request.form.get('harcanan_kg', 0))
    yem.stok_kg -= harcanan
    db.session.add(YemTuketim(yem_id=yem.id, harcanan_kg=harcanan, aciklama=request.form.get('aciklama')))
    db.session.commit()
    return redirect(url_for('rasyon'))

@app.route('/gecmis/<int:id>')
@login_required
def gecmis(id):
    return render_template('gecmis.html', hayvan=Hayvan.query.get_or_404(id), tartimlar=KiloGecmisi.query.filter_by(hayvan_id=id).order_by(KiloGecmisi.tarih.desc()).all())

@app.route('/guncelle/<int:id>', methods=['POST'])
@login_required
def guncelle(id):
    y = Hayvan.query.get_or_404(id)
    y.guncel_kg = float(request.form['yeni_kg'])
    db.session.add(KiloGecmisi(hayvan_id=y.id, kilo=y.guncel_kg))
    db.session.commit()
    return redirect(request.referrer)

@app.route('/kaba-yem')
def kaba_yem():
    return render_template('kaba_yem.html')

if __name__ == '__main__':
    app.run(debug=True)
