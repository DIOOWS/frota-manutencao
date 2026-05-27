from database import db


class ProblemaManutencao(db.Model):
    __tablename__ = "problemas_manutencao"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    causa_id = db.Column(
        db.Integer,
        db.ForeignKey("causas_manutencao.id"),
        nullable=False
    )
    nome = db.Column(db.String(150), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)