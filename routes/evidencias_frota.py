import os
import re
import zipfile
import tempfile
import urllib.request
import secrets
from io import BytesIO
from datetime import datetime, timedelta
from decimal import Decimal

import cloudinary.uploader
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    flash,
    abort,
    send_file,
    current_app,
    url_for,
)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from database import db
from models.cliente import Cliente
from models.usuario import Usuario
from models.evidencia_frota import (
    EvidenciaRegistro,
    EvidenciaCampoPai,
    EvidenciaCampoFilho,
    EvidenciaImagem,
    EvidenciaLinkPublico,
)


evidencias_frota_bp = Blueprint(
    "evidencias_frota",
    __name__,
    url_prefix="/gestao/evidencias",
)


# =========================================================
# HELPERS
# =========================================================

def usuario_logado():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return Usuario.query.get(user_id)


def usuario_eh_admin_ou_gestao():
    return session.get("user_role") in ["admin", "gestao", "gestor"]


def exigir_login():
    if not session.get("user_id"):
        return redirect("/login")
    return None


def texto(valor):
    return "" if valor is None else str(valor).strip()


def normalizar_texto(valor):
    valor = texto(valor)
    if not valor:
        return ""
    return " ".join(valor.split()).upper()


def limpar_nome_arquivo(valor):
    valor = normalizar_texto(valor) or "SEM_NOME"
    valor = valor.replace("/", "-").replace("\\", "-")
    valor = re.sub(r"[^A-Z0-9_\-\. ]+", "", valor)
    valor = valor.replace(" ", "_")
    return valor[:90] or "SEM_NOME"


def cliente_permitido(cliente_id=None, cliente_nome=None):
    if usuario_eh_admin_ou_gestao():
        return True

    usuario = usuario_logado()
    if not usuario or not getattr(usuario, "cliente", None):
        return False

    if cliente_id and usuario.cliente_id == int(cliente_id):
        return True

    return normalizar_texto(usuario.cliente.nome) == normalizar_texto(cliente_nome)


def aplicar_permissao_registros(query):
    if usuario_eh_admin_ou_gestao():
        return query

    usuario = usuario_logado()
    if not usuario or not getattr(usuario, "cliente", None):
        return query.filter(EvidenciaRegistro.id == 0)

    return query.filter(
        or_(
            EvidenciaRegistro.cliente_id == usuario.cliente_id,
            db.func.upper(EvidenciaRegistro.cliente_nome) == normalizar_texto(usuario.cliente.nome),
        )
    )


def obter_registro_ou_404(registro_id):
    registro = EvidenciaRegistro.query.get_or_404(registro_id)
    if not cliente_permitido(registro.cliente_id, registro.cliente_nome):
        abort(403)
    return registro


def obter_pai_ou_404(pai_id):
    pai = EvidenciaCampoPai.query.get_or_404(pai_id)
    obter_registro_ou_404(pai.registro_id)
    return pai


def obter_filho_ou_404(filho_id):
    filho = EvidenciaCampoFilho.query.get_or_404(filho_id)
    obter_registro_ou_404(filho.campo_pai.registro_id)
    return filho


def obter_imagem_ou_404(imagem_id):
    imagem = EvidenciaImagem.query.get_or_404(imagem_id)
    obter_registro_ou_404(imagem.campo_filho.campo_pai.registro_id)
    return imagem


def cloudinary_configurado():
    return all([
        os.getenv("CLOUD_NAME"),
        os.getenv("API_KEY"),
        os.getenv("API_SECRET"),
    ])


def salvar_imagem_evidencia(arquivo, registro, pai, filho):
    if not arquivo or not arquivo.filename:
        return None

    nome_original = secure_filename(arquivo.filename) or "imagem.jpg"

    if cloudinary_configurado():
        folder = "/".join([
            "easy_control",
            "evidencias",
            limpar_nome_arquivo(registro.cliente_nome),
            limpar_nome_arquivo(registro.frota or registro.placa or "veiculo"),
            limpar_nome_arquivo(pai.nome),
            limpar_nome_arquivo(filho.nome),
        ])

        upload = cloudinary.uploader.upload(
            arquivo,
            folder=folder,
            resource_type="image",
        )

        return {
            "url": upload.get("secure_url"),
            "public_id": upload.get("public_id"),
            "caminho_local": None,
            "nome_original": nome_original,
        }

    base_upload = current_app.config.get("UPLOAD_FOLDER") or os.path.join(
        current_app.root_path,
        "static",
        "uploads",
    )

    pasta_relativa = os.path.join(
        "evidencias",
        limpar_nome_arquivo(registro.cliente_nome),
        limpar_nome_arquivo(registro.frota or registro.placa or "veiculo"),
        limpar_nome_arquivo(pai.nome),
        limpar_nome_arquivo(filho.nome),
    )

    pasta_destino = os.path.join(base_upload, pasta_relativa)
    os.makedirs(pasta_destino, exist_ok=True)

    nome_final = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{nome_original}"
    caminho_final = os.path.join(pasta_destino, nome_final)
    arquivo.save(caminho_final)

    url = f"/static/uploads/{pasta_relativa.replace(os.sep, '/')}/{nome_final}"

    return {
        "url": url,
        "public_id": None,
        "caminho_local": caminho_final,
        "nome_original": nome_original,
    }


def clientes_para_select():
    if usuario_eh_admin_ou_gestao():
        return Cliente.query.order_by(Cliente.nome.asc()).all()

    usuario = usuario_logado()
    if usuario and getattr(usuario, "cliente", None):
        return [usuario.cliente]

    return []


def contar_imagens_registro(registro):
    total = 0
    for pai in registro.campos_pai:
        for filho in pai.filhos:
            total += len(filho.imagens)
    return total


def registros_filtrados():
    cliente_id = request.args.get("cliente_id", type=int)
    busca = texto(request.args.get("busca"))
    campo = texto(request.args.get("campo"))

    query = aplicar_permissao_registros(EvidenciaRegistro.query)

    if cliente_id:
        query = query.filter(EvidenciaRegistro.cliente_id == cliente_id)

    if busca:
        like = f"%{busca}%"
        query = query.filter(or_(
            EvidenciaRegistro.cliente_nome.ilike(like),
            EvidenciaRegistro.frota.ilike(like),
            EvidenciaRegistro.placa.ilike(like),
        ))

    if campo:
        query = query.join(EvidenciaCampoPai).filter(
            EvidenciaCampoPai.nome.ilike(f"%{campo}%")
        )

    return query.order_by(
        EvidenciaRegistro.atualizado_em.desc(),
        EvidenciaRegistro.id.desc(),
    ).all()


# =========================================================
# TELAS
# =========================================================

@evidencias_frota_bp.route("/")
def index():
    resp = exigir_login()
    if resp:
        return resp

    registros = registros_filtrados()

    for r in registros:
        r.total_campos_pai = len(r.campos_pai)
        r.total_filhos = sum(len(p.filhos) for p in r.campos_pai)
        r.total_imagens = contar_imagens_registro(r)

    return render_template(
        "gestao/evidencias_frota/index.html",
        registros=registros,
        clientes=clientes_para_select(),
        cliente_id=request.args.get("cliente_id", type=int),
        busca=texto(request.args.get("busca")),
        campo=texto(request.args.get("campo")),
    )


@evidencias_frota_bp.route("/novo", methods=["GET", "POST"])
def novo_registro():
    resp = exigir_login()
    if resp:
        return resp

    if request.method == "POST":
        cliente_id = request.form.get("cliente_id", type=int)
        frota = texto(request.form.get("frota"))
        placa = texto(request.form.get("placa"))

        if not cliente_id:
            flash("Selecione um cliente.", "danger")
            return redirect(request.url)

        cliente = Cliente.query.get_or_404(cliente_id)

        if not cliente_permitido(cliente.id, cliente.nome):
            abort(403)

        if not frota and not placa:
            flash("Informe a frota ou a placa.", "danger")
            return redirect(request.url)

        registro = EvidenciaRegistro(
            cliente_id=cliente.id,
            cliente_nome=cliente.nome,
            frota=frota or None,
            placa=normalizar_texto(placa) or None,
        )

        db.session.add(registro)
        db.session.commit()

        flash("Painel de evidências criado com sucesso!", "success")
        return redirect(f"/gestao/evidencias/{registro.id}")

    return render_template(
        "gestao/evidencias_frota/form.html",
        clientes=clientes_para_select(),
    )


@evidencias_frota_bp.route("/<int:registro_id>")
def detalhe(registro_id):
    resp = exigir_login()
    if resp:
        return resp

    registro = obter_registro_ou_404(registro_id)

    links_publicos = EvidenciaLinkPublico.query.filter_by(registro_id=registro.id).order_by(
        EvidenciaLinkPublico.criado_em.desc(),
        EvidenciaLinkPublico.id.desc(),
    ).all()

    return render_template(
        "gestao/evidencias_frota/detalhe.html",
        registro=registro,
        links_publicos=links_publicos,
        pode_gerar_link=usuario_eh_admin_ou_gestao(),
    )


@evidencias_frota_bp.route("/<int:registro_id>/excluir", methods=["POST"])
def excluir_registro(registro_id):
    resp = exigir_login()
    if resp:
        return resp

    registro = obter_registro_ou_404(registro_id)
    db.session.delete(registro)
    db.session.commit()

    flash("Painel de evidências excluído.", "success")
    return redirect("/gestao/evidencias/")


# =========================================================
# CAMPO PAI / FILHO
# =========================================================

@evidencias_frota_bp.route("/<int:registro_id>/pai/novo", methods=["POST"])
def criar_pai(registro_id):
    resp = exigir_login()
    if resp:
        return resp

    registro = obter_registro_ou_404(registro_id)
    nome = texto(request.form.get("nome"))

    if not nome:
        flash("Informe o nome do campo pai.", "danger")
        return redirect(f"/gestao/evidencias/{registro.id}")

    ordem = len(registro.campos_pai) + 1

    pai = EvidenciaCampoPai(
        registro_id=registro.id,
        nome=nome,
        ordem=ordem,
    )

    db.session.add(pai)
    db.session.commit()

    flash("Campo pai criado.", "success")
    return redirect(f"/gestao/evidencias/{registro.id}")


@evidencias_frota_bp.route("/pai/<int:pai_id>/editar", methods=["POST"])
def editar_pai(pai_id):
    resp = exigir_login()
    if resp:
        return resp

    pai = obter_pai_ou_404(pai_id)
    nome = texto(request.form.get("nome"))

    if nome:
        pai.nome = nome
        db.session.commit()
        flash("Campo pai atualizado.", "success")

    return redirect(f"/gestao/evidencias/{pai.registro_id}")


@evidencias_frota_bp.route("/pai/<int:pai_id>/excluir", methods=["POST"])
def excluir_pai(pai_id):
    resp = exigir_login()
    if resp:
        return resp

    pai = obter_pai_ou_404(pai_id)
    registro_id = pai.registro_id

    db.session.delete(pai)
    db.session.commit()

    flash("Campo pai excluído.", "success")
    return redirect(f"/gestao/evidencias/{registro_id}")


@evidencias_frota_bp.route("/pai/<int:pai_id>/filho/novo", methods=["POST"])
def criar_filho(pai_id):
    resp = exigir_login()
    if resp:
        return resp

    pai = obter_pai_ou_404(pai_id)
    nome = texto(request.form.get("nome"))

    if not nome:
        flash("Informe o nome do campo filho.", "danger")
        return redirect(f"/gestao/evidencias/{pai.registro_id}")

    filho = EvidenciaCampoFilho(
        campo_pai_id=pai.id,
        nome=nome,
        ordem=len(pai.filhos) + 1,
    )

    db.session.add(filho)
    db.session.commit()

    flash("Campo filho criado.", "success")
    return redirect(f"/gestao/evidencias/{pai.registro_id}")


@evidencias_frota_bp.route("/filho/<int:filho_id>/editar", methods=["POST"])
def editar_filho(filho_id):
    resp = exigir_login()
    if resp:
        return resp

    filho = obter_filho_ou_404(filho_id)
    nome = texto(request.form.get("nome"))

    if nome:
        filho.nome = nome
        db.session.commit()
        flash("Campo filho atualizado.", "success")

    return redirect(f"/gestao/evidencias/{filho.campo_pai.registro_id}")


@evidencias_frota_bp.route("/filho/<int:filho_id>/excluir", methods=["POST"])
def excluir_filho(filho_id):
    resp = exigir_login()
    if resp:
        return resp

    filho = obter_filho_ou_404(filho_id)
    registro_id = filho.campo_pai.registro_id

    db.session.delete(filho)
    db.session.commit()

    flash("Campo filho excluído.", "success")
    return redirect(f"/gestao/evidencias/{registro_id}")


# =========================================================
# IMAGENS
# =========================================================

@evidencias_frota_bp.route("/filho/<int:filho_id>/imagens", methods=["POST"])
def upload_imagens(filho_id):
    resp = exigir_login()
    if resp:
        return resp

    filho = obter_filho_ou_404(filho_id)
    pai = filho.campo_pai
    registro = pai.registro
    arquivos = request.files.getlist("imagens")
    legenda_padrao = texto(request.form.get("legenda"))

    adicionadas = 0
    for arquivo in arquivos:
        if not arquivo or not arquivo.filename:
            continue

        dados = salvar_imagem_evidencia(arquivo, registro, pai, filho)
        if not dados or not dados.get("url"):
            continue

        imagem = EvidenciaImagem(
            campo_filho_id=filho.id,
            imagem_url=dados["url"],
            public_id=dados.get("public_id"),
            caminho_local=dados.get("caminho_local"),
            nome_original=dados.get("nome_original"),
            legenda=legenda_padrao or None,
            ordem=len(filho.imagens) + adicionadas + 1,
        )

        db.session.add(imagem)
        adicionadas += 1

    db.session.commit()

    if adicionadas:
        flash(f"{adicionadas} imagem(ns) enviada(s).", "success")
    else:
        flash("Nenhuma imagem válida foi enviada.", "warning")

    return redirect(f"/gestao/evidencias/{registro.id}")


@evidencias_frota_bp.route("/imagem/<int:imagem_id>/editar", methods=["POST"])
def editar_imagem(imagem_id):
    resp = exigir_login()
    if resp:
        return resp

    imagem = obter_imagem_ou_404(imagem_id)
    imagem.legenda = texto(request.form.get("legenda")) or None
    db.session.commit()

    flash("Legenda atualizada.", "success")
    return redirect(f"/gestao/evidencias/{imagem.campo_filho.campo_pai.registro_id}")


@evidencias_frota_bp.route("/imagem/<int:imagem_id>/excluir", methods=["POST"])
def excluir_imagem(imagem_id):
    resp = exigir_login()
    if resp:
        return resp

    imagem = obter_imagem_ou_404(imagem_id)
    registro_id = imagem.campo_filho.campo_pai.registro_id

    if imagem.public_id and cloudinary_configurado():
        try:
            cloudinary.uploader.destroy(imagem.public_id, resource_type="image")
        except Exception:
            pass

    if imagem.caminho_local and os.path.exists(imagem.caminho_local):
        try:
            os.remove(imagem.caminho_local)
        except Exception:
            pass

    db.session.delete(imagem)
    db.session.commit()

    flash("Imagem excluída.", "success")
    return redirect(f"/gestao/evidencias/{registro_id}")



# =========================================================
# LINK PÚBLICO DO CLIENTE
# =========================================================

def exigir_gestao_links():
    resp = exigir_login()
    if resp:
        return resp

    if not usuario_eh_admin_ou_gestao():
        abort(403)

    return None


def gerar_token_link_publico():
    while True:
        token = secrets.token_urlsafe(32)
        existente = EvidenciaLinkPublico.query.filter_by(token=token).first()
        if not existente:
            return token


def obter_link_publico_ou_404(token):
    link = EvidenciaLinkPublico.query.filter_by(token=token).first_or_404()

    if not link.esta_disponivel():
        abort(404)

    link.ultimo_acesso_em = datetime.utcnow()
    db.session.commit()
    return link


def imagens_do_registro(registro_id):
    return EvidenciaImagem.query.join(EvidenciaCampoFilho).join(EvidenciaCampoPai).join(EvidenciaRegistro).filter(
        EvidenciaRegistro.id == int(registro_id)
    ).order_by(
        EvidenciaCampoPai.ordem.asc(),
        EvidenciaCampoPai.id.asc(),
        EvidenciaCampoFilho.ordem.asc(),
        EvidenciaCampoFilho.id.asc(),
        EvidenciaImagem.ordem.asc(),
        EvidenciaImagem.id.asc(),
    ).all()


@evidencias_frota_bp.route("/<int:registro_id>/links/criar", methods=["POST"])
def criar_link_publico(registro_id):
    resp = exigir_gestao_links()
    if resp:
        return resp

    registro = obter_registro_ou_404(registro_id)

    validade = request.form.get("validade_dias", type=int)
    expira_em = None
    if validade and validade > 0:
        expira_em = datetime.utcnow() + timedelta(days=validade)

    link = EvidenciaLinkPublico(
        registro_id=registro.id,
        token=gerar_token_link_publico(),
        permitir_excel=True if request.form.get("permitir_excel") == "on" else False,
        permitir_zip=True if request.form.get("permitir_zip") == "on" else False,
        criado_por=session.get("user_id"),
        expira_em=expira_em,
        ativo=True,
    )

    db.session.add(link)
    db.session.commit()

    flash("Link público gerado com sucesso.", "success")
    return redirect(f"/gestao/evidencias/{registro.id}")


@evidencias_frota_bp.route("/links/<int:link_id>/desativar", methods=["POST"])
def desativar_link_publico(link_id):
    resp = exigir_gestao_links()
    if resp:
        return resp

    link = EvidenciaLinkPublico.query.get_or_404(link_id)
    obter_registro_ou_404(link.registro_id)

    link.ativo = False
    db.session.commit()

    flash("Link público desativado.", "success")
    return redirect(f"/gestao/evidencias/{link.registro_id}")


@evidencias_frota_bp.route("/publico/<token>")
def visualizacao_publica(token):
    link = obter_link_publico_ou_404(token)
    registro = link.registro

    return render_template(
        "gestao/evidencias_frota/publico.html",
        link=link,
        registro=registro,
    )


@evidencias_frota_bp.route("/publico/<token>/excel")
def exportar_excel_publico(token):
    link = obter_link_publico_ou_404(token)

    if not link.permitir_excel:
        abort(403)

    return gerar_excel_registro_publico(link.registro_id)


@evidencias_frota_bp.route("/publico/<token>/imagens.zip")
def exportar_zip_publico(token):
    link = obter_link_publico_ou_404(token)

    if not link.permitir_zip:
        abort(403)

    imagens = imagens_do_registro(link.registro_id)

    memoria = BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zf:
        if not imagens:
            zf.writestr("SEM_IMAGENS.txt", "Nenhuma imagem encontrada neste painel.")
        for img in imagens:
            adicionar_imagem_ao_zip(zf, img)

    memoria.seek(0)
    return send_file(
        memoria,
        as_attachment=True,
        download_name=f"evidencias_cliente_{link.registro_id}_imagens.zip",
        mimetype="application/zip",
    )


# =========================================================
# EXPORTAÇÕES
# =========================================================

def imagens_por_filtros(registro_id=None):
    query = EvidenciaImagem.query.join(EvidenciaCampoFilho).join(EvidenciaCampoPai).join(EvidenciaRegistro)
    query = aplicar_permissao_registros(query)

    if registro_id:
        query = query.filter(EvidenciaRegistro.id == int(registro_id))

    cliente_id = request.args.get("cliente_id", type=int)
    campo = texto(request.args.get("campo"))
    busca = texto(request.args.get("busca"))

    if cliente_id:
        query = query.filter(EvidenciaRegistro.cliente_id == cliente_id)

    if campo:
        query = query.filter(EvidenciaCampoPai.nome.ilike(f"%{campo}%"))

    if busca:
        query = query.filter(or_(
            EvidenciaRegistro.cliente_nome.ilike(f"%{busca}%"),
            EvidenciaRegistro.frota.ilike(f"%{busca}%"),
            EvidenciaRegistro.placa.ilike(f"%{busca}%"),
            EvidenciaCampoPai.nome.ilike(f"%{busca}%"),
            EvidenciaCampoFilho.nome.ilike(f"%{busca}%"),
        ))

    return query.order_by(
        EvidenciaRegistro.cliente_nome.asc(),
        EvidenciaRegistro.frota.asc(),
        EvidenciaRegistro.placa.asc(),
        EvidenciaCampoPai.ordem.asc(),
        EvidenciaCampoFilho.ordem.asc(),
        EvidenciaImagem.ordem.asc(),
    ).all()


def ajustar_excel(ws):
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            max_len = max(max_len, len(str(cell.value or "")))
        ws.column_dimensions[col_letter].width = min(max(max_len + 2, 14), 45)


def estilizar_cabecalho(ws):
    fill = PatternFill("solid", fgColor="1f2937")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font


@evidencias_frota_bp.route("/exportar/excel")
def exportar_excel():
    resp = exigir_login()
    if resp:
        return resp

    imagens = imagens_por_filtros()

    wb = Workbook()
    ws_resumo = wb.active
    ws_resumo.title = "Resumo"
    ws_resumo.append(["Cliente", "Frota", "Placa", "Campo pai", "Campo filho", "Qtd. imagens"])

    resumo = {}
    for img in imagens:
        filho = img.campo_filho
        pai = filho.campo_pai
        registro = pai.registro
        chave = (
            registro.cliente_nome,
            registro.frota or "",
            registro.placa or "",
            pai.nome,
            filho.nome,
        )
        resumo[chave] = resumo.get(chave, 0) + 1

    for chave, qtd in sorted(resumo.items()):
        ws_resumo.append(list(chave) + [qtd])
    estilizar_cabecalho(ws_resumo)
    ajustar_excel(ws_resumo)

    ws_imagens = wb.create_sheet("Imagens")
    ws_imagens.append([
        "Cliente", "Frota", "Placa", "Campo pai", "Campo filho",
        "Legenda", "Nome original", "URL/arquivo", "Enviado em",
    ])

    for img in imagens:
        filho = img.campo_filho
        pai = filho.campo_pai
        registro = pai.registro
        ws_imagens.append([
            registro.cliente_nome,
            registro.frota or "",
            registro.placa or "",
            pai.nome,
            filho.nome,
            img.legenda or "",
            img.nome_original or "",
            img.imagem_url,
            img.enviado_em.strftime("%d/%m/%Y %H:%M") if img.enviado_em else "",
        ])
    estilizar_cabecalho(ws_imagens)
    ajustar_excel(ws_imagens)

    # Abas dinâmicas por campo pai.
    nomes_usados = {"Resumo", "Imagens"}
    campos = {}
    for img in imagens:
        nome = img.campo_filho.campo_pai.nome or "SEM CAMPO"
        campos.setdefault(nome, []).append(img)

    for nome_campo, imgs in sorted(campos.items()):
        titulo = re.sub(r"[\\/*?:\[\]]", "-", nome_campo)[:28] or "Campo"
        base_titulo = titulo
        indice = 2
        while titulo in nomes_usados:
            titulo = f"{base_titulo[:25]} {indice}"
            indice += 1
        nomes_usados.add(titulo)

        ws = wb.create_sheet(titulo)
        ws.append(["Cliente", "Frota", "Placa", "Campo filho", "Qtd./Imagem", "Legenda", "URL/arquivo"])
        for img in imgs:
            filho = img.campo_filho
            pai = filho.campo_pai
            registro = pai.registro
            ws.append([
                registro.cliente_nome,
                registro.frota or "",
                registro.placa or "",
                filho.nome,
                img.nome_original or f"Imagem {img.id}",
                img.legenda or "",
                img.imagem_url,
            ])
        estilizar_cabecalho(ws)
        ajustar_excel(ws)

    saida = BytesIO()
    wb.save(saida)
    saida.seek(0)

    return send_file(
        saida,
        as_attachment=True,
        download_name=f"evidencias_frotas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@evidencias_frota_bp.route("/<int:registro_id>/exportar/excel")
def exportar_excel_registro(registro_id):
    request.args = request.args.copy()
    return exportar_excel_por_registro(registro_id)


def montar_excel_registro(imagens):
    wb = Workbook()
    ws = wb.active
    ws.title = "Evidências"
    ws.append(["Cliente", "Frota", "Placa", "Campo pai", "Campo filho", "Legenda", "Imagem"])

    for img in imagens:
        filho = img.campo_filho
        pai = filho.campo_pai
        registro = pai.registro
        ws.append([
            registro.cliente_nome,
            registro.frota or "",
            registro.placa or "",
            pai.nome,
            filho.nome,
            img.legenda or "",
            img.imagem_url,
        ])

    estilizar_cabecalho(ws)
    ajustar_excel(ws)

    saida = BytesIO()
    wb.save(saida)
    saida.seek(0)
    return saida


def exportar_excel_por_registro(registro_id):
    obter_registro_ou_404(registro_id)
    imagens = imagens_por_filtros(registro_id=registro_id)
    saida = montar_excel_registro(imagens)

    return send_file(
        saida,
        as_attachment=True,
        download_name=f"evidencias_registro_{registro_id}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def gerar_excel_registro_publico(registro_id):
    imagens = imagens_do_registro(registro_id)
    saida = montar_excel_registro(imagens)

    return send_file(
        saida,
        as_attachment=True,
        download_name=f"evidencias_cliente_{registro_id}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def caminho_local_por_url_estatica(url):
    """
    Converte URL local /static/uploads/... para caminho físico no projeto.
    Isso é essencial para o ZIP funcionar em ambiente local e também em links públicos.
    """
    url = texto(url)

    if not url.startswith("/static/"):
        return None

    caminho_relativo = url.lstrip("/").replace("/", os.sep)
    caminho_absoluto = os.path.join(current_app.root_path, caminho_relativo)

    return caminho_absoluto if os.path.exists(caminho_absoluto) else None


def adicionar_imagem_ao_zip(zf, img):
    filho = img.campo_filho
    pai = filho.campo_pai
    registro = pai.registro

    extensao = os.path.splitext(img.nome_original or "imagem.jpg")[1] or ".jpg"
    nome_arquivo = limpar_nome_arquivo(img.nome_original or f"imagem_{img.id}{extensao}")

    caminho_zip = "/".join([
        limpar_nome_arquivo(registro.cliente_nome),
        limpar_nome_arquivo(registro.frota or registro.placa or "VEICULO"),
        limpar_nome_arquivo(pai.nome),
        limpar_nome_arquivo(filho.nome),
        f"{img.id}_{nome_arquivo}",
    ])

    # 1) Arquivo local salvo diretamente no banco.
    if img.caminho_local and os.path.exists(img.caminho_local):
        zf.write(img.caminho_local, caminho_zip)
        return True

    # 2) URL local do Flask: /static/uploads/...
    caminho_estatico = caminho_local_por_url_estatica(img.imagem_url)
    if caminho_estatico:
        zf.write(caminho_estatico, caminho_zip)
        return True

    # 3) URL externa absoluta, exemplo Cloudinary.
    if img.imagem_url and str(img.imagem_url).startswith(("http://", "https://")):
        try:
            req = urllib.request.Request(
                img.imagem_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                zf.writestr(caminho_zip, resp.read())
                return True
        except Exception as e:
            zf.writestr(
                caminho_zip + ".txt",
                "Não foi possível baixar a imagem automaticamente.\n"
                f"URL: {img.imagem_url}\n"
                f"Erro: {str(e)}"
            )
            return False

    # 4) Sem caminho válido.
    zf.writestr(
        caminho_zip + ".txt",
        f"Imagem sem caminho válido no sistema. ID: {getattr(img, 'id', '-')}."
    )
    return False


@evidencias_frota_bp.route("/exportar/imagens.zip")
def exportar_zip():
    resp = exigir_login()
    if resp:
        return resp

    imagens = imagens_por_filtros()

    memoria = BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zf:
        if not imagens:
            zf.writestr("SEM_IMAGENS.txt", "Nenhuma imagem encontrada para os filtros informados.")
        for img in imagens:
            adicionar_imagem_ao_zip(zf, img)

    memoria.seek(0)
    return send_file(
        memoria,
        as_attachment=True,
        download_name=f"evidencias_imagens_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
        mimetype="application/zip",
    )


@evidencias_frota_bp.route("/<int:registro_id>/exportar/imagens.zip")
def exportar_zip_registro(registro_id):
    resp = exigir_login()
    if resp:
        return resp

    obter_registro_ou_404(registro_id)
    imagens = imagens_por_filtros(registro_id=registro_id)

    memoria = BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zf:
        if not imagens:
            zf.writestr("SEM_IMAGENS.txt", "Nenhuma imagem encontrada neste painel.")
        for img in imagens:
            adicionar_imagem_ao_zip(zf, img)

    memoria.seek(0)
    return send_file(
        memoria,
        as_attachment=True,
        download_name=f"evidencias_registro_{registro_id}_imagens.zip",
        mimetype="application/zip",
    )
