from database import db


class AfericaoTermometro(db.Model):
    __tablename__ = "afericoes_termometros"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    numero_frota = db.Column(db.String(50), nullable=False, index=True)
    os = db.Column(db.String(50), nullable=False, index=True)

    # PLACA / AMBIENTE
    tipo_termometro = db.Column(db.String(20), nullable=False, index=True)

    afericao = db.Column(db.String(50))
    data_afericao = db.Column(db.Date)
    # C / NC / NA
    status = db.Column(db.String(5))

    # 🔥 imagens da aferição (JSON com lista de URLs)
    imagens = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint(
            "numero_frota",
            "os",
            "tipo_termometro",
            name="uq_afericao_frota_os_tipo"
        ),
    )