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

    # Mantido por compatibilidade com os dados antigos.
    filhos = db.relationship(
        "EvidenciaCampoFilho",
        backref="campo_pai",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="EvidenciaCampoFilho.ordem.asc(), EvidenciaCampoFilho.id.asc()",
    )

    # Nova relação: imagens pertencem diretamente ao campo pai.
    imagens = db.relationship(
        "EvidenciaImagem",
        backref="campo_pai",
        foreign_keys="EvidenciaImagem.campo_pai_id",
        lazy=True,
        order_by="EvidenciaImagem.ordem.asc(), EvidenciaImagem.id.asc()",
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

    # Mantido por compatibilidade com fotos antigas.
    imagens = db.relationship(
        "EvidenciaImagem",
        backref="campo_filho",
        foreign_keys="EvidenciaImagem.campo_filho_id",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="EvidenciaImagem.ordem.asc(), EvidenciaImagem.id.asc()",
    )


class EvidenciaTipoFoto(db.Model):
    __tablename__ = "evidencias_tipos_foto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False, unique=True)
    ativo = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class EvidenciaImagem(db.Model):
    __tablename__ = "evidencias_imagens"

    id = db.Column(db.Integer, primary_key=True)

    # Antigo vínculo. Agora é opcional para não perder histórico.
    campo_filho_id = db.Column(db.Integer, db.ForeignKey("evidencias_campos_filho.id"), nullable=True)

    # Novo vínculo principal.
    campo_pai_id = db.Column(db.Integer, db.ForeignKey("evidencias_campos_pai.id"), nullable=True, index=True)

    # Dropdown cadastrado. Ex: Antes, Depois, Finalizado, Avaria.
    tipo_foto = db.Column(db.String(80), nullable=True, index=True)

    imagem_url = db.Column(db.Text, nullable=False)
    public_id = db.Column(db.String(255), nullable=True)
    caminho_local = db.Column(db.String(500), nullable=True)
    nome_original = db.Column(db.String(255), nullable=True)
    legenda = db.Column(db.String(255), nullable=True)
    ordem = db.Column(db.Integer, default=0)

    enviado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def tipo_resolvido(self):
        if self.tipo_foto:
            return self.tipo_foto
        if self.campo_filho:
            return self.campo_filho.nome
        return "Sem tipo"


class EvidenciaTabelaControle(db.Model):
    __tablename__ = "evidencias_tabelas_controle"

    id = db.Column(db.Integer, primary_key=True)
    campo_pai_id = db.Column(db.Integer, db.ForeignKey("evidencias_campos_pai.id"), nullable=False, index=True)
    titulo = db.Column(db.String(180), nullable=False)
    ativa = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campo_pai = db.relationship("EvidenciaCampoPai", backref=db.backref("tabela_controle", uselist=False, cascade="all, delete-orphan"))

    colunas = db.relationship(
        "EvidenciaTabelaColuna",
        backref="tabela",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="EvidenciaTabelaColuna.ordem.asc(), EvidenciaTabelaColuna.id.asc()",
    )

    linhas = db.relationship(
        "EvidenciaTabelaLinha",
        backref="tabela",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="EvidenciaTabelaLinha.ordem.asc(), EvidenciaTabelaLinha.id.asc()",
    )


class EvidenciaTabelaColuna(db.Model):
    __tablename__ = "evidencias_tabelas_colunas"

    id = db.Column(db.Integer, primary_key=True)
    tabela_id = db.Column(db.Integer, db.ForeignKey("evidencias_tabelas_controle.id"), nullable=False, index=True)
    grupo = db.Column(db.String(120), nullable=True)
    nome = db.Column(db.String(120), nullable=False)
    tipo = db.Column(db.String(40), default="texto")
    cor = db.Column(db.String(30), default="padrao")
    largura = db.Column(db.Integer, default=16)
    ordem = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    celulas = db.relationship(
        "EvidenciaTabelaCelula",
        backref="coluna",
        cascade="all, delete-orphan",
        lazy=True,
    )


class EvidenciaTabelaLinha(db.Model):
    __tablename__ = "evidencias_tabelas_linhas"

    id = db.Column(db.Integer, primary_key=True)
    tabela_id = db.Column(db.Integer, db.ForeignKey("evidencias_tabelas_controle.id"), nullable=False, index=True)
    rotulo = db.Column(db.String(120), nullable=False)
    ordem = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    celulas = db.relationship(
        "EvidenciaTabelaCelula",
        backref="linha",
        cascade="all, delete-orphan",
        lazy=True,
    )


class EvidenciaTabelaCelula(db.Model):
    __tablename__ = "evidencias_tabelas_celulas"

    id = db.Column(db.Integer, primary_key=True)
    linha_id = db.Column(db.Integer, db.ForeignKey("evidencias_tabelas_linhas.id"), nullable=False, index=True)
    coluna_id = db.Column(db.Integer, db.ForeignKey("evidencias_tabelas_colunas.id"), nullable=False, index=True)
    valor = db.Column(db.Text, nullable=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("linha_id", "coluna_id", name="uq_evidencia_celula_linha_coluna"),
    )


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
