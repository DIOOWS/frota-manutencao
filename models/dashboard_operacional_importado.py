from database import db


class DashboardOperacionalImportado(db.Model):
    __tablename__ = "dashboard_operacional_importado"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    cliente = db.Column(db.String(255), index=True)
    cidade_uf = db.Column(db.String(255), index=True)

    entrada = db.Column(db.DateTime, index=True)
    pronto = db.Column(db.DateTime)
    saida = db.Column(db.DateTime)

    situacao = db.Column(db.String(255), index=True)
    veiculo = db.Column(db.String(255), index=True)
    defeito = db.Column(db.Text)
    tipo_servico = db.Column(db.String(120), index=True)
    marca = db.Column(db.String(120))

    frota_original = db.Column(db.String(255))
    frota_tratada = db.Column(db.String(20), index=True)

    km = db.Column(db.String(80))
    ano = db.Column(db.Integer, index=True)
    mes = db.Column(db.Integer, index=True)

    criado_em = db.Column(db.DateTime, server_default=db.func.now())
