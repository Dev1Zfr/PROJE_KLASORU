import os
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
    irk = db.Column(db.String(50), nullable=False)
    alis_kg = db.Column(db.Float, nullable=False)
    guncel_kg = db.Column(db.Float, nullable=False)
    alis_fiyati = db.Column(db.Float, nullable=False)
    alis_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
    durum = db.Column(db.String(20), default='Mevcut')
    satis_turu = db.Column(db.String(20), default='Normal')
    satis_fiyati = db.Column(db.Float, nullable=True)
    randiman = db.Column(db.Float, default=55.0)
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password='123'))
        db.session.commit()

# --- ROTALAR ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# 1. YENİ ANA EKRAN (3 BÜYÜK BUTON)
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# 2. MEVCUT HAYVANLAR LİSTESİ VE SIRALAMA EKRANI
@app.route('/mevcut')
@login_required
def mevcut():
    hayvanlar = Hayvan.query.filter_by(durum='Mevcut').all()
    # Kilo artışına göre en çoktan aza doğru sıralama
    hayvanlar_sirali = sorted(hayvanlar, key=lambda x: x.gunluk_artis, reverse=True)
    return render_template('mevcut.html', hayvanlar=hayvanlar, hayvanlar_sirali=hayvanlar_sirali)

# 3. YENİ TOPLU/TEKLİ HAYVAN ALIŞI
@app.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    if request.method == 'POST':
        kayit_turu = request.form.get('kayit_turu')
        irk = request.form['irk']
        alis_kg = float(request.form['alis_kg'])
        alis_fiyati = float(request.form['alis_fiyati'])
        
        if kayit_turu == 'Toplu':
            adet = int(request.form['adet'])
            grup_adi = request.form['grup_adi']
            for i in range(1, adet + 1):
                yeni_hayvan = Hayvan(
                    kupe_no=f"{grup_adi}-{i}",
                    irk=irk, alis_kg=alis_kg, guncel_kg=alis_kg, alis_fiyati=alis_fiyati
                )
                db.session.add(yeni_hayvan)
                db.session.flush() # ID'yi alabilmek için
                db.session.add(KiloGecmisi(hayvan_id=yeni_hayvan.id, kilo=alis_kg))
        else:
            kupe_no = request.form['kupe_no']
            yeni_hayvan = Hayvan(
                kupe_no=kupe_no, irk=irk, alis_kg=alis_kg, guncel_kg=alis_kg, alis_fiyati=alis_fiyati
            )
            db.session.add(yeni_hayvan)
            db.session.flush()
            db.session.add(KiloGecmisi(hayvan_id=yeni_hayvan.id, kilo=alis_kg))
            
        db.session.commit()
        return redirect(url_for('mevcut'))
    return render_template('ekle.html')

# TOPLU SATIŞ ROTASI
@app.route('/toplu-satis', methods=['POST'])
@login_required
def toplu_satis():
    secilen_idleri = request.form.getlist('secilen_hayvanlar')
    toplam_fiyat = float(request.form.get('toplam_satis_fiyati', 0))
    alici_ad = request.form.get('alici_ad')
    
    if secilen_idleri:
        adet = len(secilen_idleri)
        hayvan_basi_fiyat = toplam_fiyat / adet
        for hid in secilen_idleri:
            hayvan = Hayvan.query.get(int(hid))
            if hayvan:
                hayvan.durum = 'Satildi'
                hayvan.satis_turu = 'Normal'
                hayvan.satis_fiyati = hayvan_basi_fiyat
                db.session.add(Hisse(hayvan_id=hayvan.id, hissedar_adi=alici_ad, toplam_borc=hayvan_basi_fiyat))
        db.session.commit()
    return redirect(url_for('satilanlar'))

@app.route('/satilanlar')
@login_required
def satilanlar():
    kurbanlar = Hayvan.query.filter_by(durum='Satildi', satis_turu='Kurban').order_by(Hayvan.kesim_sirasi.asc()).all()
    normal_satilanlar = Hayvan.query.filter_by(durum='Satildi', satis_turu='Normal').all()
    return render_template('satilanlar.html', kurbanlar=kurbanlar, normal_satilanlar=normal_satilanlar)

@app.route('/guncelle/<int:id>', methods=['POST'])
@login_required
def guncelle(id):
    hayvan = Hayvan.query.get_or_404(id)
    yeni_kilo = float(request.form['yeni_kg'])
    hayvan.guncel_kg = yeni_kilo
    db.session.add(KiloGecmisi(hayvan_id=hayvan.id, kilo=yeni_kilo))
    db.session.commit()
    return redirect(url_for('mevcut'))

@app.route('/satis-yap/<int:id>', methods=['GET', 'POST'])
@login_required
def satis_yap(id):
    hayvan = Hayvan.query.get_or_404(id)
    if request.method == 'POST':
        satis_turu = request.form.get('satis_turu')
        toplam_fiyat = float(request.form.get('satis_fiyati', 0))
        hayvan.satis_turu = satis_turu
        hayvan.satis_fiyati = toplam_fiyat
        hayvan.durum = 'Satildi'
        
        if satis_turu == 'Kurban':
            hisse_fiyati = round(toplam_fiyat / 7.0, 2)
            for i in range(1, 8):
                ad = request.form.get(f'hissedar_ad_{i}')
                if ad:
                    db.session.add(Hisse(hayvan_id=hayvan.id, hisse_sira=i, hissedar_adi=ad, toplam_borc=hisse_fiyati))
        else:
            db.session.add(Hisse(hayvan_id=hayvan.id, hissedar_adi=request.form.get('alici_ad'), toplam_borc=toplam_fiyat))
            
        db.session.commit()
        return redirect(url_for('satilanlar'))
    return render_template('satis_detay.html', hayvan=hayvan)

if __name__ == '__main__':
    app.run(debug=True)
