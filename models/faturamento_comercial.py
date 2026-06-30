from datetime import datetime
from database import db


class FaturamentoComercial(db.Model):
    __tablename__ = "faturamento_comercial"

    id = db.Column(db.Integer, primary_key=True)

    cliente = db.Column(db.String(200), index=True)
    os = db.Column(db.String(50), index=True)
    nfse = db.Column(db.String(50), index=True)
    pedido_compras = db.Column(db.String(120))

    valor = db.Column(db.Numeric(12, 2), default=0)
    comissao = db.Column(db.Numeric(12, 2), default=0)

    data_emissao = db.Column(db.Date, index=True)
    vencimento_30 = db.Column(db.Date, index=True)
    vencimento_60 = db.Column(db.Date, index=True)
    vencimento_90 = db.Column(db.Date, index=True)

    status = db.Column(db.String(30), default="PENDENTE", index=True)
    tipo = db.Column(db.String(30), default="CONTRATO", index=True)
    comercial = db.Column(db.String(120), index=True)
    observacoes = db.Column(db.Text)

    pago = db.Column(db.Boolean, default=False, index=True)

    mes = db.Column(db.Integer, index=True)
    ano = db.Column(db.Integer, index=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
