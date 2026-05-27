from database import db


class CausaManutencao(db.Model):
    __tablename__ = "causas_manutencao"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(150), nullable=False, unique=True)
    ativo = db.Column(db.Boolean, default=True, nullable=False)

    problemas = db.relationship(
        "ProblemaManutencao",
        backref="causa_ref",
        lazy=True,
        cascade="all, delete-orphan"
    )