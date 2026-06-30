from database import db


class Manutencao(db.Model):
    __tablename__ = "manutencoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    data = db.Column(db.Date)
    data_saida = db.Column(db.Date)
    dtm = db.Column(db.Integer)

    numero_frota = db.Column(db.String)
    placa = db.Column(db.String(20))
    os = db.Column(db.String(50))
    bau = db.Column(db.String)
    tipo_veiculo = db.Column(db.String)
    tipo_servico = db.Column(db.String)
    tipo_atendimento = db.Column(db.String)
    tipo_manutencao = db.Column(db.String)
    status = db.Column(db.String)

    problema = db.Column(db.String)
    causa = db.Column(db.String)

    observacao = db.Column(db.String)
    cliente = db.Column(db.String)

    km_entrada = db.Column(db.String(50))
    km_imagem = db.Column(db.Text)

    imagens = db.Column(db.Text)