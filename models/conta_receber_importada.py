from datetime import datetime
from database import db


class ContaReceberImportada(db.Model):
    __tablename__ = "contas_receber_importadas"

    id = db.Column(db.Integer, primary_key=True)

    numero_fatura = db.Column(db.String(50))
    cliente = db.Column(db.String(200))
    telefone = db.Column(db.String(80))
    email = db.Column(db.String(180))

    plano_contas = db.Column(db.String(150))
    categoria = db.Column(db.String(150))
    setor = db.Column(db.String(40))
    # GERAL, ASSISTÊNCIA ou LOGÍSTICA

    cobranca = db.Column(db.String(100))

    data_documento = db.Column(db.DateTime)
    data_vencimento = db.Column(db.DateTime)
    data_pagamento = db.Column(db.DateTime)

    valor = db.Column(db.Numeric(12, 2), default=0)
    juros = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), default=0)

    pago = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(30), default="PENDENTE")

    observacoes = db.Column(db.Text)

    mes = db.Column(db.Integer)
    ano = db.Column(db.Integer)

    # =====================================================
    # CONCILIAÇÃO / CONTROLE DE IMPORTAÇÃO
    # =====================================================
    # Usado para impedir duplicidade entre relatório de vencimento
    # e relatório de recebimento/pagamento.
    chave_conciliacao = db.Column(db.String(255), index=True)

    # Exemplo: VENCIMENTO, RECEBIMENTO, MANUAL, IMPORTACAO
    origem_importacao = db.Column(db.String(50), default="VENCIMENTO")

    importado_em = db.Column(db.DateTime, default=datetime.utcnow)