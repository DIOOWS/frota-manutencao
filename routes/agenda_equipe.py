import os
from uuid import uuid4

from flask import Blueprint, render_template, request, redirect, flash, current_app
from werkzeug.utils import secure_filename

from utils.auth import gestao_required
from database import db
from models.tarefa_equipe import TarefaEquipe
from models.membro_agenda_equipe import MembroAgendaEquipe


agenda_equipe_bp = Blueprint(
    "agenda_equipe",
    __name__,
    url_prefix="/admin/agenda-equipe"
)


DIAS_SEMANA = [
    "SEGUNDA",
    "TERCA",
    "QUARTA",
    "QUINTA",
    "SEXTA",
]


MEMBROS_PADRAO = [
    {
        "nome": "João",
        "cargo": "Equipe",
        "foto": "/static/img/equipe/joao.jpg",
    },
    {
        "nome": "Carlos",
        "cargo": "Equipe",
        "foto": "/static/img/equipe/carlos.jpg",
    },
    {
        "nome": "Aquizia",
        "cargo": "Equipe",
        "foto": "/static/img/equipe/aquizia.jpg",
    },
]


EXTENSOES_PERMITIDAS = {"png", "jpg", "jpeg", "webp"}


def texto(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def normalizar_nome(valor):
    return texto(valor).title()


def normalizar_status(valor):
    status = texto(valor).upper()

    if status not in ["PENDENTE", "ANDAMENTO", "CONCLUIDA", "CANCELADA"]:
        return "PENDENTE"

    return status


def normalizar_dia(valor):
    dia = texto(valor).upper()

    mapa = {
        "SEGUNDA": "SEGUNDA",
        "TERÇA": "TERCA",
        "TERCA": "TERCA",
        "QUARTA": "QUARTA",
        "QUINTA": "QUINTA",
        "SEXTA": "SEXTA",
    }

    return mapa.get(dia, "SEGUNDA")


def extensao_permitida(nome_arquivo):
    if "." not in nome_arquivo:
        return False

    extensao = nome_arquivo.rsplit(".", 1)[1].lower()

    return extensao in EXTENSOES_PERMITIDAS


def salvar_foto_membro(arquivo):
    if not arquivo or not arquivo.filename:
        return None

    if not extensao_permitida(arquivo.filename):
        raise ValueError("Formato de imagem inválido. Use PNG, JPG, JPEG ou WEBP.")

    pasta = os.path.join(
        current_app.root_path,
        "static",
        "uploads",
        "equipe"
    )

    os.makedirs(pasta, exist_ok=True)

    nome_original = secure_filename(arquivo.filename)
    extensao = nome_original.rsplit(".", 1)[1].lower()
    nome_final = f"{uuid4().hex}.{extensao}"

    caminho_final = os.path.join(pasta, nome_final)
    arquivo.save(caminho_final)

    return f"/static/uploads/equipe/{nome_final}"


def garantir_membros_padrao():
    total = MembroAgendaEquipe.query.count()

    if total > 0:
        return

    for item in MEMBROS_PADRAO:
        membro = MembroAgendaEquipe(
            nome=item["nome"],
            cargo=item["cargo"],
            foto=item["foto"],
            ativo=True,
        )

        db.session.add(membro)

    db.session.commit()


def buscar_membros():
    garantir_membros_padrao()

    return MembroAgendaEquipe.query.filter_by(
        ativo=True
    ).order_by(
        MembroAgendaEquipe.nome.asc()
    ).all()


def buscar_membro_por_id(membro_id):
    if not membro_id:
        return None

    return MembroAgendaEquipe.query.filter_by(
        id=membro_id,
        ativo=True
    ).first()


def montar_tarefas_por_dia(responsavel):
    tarefas = TarefaEquipe.query.filter_by(
        responsavel=responsavel
    ).order_by(
        TarefaEquipe.id.desc()
    ).all()

    tarefas_por_dia = {
        dia: []
        for dia in DIAS_SEMANA
    }

    for tarefa in tarefas:
        dia = normalizar_dia(tarefa.dia_semana)

        if dia not in tarefas_por_dia:
            tarefas_por_dia[dia] = []

        tarefas_por_dia[dia].append(tarefa)

    return tarefas_por_dia


def contar_tarefas(responsavel):
    tarefas = TarefaEquipe.query.filter_by(
        responsavel=responsavel
    ).all()

    total = len(tarefas)

    pendentes = len([
        t for t in tarefas
        if (t.status or "").upper() == "PENDENTE"
    ])

    andamento = len([
        t for t in tarefas
        if (t.status or "").upper() == "ANDAMENTO"
    ])

    concluidas = len([
        t for t in tarefas
        if (t.status or "").upper() == "CONCLUIDA"
    ])

    canceladas = len([
        t for t in tarefas
        if (t.status or "").upper() == "CANCELADA"
    ])

    return {
        "total": total,
        "pendentes": pendentes,
        "andamento": andamento,
        "concluidas": concluidas,
        "canceladas": canceladas,
    }


def montar_membros_com_resumo(membros):
    membros_com_resumo = []

    for membro in membros:
        resumo = contar_tarefas(membro.nome)

        membros_com_resumo.append({
            "id": membro.id,
            "nome": membro.nome,
            "cargo": membro.cargo,
            "foto": membro.foto,
            "resumo": resumo,
        })

    return membros_com_resumo


@agenda_equipe_bp.route("/", methods=["GET"])
@gestao_required
def index():

    membros = buscar_membros()
    membros_com_resumo = montar_membros_com_resumo(membros)

    membro_id = request.args.get("membro_id", type=int)

    membro_selecionado = buscar_membro_por_id(membro_id)

    if not membro_selecionado and membros:
        membro_selecionado = membros[0]

    tarefas_por_dia = None
    resumo_membro = None

    if membro_selecionado:
        tarefas_por_dia = montar_tarefas_por_dia(
            membro_selecionado.nome
        )

        resumo_membro = contar_tarefas(
            membro_selecionado.nome
        )

    return render_template(
        "admin/agenda_equipe.html",
        membros=membros_com_resumo,
        membros_raw=membros,
        membro_selecionado=membro_selecionado,
        tarefas_por_dia=tarefas_por_dia,
        resumo_membro=resumo_membro,
        dias_semana=DIAS_SEMANA
    )


# =====================================================
# MEMBROS
# =====================================================

@agenda_equipe_bp.route("/membros/novo", methods=["POST"])
@gestao_required
def novo_membro():

    nome = normalizar_nome(
        request.form.get("nome")
    )

    cargo = texto(
        request.form.get("cargo")
    ) or "Equipe"

    if not nome:
        flash("Informe o nome do membro.", "danger")
        return redirect("/admin/agenda-equipe/")

    try:
        foto = salvar_foto_membro(
            request.files.get("foto")
        )

        membro = MembroAgendaEquipe(
            nome=nome,
            cargo=cargo,
            foto=foto,
            ativo=True,
        )

        db.session.add(membro)
        db.session.commit()

        flash("Membro adicionado à agenda com sucesso!", "success")

        return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao cadastrar membro: {str(e)}", "danger")

    return redirect("/admin/agenda-equipe/")


@agenda_equipe_bp.route("/membros/editar/<int:id>", methods=["POST"])
@gestao_required
def editar_membro(id):

    membro = MembroAgendaEquipe.query.get_or_404(id)

    nome_antigo = membro.nome

    nome = normalizar_nome(
        request.form.get("nome")
    )

    cargo = texto(
        request.form.get("cargo")
    ) or "Equipe"

    if not nome:
        flash("Informe o nome do membro.", "danger")
        return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}")

    try:
        nova_foto = salvar_foto_membro(
            request.files.get("foto")
        )

        membro.nome = nome
        membro.cargo = cargo

        if nova_foto:
            membro.foto = nova_foto

        if nome_antigo != nome:
            TarefaEquipe.query.filter_by(
                responsavel=nome_antigo
            ).update({
                "responsavel": nome
            })

        db.session.commit()

        flash("Membro atualizado com sucesso!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao editar membro: {str(e)}", "danger")

    return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}")


@agenda_equipe_bp.route("/membros/excluir/<int:id>", methods=["POST"])
@gestao_required
def excluir_membro(id):

    membro = MembroAgendaEquipe.query.get_or_404(id)

    try:
        TarefaEquipe.query.filter_by(
            responsavel=membro.nome
        ).delete()

        db.session.delete(membro)
        db.session.commit()

        flash("Membro e tarefas vinculadas foram excluídos.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir membro: {str(e)}", "danger")

    return redirect("/admin/agenda-equipe/")


# =====================================================
# TAREFAS
# =====================================================

@agenda_equipe_bp.route("/nova", methods=["POST"])
@gestao_required
def nova():

    membro_id = request.form.get("membro_id", type=int)
    membro = buscar_membro_por_id(membro_id)

    if not membro:
        flash("Responsável inválido.", "danger")
        return redirect("/admin/agenda-equipe/")

    titulo = texto(
        request.form.get("titulo")
    )

    descricao = texto(
        request.form.get("descricao")
    )

    dia_semana = normalizar_dia(
        request.form.get("dia_semana")
    )

    status = normalizar_status(
        request.form.get("status")
    )

    if not titulo:
        flash("Informe o título da tarefa.", "danger")
        return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}")

    tarefa = TarefaEquipe(
        responsavel=membro.nome,
        titulo=titulo,
        descricao=descricao,
        dia_semana=dia_semana,
        status=status,
    )

    try:
        db.session.add(tarefa)
        db.session.commit()

        flash("Tarefa cadastrada com sucesso!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao cadastrar tarefa: {str(e)}", "danger")

    return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}")


@agenda_equipe_bp.route("/editar/<int:id>", methods=["POST"])
@gestao_required
def editar(id):

    tarefa = TarefaEquipe.query.get_or_404(id)

    membro_id = request.form.get("membro_id", type=int)
    membro = buscar_membro_por_id(membro_id)

    titulo = texto(
        request.form.get("titulo")
    )

    descricao = texto(
        request.form.get("descricao")
    )

    dia_semana = normalizar_dia(
        request.form.get("dia_semana")
    )

    status = normalizar_status(
        request.form.get("status")
    )

    if not titulo:
        flash("Informe o título da tarefa.", "danger")
        return redirect(f"/admin/agenda-equipe/?membro_id={membro.id if membro else ''}")

    try:
        if membro:
            tarefa.responsavel = membro.nome

        tarefa.titulo = titulo
        tarefa.descricao = descricao
        tarefa.dia_semana = dia_semana
        tarefa.status = status

        db.session.commit()

        flash("Tarefa atualizada com sucesso!", "success")

        membro_destino = membro or MembroAgendaEquipe.query.filter_by(
            nome=tarefa.responsavel
        ).first()

        if membro_destino:
            return redirect(f"/admin/agenda-equipe/?membro_id={membro_destino.id}")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao editar tarefa: {str(e)}", "danger")

    return redirect("/admin/agenda-equipe/")


@agenda_equipe_bp.route("/concluir/<int:id>", methods=["POST"])
@gestao_required
def concluir(id):

    tarefa = TarefaEquipe.query.get_or_404(id)

    try:
        tarefa.status = "CONCLUIDA"
        db.session.commit()

        flash("Tarefa marcada como concluída!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao concluir tarefa: {str(e)}", "danger")

    membro = MembroAgendaEquipe.query.filter_by(
        nome=tarefa.responsavel
    ).first()

    if membro:
        return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}")

    return redirect("/admin/agenda-equipe/")


@agenda_equipe_bp.route("/excluir/<int:id>", methods=["POST"])
@gestao_required
def excluir(id):

    tarefa = TarefaEquipe.query.get_or_404(id)
    responsavel = tarefa.responsavel

    try:
        db.session.delete(tarefa)
        db.session.commit()

        flash("Tarefa excluída com sucesso!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir tarefa: {str(e)}", "danger")

    membro = MembroAgendaEquipe.query.filter_by(
        nome=responsavel
    ).first()

    if membro:
        return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}")

    return redirect("/admin/agenda-equipe/")