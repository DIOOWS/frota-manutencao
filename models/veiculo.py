from database import db  # 🔥 FALTOU ISSO

class Veiculo(db.Model):
    __tablename__ = "veiculo"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    placa = db.Column(db.String(20))