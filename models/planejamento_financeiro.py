from datetime import datetime

from database import db


class PlanejamentoFinanceiro(db.Model):
    __tablename__ = "planejamento_financeiro"

    id = db.Column(db.Integer, primary_key=True)

    # ID atual da conta importada. Pode mudar após limpar/reimportar.
    conta_id = db.Column(db.Integer, nullable=False)

    # Identificador estável usado para recuperar o planejamento após reimportação.
    chave_conta = db.Column(db.String(64), nullable=True, index=True)

    origem = db.Column(db.String(30), nullable=False, default="IMPORTADA")
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    status_planejamento = db.Column(
        db.String(30),
        nullable=False,
        default="PLANEJADA",
    )

    # Snapshot para preservar os dados básicos do que foi planejado.
    descricao_snapshot = db.Column(db.String(255), nullable=True)
    fornecedor_snapshot = db.Column(db.String(255), nullable=True)
    valor_snapshot = db.Column(db.Numeric(14, 2), nullable=True)
    vencimento_snapshot = db.Column(db.Date, nullable=True)
    observacao_snapshot = db.Column(db.Text, nullable=True)

    # Dados da decisão de pagamento. Mantém o valor original no snapshot
    # e registra quanto e quando a empresa pretende pagar.
    tipo_planejamento = db.Column(db.String(20), nullable=False, default="TOTAL")
    valor_planejado = db.Column(db.Numeric(14, 2), nullable=True)
    data_prevista = db.Column(db.Date, nullable=True)
    observacao_previsao = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "conta_id",
            "origem",
            "mes",
            "ano",
            name="uq_planejamento_financeiro_conta_origem_mes_ano",
        ),
        db.Index(
            "idx_planejamento_chave_competencia",
            "chave_conta",
            "origem",
            "mes",
            "ano",
        ),
    )
