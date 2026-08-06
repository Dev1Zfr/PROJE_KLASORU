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
    enerji_me = db.Column(db.Float, default=0.0) # Mcal/kg Enerji
    protein_hp = db.Column(db.Float, default=0.0) # % Ham Protein
    kuru_madde = db.Column(db.Float, default=0.0) # % Kuru Madde (Kaba Yem Oranı)

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
    elif not admin_user.is_admin:
        admin_user.is_admin = True
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
            hata = "Bu kullanıcı adı zaten kullanılıyor!"
        else:
            db.session.add(User(username=username, password=password, is_admin=False))
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html', hata=hata)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
@admin_required
def admin():
    kullanicilar = User.query.all()
    toplam_hayvan = Hayvan.query.count()
    mevcut_hayvan = Hayvan.query.filter_by(durum='Mevcut').count()
    satilan_hayvan = Hayvan.query.filter_by(durum='Satildi').count()
    
    toplam_satis_tutari = db.session.query(db.func.sum(Hayvan.satis_fiyati)).filter(Hayvan.durum == 'Satildi').scalar() or 0.0
    toplam_tahsilat = db.session.query(db.func.sum(OdemeGecmisi.tutar)).scalar() or 0.0
    toplam_kalan_alacak = max(0.0, toplam_satis_tutari - toplam_tahsilat)

    return render_template(
        'admin.html',
        kullanicilar=kullanicilar,
        toplam_hayvan=toplam_hayvan,
        mevcut_hayvan=mevcut_hayvan,
        satilan_hayvan=satilan_hayvan,
        toplam_satis_tutari=toplam_satis_tutari,
        toplam_tahsilat=toplam_tahsilat,
        toplam_kalan_alacak=toplam_kalan_alacak
    )

@app.route('/admin/kullanici-ekle', methods=['POST'])
@login_required
@admin_required
def admin_kullanici_ekle():
    username = request.form.get('username')
    password = request.form.get('password')
    is_admin = True if request.form.get('is_admin') else False
    if not User.query.filter_by(username=username).first():
        db.session.add(User(username=username, password=password, is_admin=is_admin))
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/kullanici-sil/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def kullanici_sil(user_id):
    user = User.query.get_or_404(user_id)
    if user.username != 'admin':
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/mevcut')
@login_required
def mevcut():
    hayvanlar = Hayvan.query.filter_by(durum='Mevcut').all()
    hayvanlar_sirali = sorted(hayvanlar, key=lambda x: x.gunluk_artis, reverse=True)
    return render_template('mevcut.html', hayvanlar=hayvanlar, hayvanlar_sirali=hayvanlar_sirali)

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
                db.session.flush()
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

@app.route('/toplu-satis', methods=['POST'])
@login_required
def toplu_satis():
    secilen_idleri = request.form.getlist('secilen_hayvanlar')
    toplam_fiyat = float(request.form.get('toplam_satis_fiyati', 0))
    alici_ad = request.form.get('alici_ad')
    alici_tel = request.form.get('alici_tel', '')
    
    if secilen_idleri:
        adet = len(secilen_idleri)
        hayvan_basi_fiyat = toplam_fiyat / adet
        for hid in secilen_idleri:
            hayvan = Hayvan.query.get(int(hid))
            if hayvan:
                hayvan.durum = 'Satildi'
                hayvan.satis_turu = 'Normal'
                hayvan.satis_fiyati = hayvan_basi_fiyat
                db.session.add(Hisse(hayvan_id=hayvan.id, hissedar_adi=alici_ad, hissedar_tel=alici_tel, toplam_borc=hayvan_basi_fiyat))
        db.session.commit()
    return redirect(url_for('satilanlar'))

@app.route('/satilanlar')
@login_required
def satilanlar():
    q = request.args.get('q', '').strip()
    hisse_sorgu = Hisse.query
    if q:
        hisse_sorgu = hisse_sorgu.filter((Hisse.hissedar_adi.ilike(f'%{q}%')) | (Hisse.hissedar_tel.ilike(f'%{q}%')))
    
    hisseler = hisse_sorgu.all()
    kurbanlar = Hayvan.query.filter_by(durum='Satildi', satis_turu='Kurban').order_by(Hayvan.kesim_sirasi.asc()).all()
    normal_satilanlar = Hayvan.query.filter_by(durum='Satildi', satis_turu='Normal').all()
    return render_template('satilanlar.html', kurbanlar=kurbanlar, normal_satilanlar=normal_satilanlar, arama_hisseleri=hisseler, arama_kelimesi=q)

# DÜZELTİLEN SATIŞ ROTA VE FORM İŞLEMLERİ
@app.route('/satis-yap/<int:id>', methods=['GET', 'POST'])
@login_required
def satis_yap(id):
    hayvan = Hayvan.query.get_or_404(id)
    if request.method == 'POST':
        satis_turu = request.form.get('satis_turu', 'Normal')
        toplam_fiyat = float(request.form.get('satis_fiyati') or 0)
        hayvan.satis_turu = satis_turu
        hayvan.satis_fiyati = toplam_fiyat
        hayvan.randiman = float(request.form.get('randiman') or 55)
        hayvan.durum = 'Satildi'
        
        if request.form.get('kesim_sirasi'):
            hayvan.kesim_sirasi = int(request.form.get('kesim_sirasi'))
        
        Hisse.query.filter_by(hayvan_id=hayvan.id).delete()
        
        if satis_turu == 'Kurban':
            hisse_fiyati = round(toplam_fiyat / 7.0, 2)
            for i in range(1, 8):
                ad = request.form.get(f'hissedar_ad_{i}')
                tel = request.form.get(f'hissedar_tel_{i}')
                if ad:
                    db.session.add(Hisse(hayvan_id=hayvan.id, hisse_sira=i, hissedar_adi=ad, hissedar_tel=tel, toplam_borc=hisse_fiyati))
        else:
            ad = request.form.get('alici_ad') or 'İsimsiz Müşteri'
            tel = request.form.get('alici_tel') or ''
            db.session.add(Hisse(hayvan_id=hayvan.id, hissedar_adi=ad, hissedar_tel=tel, toplam_borc=toplam_fiyat))
            
        db.session.commit()
        return redirect(url_for('satilanlar'))
    return render_template('satis_detay.html', hayvan=hayvan)

@app.route('/odeme-ekle/<int:hisse_id>', methods=['POST'])
@login_required
def odeme_ekle(hisse_id):
    hisse = Hisse.query.get_or_404(hisse_id)
    ek_odeme = float(request.form.get('ek_odeme') or 0)
    not_aciklama = request.form.get('aciklama_not', '')
    
    yeni_odeme = OdemeGecmisi(hisse_id=hisse.id, tutar=ek_odeme, aciklama_not=not_aciklama)
    db.session.add(yeni_odeme)
    db.session.commit()
    return redirect(request.referrer or url_for('satilanlar'))

# RASYON YÖNETİMİ & YEM STOK ROTALARI
@app.route('/rasyon')
@login_required
def rasyon():
    yemler = Yem.query.all()
    return render_template('rasyon.html', yemler=yemler)

@app.route('/rasyon/yem-ekle', methods=['POST'])
@login_required
def yem_ekle():
    yem_adi = request.form.get('yem_adi')
    stok_kg = float(request.form.get('stok_kg') or 0)
    enerji_me = float(request.form.get('enerji_me') or 0)
    protein_hp = float(request.form.get('protein_hp') or 0)
    kuru_madde = float(request.form.get('kuru_madde') or 0)
    
    yeni_yem = Yem(yem_adi=yem_adi, stok_kg=stok_kg, enerji_me=enerji_me, protein_hp=protein_hp, kuru_madde=kuru_madde)
    db.session.add(yeni_yem)
    db.session.commit()
    return redirect(url_for('rasyon'))

@app.route('/rasyon/yem-sil/<int:id>', methods=['POST'])
@login_required
def yem_sil(id):
    yem = Yem.query.get_or_404(id)
    db.session.delete(yem)
    db.session.commit()
    return redirect(url_for('rasyon'))

@app.route('/kesim-ekrani')
def kesim_ekrani():
    kurbanlar = Hayvan.query.filter_by(durum='Satildi', satis_turu='Kurban').order_by(Hayvan.kesim_sirasi.asc()).all()
    return render_template('kesim_ekrani.html', kurbanlar=kurbanlar)

@app.route('/sira-guncelle/<int:id>', methods=['POST'])
@login_required
def sira_guncelle(id):
    hayvan = Hayvan.query.get_or_404(id)
    hayvan.kesim_sirasi = int(request.form.get('kesim_sirasi'))
    hayvan.kesim_durumu = request.form.get('kesim_durumu')
    db.session.commit()
    return redirect(url_for('satilanlar'))

@app.route('/guncelle/<int:id>', methods=['POST'])
@login_required
def guncelle(id):
    hayvan = Hayvan.query.get_or_404(id)
    yeni_kilo = float(request.form['yeni_kg'])
    hayvan.guncel_kg = yeni_kilo
    db.session.add(KiloGecmisi(hayvan_id=hayvan.id, kilo=yeni_kilo))
    db.session.commit()
    return redirect(url_for('mevcut'))

@app.route('/gecmis/<int:id>')
@login_required
def gecmis(id):
    hayvan = Hayvan.query.get_or_404(id)
    tartimlar = KiloGecmisi.query.filter_by(hayvan_id=id).order_by(KiloGecmisi.tarih.desc()).all()
    return render_template('gecmis.html', hayvan=hayvan, tartimlar=tartimlar)

@app.route('/kaba-yem')
@login_required
def kaba_yem():
    return render_template('kaba_yem.html')

if __name__ == '__main__':
    app.run(debug=True)
