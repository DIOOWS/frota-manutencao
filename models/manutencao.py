from database import db

class Manutencao(db.Model):
    __tablename__ = "manutencoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    data = db.Column(db.Date)
    numero_frota = db.Column(db.String)
    bau = db.Column(db.String)
    tipo_veiculo = db.Column(db.String)
    tipo_servico = db.Column(db.String)
    tipo_atendimento = db.Column(db.String)
    tipo_manutencao = db.Column(db.String)
    status = db.Column(db.String)
    observacao = db.Column(db.String)
    cliente = db.Column(db.String)
    os = db.Column(db.String(50))