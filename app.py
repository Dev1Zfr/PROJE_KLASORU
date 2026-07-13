import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
# Gizli anahtar 123 yapıldı
app.secret_key = "123"

# Veritabanı bağlantı ayarı (Render için PostgreSQL, lokal için SQLite)
database_url = os.environ.get('DATABASE_URL')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///ciftlik.db'
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
    durum = db.Column(db.String(20), default='Mevcut')

    @property
    def gunluk_artis(self):
        gun_farki = (datetime.utcnow() - self.alis_tarihi).days
        if gun_farki == 0:
            gun_farki = 1
        artis = self.guncel_kg - self.alis_kg
        return round(artis / gun_farki, 2)

# Tabloları oluştur
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    hayvanlar = Hayvan.query.filter_by(durum='Mevcut').all()
    return render_template('index.html', hayvanlar=hayvanlar)

@app.route('/ekle', methods=['GET', 'POST'])
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
        return redirect(url_for('index'))
    return render_template('ekle.html')

@app.route('/guncelle/<int:id>', methods=['POST'])
def guncelle(id):
    hayvan = Hayvan.query.get_or_404(id)
    hayvan.guncel_kg = float(request.form['yeni_kg'])
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
