from datetime import datetime
from database import db


class ContaRadarFinanceiro(db.Model):
    __tablename__ = "contas_radar_financeiro"

    id = db.Column(db.Integer, primary_key=True)

    descricao = db.Column(db.String(255), nullable=False)
    fornecedor = db.Column(db.String(200))
    categoria = db.Column(db.String(150))
    setor = db.Column(db.String(50), default="ASSISTÊNCIA")

    valor = db.Column(db.Numeric(12, 2), default=0)

    data_vencimento = db.Column(db.DateTime)
    data_pagamento = db.Column(db.DateTime)

    status = db.Column(db.String(30), default="PENDENTE")
    # PENDENTE, PAGO, ADIADO, TRANSPORTADO, CANCELADO

    observacoes = db.Column(db.Text)

    parcela_atual = db.Column(db.Integer)
    total_parcelas = db.Column(db.Integer)

    recorrente = db.Column(db.Boolean, default=False)
    gerado_por_transporte = db.Column(db.Boolean, default=False)

    conta_origem_id = db.Column(db.Integer, db.ForeignKey("contas_radar_financeiro.id"))
    conta_origem = db.relationship(
        "ContaRadarFinanceiro",
        remote_side=[id],
        backref="parcelas_geradas"
    )

    mes = db.Column(db.Integer)
    ano = db.Column(db.Integer)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def esta_pendente(self):
        return self.status in ["PENDENTE", "ADIADO"]

    def esta_pago(self):
        return self.status == "PAGO"

    def esta_cancelado(self):
        return self.status == "CANCELADO"

    def nome_parcela(self):
        if self.parcela_atual and self.total_parcelas:
            return f"{self.parcela_atual}/{self.total_parcelas}"

        return "-"