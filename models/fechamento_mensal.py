from datetime import datetime
from database import db


class FechamentoMensal(db.Model):
    __tablename__ = "fechamentos_mensais"

    id = db.Column(db.Integer, primary_key=True)

    mes = db.Column(db.Integer, nullable=False)

    ano = db.Column(db.Integer, nullable=False)

    saldo_inicial = db.Column(db.Numeric(12, 2), default=0)

    total_entradas = db.Column(db.Numeric(12, 2), default=0)

    total_saidas = db.Column(db.Numeric(12, 2), default=0)

    lucro_mes = db.Column(db.Numeric(12, 2), default=0)

    saldo_final = db.Column(db.Numeric(12, 2), default=0)

    total_a_pagar = db.Column(db.Numeric(12, 2), default=0)

    total_a_receber = db.Column(db.Numeric(12, 2), default=0)

    margem_operacional = db.Column(db.Numeric(8, 2), default=0)

    fechado = db.Column(db.Boolean, default=False)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)