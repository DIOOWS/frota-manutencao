from datetime import datetime
from database import db


class LancamentoFinanceiro(db.Model):
    __tablename__ = "lancamentos_financeiros"

    id = db.Column(db.Integer, primary_key=True)

    data = db.Column(db.Date, nullable=False)

    tipo = db.Column(db.String(20), nullable=False)
    # RECEITA ou DESPESA

    categoria = db.Column(db.String(120), nullable=False)

    subcategoria = db.Column(db.String(120))

    setor = db.Column(db.String(100))
    # ASSISTÊNCIA, LOGÍSTICA, ADMINISTRATIVO, GERAL

    cliente = db.Column(db.String(150))

    descricao = db.Column(db.Text)

    valor = db.Column(db.Numeric(12, 2), nullable=False)

    status = db.Column(db.String(30), default="PENDENTE")
    # PENDENTE, PAGO, RECEBIDO, CANCELADO

    origem = db.Column(db.String(80))
    # EXERCÍCIO ATUAL, EXERCÍCIO ANTERIOR, MANUAL, IMPORTAÇÃO

    recorrente = db.Column(db.Boolean, default=False)

    mes = db.Column(db.Integer)

    ano = db.Column(db.Integer)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)