from datetime import datetime
from database import db


class EvidenciaRegistro(db.Model):
    __tablename__ = "evidencias_registros"

    id = db.Column(db.Integer, primary_key=True)

    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    cliente_nome = db.Column(db.String(150), nullable=False)

    frota = db.Column(db.String(50), nullable=True)
    placa = db.Column(db.String(20), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    cliente = db.relationship("Cliente", backref="evidencias_registros")

    campos_pai = db.relationship(
        "EvidenciaCampoPai",
        backref="registro",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="EvidenciaCampoPai.ordem.asc(), EvidenciaCampoPai.id.asc()",
    )

    def identificador(self):
        if self.frota:
            return f"Frota {self.frota}"
        if self.placa:
            return f"Placa {self.placa}"
        return "Sem identificação"


class EvidenciaCampoPai(db.Model):
    __tablename__ = "evidencias_campos_pai"

    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey("evidencias_registros.id"), nullable=False)

    nome = db.Column(db.String(180), nullable=False)
    ordem = db.Column(db.Integer, default=0)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    filhos = db.relationship(
        "EvidenciaCampoFilho",
        backref="campo_pai",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="EvidenciaCampoFilho.ordem.asc(), EvidenciaCampoFilho.id.asc()",
    )


class EvidenciaCampoFilho(db.Model):
    __tablename__ = "evidencias_campos_filho"

    id = db.Column(db.Integer, primary_key=True)
    campo_pai_id = db.Column(db.Integer, db.ForeignKey("evidencias_campos_pai.id"), nullable=False)

    nome = db.Column(db.String(180), nullable=False)
    ordem = db.Column(db.Integer, default=0)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    imagens = db.relationship(
        "EvidenciaImagem",
        backref="campo_filho",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="EvidenciaImagem.ordem.asc(), EvidenciaImagem.id.asc()",
    )


class EvidenciaImagem(db.Model):
    __tablename__ = "evidencias_imagens"

    id = db.Column(db.Integer, primary_key=True)
    campo_filho_id = db.Column(db.Integer, db.ForeignKey("evidencias_campos_filho.id"), nullable=False)

    imagem_url = db.Column(db.Text, nullable=False)
    public_id = db.Column(db.String(255), nullable=True)
    caminho_local = db.Column(db.String(500), nullable=True)
    nome_original = db.Column(db.String(255), nullable=True)
    legenda = db.Column(db.String(255), nullable=True)
    ordem = db.Column(db.Integer, default=0)

    enviado_em = db.Column(db.DateTime, default=datetime.utcnow)



class EvidenciaLinkPublico(db.Model):
    __tablename__ = "evidencias_links_publicos"

    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey("evidencias_registros.id"), nullable=False)

    token = db.Column(db.String(120), unique=True, nullable=False, index=True)
    ativo = db.Column(db.Boolean, default=True)

    permitir_excel = db.Column(db.Boolean, default=True)
    permitir_zip = db.Column(db.Boolean, default=True)

    criado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    expira_em = db.Column(db.DateTime, nullable=True)
    ultimo_acesso_em = db.Column(db.DateTime, nullable=True)

    registro = db.relationship("EvidenciaRegistro", backref="links_publicos")

    def esta_expirado(self):
        if not self.expira_em:
            return False
        return datetime.utcnow() > self.expira_em

    def esta_disponivel(self):
        return bool(self.ativo) and not self.esta_expirado()
