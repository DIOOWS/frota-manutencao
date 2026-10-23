from datetime import datetime
from database import db


class PainelTVConfig(db.Model):
    __tablename__ = "painel_tv_config"

    id = db.Column(db.Integer, primary_key=True)

    competencia = db.Column(
        db.String(7),
        unique=True,
        nullable=False
    )

    empresa = db.Column(
        db.String(100),
        nullable=False,
        default="EASY ASSISTÊNCIA"
    )

    meta_faturamento = db.Column(
        db.Numeric(14, 2),
        nullable=False,
        default=0
    )

    meta_servicos = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    segundos_tela = db.Column(
        db.Integer,
        nullable=False,
        default=15
    )

    avisos = db.Column(
        db.Text,
        nullable=False,
        default=""
    )

    atualizado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )