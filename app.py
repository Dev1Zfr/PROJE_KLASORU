import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

app = Flask(__name__)
app.secret_key = "123"

# Veritabanı bağlantısı
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

class KiloGecmisi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hayvan_id = db.Column(db.Integer, db.ForeignKey('hayvan.id'), nullable=False)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    kilo = db.Column(db.Float, nullable=False)

class Hisse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hayvan_id = db.Column(db.Integer, db.ForeignKey('hayvan.id'), nullable=False)
    hissedar_adi = db.Column(db.String(100))
    hissedar_tel = db.Column(db.String(20))

class Hayvan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kupe_no = db.Column(db.String(50), unique=True, nullable=False)
    irk = db.Column(db.String(50), nullable=False)
    alis_kg = db.Column(db.Float, nullable=False)
    guncel_kg = db.Column(db.Float, nullable=False)
    alis_fiyati = db.Column(db.Float, nullable=False)
    alis_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Durumlar: 'Mevcut', 'Satildi'
    durum = db.Column(db.String(20), default='Mevcut')
    
    # Kurbanlık & Satış Özellikleri
    is_kurban = db.Column(db.Boolean, default=False)
    satis_fiyati = db.Column(db.Float, nullable=True)
    randiman = db.Column(db.Float, default=55.0) # Varsayılan randıman %55
    
    tartimlar = db.relationship('KiloGecmisi', backref='hayvan', lazy=True, cascade="all, delete-orphan")
    hisseler = db.relationship('Hisse', backref='hayvan', lazy=True, cascade="all, delete-orphan")

    @property
    def gunluk_artis(self):
        gun_farki = (datetime.utcnow() - self.alis_tarihi).days
        if gun_farki == 0:
            gun_farki = 1
        artis = self.guncel_kg - self.alis_kg
        return round(artis / gun_farki, 2)

    @property
    def karkas_et_kg(self):
        """Canlı Ağırlık * Randıman (%)"""
        if self.randiman:
            return round(self.guncel_kg * (self.randiman / 100.0), 1)
        return 0.0

    @property
    def hisse_basi_et(self):
        """Karkas Et / 7 Hisse"""
        return round(self.karkas_et_kg / 7.0, 1)

    @property
    def hisse_fiyati(self):
        """Satış Fiyatı / 7 Hisse"""
        if self.satis_fiyati:
            return round(self.satis_fiyati / 7.0, 2)
        return 0.0

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        yeni_admin = User(username='admin', password='123')
        db.session.add(yeni_admin)
        db.session.commit()

# --- ROTALAR ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    hata = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('index'))
        else:
            hata = "Hatalı kullanıcı adı veya şifre!"
    return render_template('login.html', hata=hata)

@app.route('/register', methods=['GET', 'POST'])
def register():
    hata = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            hata = "Bu kullanıcı adı zaten var!"
        else:
            yeni_kullanici = User(username=username, password=password)
            db.session.add(yeni_kullanici)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html', hata=hata)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# 1. MEVCUT HAYVANLAR SAYFASI
@app.route('/')
@login_required
def index():
    hayvanlar = Hayvan.query.filter_by(durum='Mevcut').all()
    return render_template('index.html', hayvanlar=hayvanlar)

# 2. HAYVAN ALIŞ (Ekleme) SAYFASI
@app.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    if request.method == 'POST':
        yeni_hayvan = Hayvan(
            kupe_no=request.form['kupe_no'],
            irk=request.form['irk'],
            alis_kg=float(request.form['alis_kg']),
            guncel_kg=float(request.form['alis_kg']),
            alis_fiyati=float(request.form['alis_fiyati'])
        )
        db.session.add(yeni_hayvan)
        db.session.commit()
        
        ilk_tartim = KiloGecmisi(hayvan_id=yeni_hayvan.id, kilo=yeni_hayvan.alis_kg)
        db.session.add(ilk_tartim)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('ekle.html')

# 3. SATILAN HAYVANLAR SAYFASI
@app.route('/satilanlar')
@login_required
def satilanlar():
    hayvanlar = Hayvan.query.filter_by(durum='Satildi').all()
    return render_template('satilanlar.html', hayvanlar=hayvanlar)

# KURBAN / SATIŞ DETAY & 7 HİSSE KAYIT SAYFASI
@app.route('/satis-yap/<int:id>', methods=['GET', 'POST'])
@login_required
def satis_yap(id):
    hayvan = Hayvan.query.get_or_404(id)
    if request.method == 'POST':
        hayvan.satis_fiyati = float(request.form.get('satis_fiyati', 0))
        hayvan.randiman = float(request.form.get('randiman', 55))
        hayvan.is_kurban = True if request.form.get('is_kurban') else False
        hayvan.durum = 'Satildi'
        
        # 7 Tane Hissedar Bilgisini Kaydet
        Hisse.query.filter_by(hayvan_id=hayvan.id).delete() # Eski kayıtları temizle
        for i in range(1, 8):
            ad = request.form.get(f'hissedar_ad_{i}')
            tel = request.form.get(f'hissedar_tel_{i}')
            if ad:
                yeni_hisse = Hisse(hayvan_id=hayvan.id, hissedar_adi=ad, hissedar_tel=tel)
                db.session.add(yeni_hisse)
                
        db.session.commit()
        return redirect(url_for('satilanlar'))
        
    return render_template('satis_detay.html', hayvan=hayvan)

@app.route('/guncelle/<int:id>', methods=['POST'])
@login_required
def guncelle(id):
    hayvan = Hayvan.query.get_or_404(id)
    yeni_kilo = float(request.form['yeni_kg'])
    hayvan.guncel_kg = yeni_kilo
    yeni_tartim = KiloGecmisi(hayvan_id=hayvan.id, kilo=yeni_kilo)
    db.session.add(yeni_tartim)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/gecmis/<int:id>')
@login_required
def gecmis(id):
    hayvan = Hayvan.query.get_or_404(id)
    tartimlar = KiloGecmisi.query.filter_by(hayvan_id=id).order_by(KiloGecmisi.tarih.desc()).all()
    return render_template('gecmis.html', hayvan=hayvan, tartimlar=tartimlar)

if __name__ == '__main__':
    app.run(debug=True)
