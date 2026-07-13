from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "gizli_anahtar_degistir"
# Test için SQLite. Render'a atarken burayı PostgreSQL URI'si ile değiştireceksin.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ciftlik.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Veritabanı Modeli
class Hayvan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kupe_no = db.Column(db.String(50), unique=True, nullable=False)
    irk = db.Column(db.String(50), nullable=False)
    alis_kg = db.Column(db.Float, nullable=False)
    guncel_kg = db.Column(db.Float, nullable=False)
    alis_fiyati = db.Column(db.Float, nullable=False)
    alis_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    durum = db.Column(db.String(20), default='Mevcut') # Mevcut, Satildi

    @property
    def gunluk_artis(self):
        # Sisteme girdiği günden bugüne geçen zamanı hesapla
        gun_farki = (datetime.utcnow() - self.alis_tarihi).days
        if gun_farki == 0:
            gun_farki = 1 # Aynı gün 0'a bölünme hatasını önlemek için
        
        artis = self.guncel_kg - self.alis_kg
        return round(artis / gun_farki, 2)

# Veritabanını oluştur
with app.app_context():
    db.create_all()

# 1. Mevcut Hayvanlar / Satış Vitrini
@app.route('/')
def index():
    hayvanlar = Hayvan.query.filter_by(durum='Mevcut').all()
    return render_template('index.html', hayvanlar=hayvanlar)

# 2. Hayvan Alış (Ekleme)
@app.route('/ekle', methods=['GET', 'POST'])
def ekle():
    if request.method == 'POST':
        yeni_hayvan = Hayvan(
            kupe_no=request.form['kupe_no'],
            irk=request.form['irk'],
            alis_kg=float(request.form['alis_kg']),
            guncel_kg=float(request.form['alis_kg']), # İlk girişte güncel kg alış ile aynıdır
            alis_fiyati=float(request.form['alis_fiyati'])
        )
        db.session.add(yeni_hayvan)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('ekle.html')

# Güncel KG Güncelleme Rotası (Müşteri için günlük artışı tetikler)
@app.route('/guncelle/<int:id>', methods=['POST'])
def guncelle(id):
    hayvan = Hayvan.query.get_or_404(id)
    hayvan.guncel_kg = float(request.form['yeni_kg'])
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
