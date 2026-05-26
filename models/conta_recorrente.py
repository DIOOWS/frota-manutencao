from datetime import datetime
from database import db


class ContaRecorrente(db.Model):
    __tablename__ = "contas_recorrentes"

    id = db.Column(db.Integer, primary_key=True)

    descricao = db.Column(db.String(200), nullable=False)
    fornecedor_funcionario = db.Column(db.String(200))
    plano_contas = db.Column(db.String(150))
    categoria = db.Column(db.String(150))
    setor = db.Column(db.String(40), default="GERAL")

    valor = db.Column(db.Numeric(12, 2), default=0)

    # Dia fixo do mês em que a conta vence.
    # Exemplo: aluguel todo dia 10.
    dia_vencimento = db.Column(db.Integer, nullable=False)

    # A partir de qual data/mês essa recorrência começa a gerar contas.
    data_inicio = db.Column(db.Date, nullable=False)

    # Opcional: quando a recorrência deve parar.
    data_fim = db.Column(db.Date)

    ativo = db.Column(db.Boolean, default=True)
    observacoes = db.Column(db.Text)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)