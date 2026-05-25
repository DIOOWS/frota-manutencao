import os
import calendar
from uuid import uuid4
from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, flash, current_app
from werkzeug.utils import secure_filename

from utils.auth import gestao_required
from database import db
from models.tarefa_equipe import TarefaEquipe, ExecucaoTarefaEquipe
from models.membro_agenda_equipe import MembroAgendaEquipe
from models.agenda_mes_equipe import AgendaMesEquipe


agenda_equipe_bp = Blueprint(
    "agenda_equipe",
    __name__,
    url_prefix="/admin/agenda-equipe"
)


EXTENSOES_PERMITIDAS = {"png", "jpg", "jpeg", "webp"}

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


def texto(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def normalizar_nome(valor):
    return texto(valor).title()


def normalizar_periodicidade(valor):
    periodicidade = texto(valor).upper()

    if periodicidade not in ["DIARIA", "SEMANAL", "MENSAL", "EXTRA"]:
        return "DIARIA"

    return periodicidade


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


def ultimo_dia_mes(mes, ano):
    return calendar.monthrange(ano, mes)[1]


def mes_anterior(mes, ano):
    if mes == 1:
        return 12, ano - 1

    return mes - 1, ano


def nome_mes_texto(mes):
    nomes = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Março",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }

    return nomes.get(mes, str(mes))


def nome_dia_semana(numero):
    nomes = {
        0: "seg",
        1: "ter",
        2: "qua",
        3: "qui",
        4: "sex",
        5: "sáb",
        6: "dom",
    }

    return nomes.get(numero, "")


def dias_do_mes(mes, ano):
    total_dias = ultimo_dia_mes(mes, ano)
    dias = []

    for dia in range(1, total_dias + 1):
        data_ref = date(ano, mes, dia)
        semana = data_ref.weekday()

        dias.append({
            "dia": dia,
            "data": data_ref,
            "semana": semana,
            "semana_nome": nome_dia_semana(semana),
            "fim_semana": semana in [5, 6],
            "hoje": data_ref == date.today(),
        })

    return dias


def datas_programadas_tarefa(tarefa):
    total_dias = ultimo_dia_mes(tarefa.mes, tarefa.ano)
    datas = []

    periodicidade = (tarefa.periodicidade or "DIARIA").upper()

    for dia in range(1, total_dias + 1):
        data_ref = date(tarefa.ano, tarefa.mes, dia)
        semana = data_ref.weekday()

        if periodicidade == "DIARIA":
            if semana <= 4:
                datas.append(data_ref)

        elif periodicidade == "SEMANAL":
            if tarefa.dia_semana is not None and semana == tarefa.dia_semana:
                datas.append(data_ref)

        elif periodicidade == "MENSAL":
            dia_alvo = tarefa.dia_mes or 1
            dia_real = min(dia_alvo, total_dias)

            if dia == dia_real:
                datas.append(data_ref)

        elif periodicidade == "EXTRA":
            dia_alvo = tarefa.dia_mes or 1
            dia_real = min(dia_alvo, total_dias)

            if dia == dia_real:
                datas.append(data_ref)

    return datas


def criar_execucoes_da_tarefa(tarefa):
    datas = datas_programadas_tarefa(tarefa)

    for data_ref in datas:
        existe = ExecucaoTarefaEquipe.query.filter_by(
            tarefa_id=tarefa.id,
            data=data_ref
        ).first()

        if existe:
            continue

        execucao = ExecucaoTarefaEquipe(
            tarefa_id=tarefa.id,
            data=data_ref,
            status="PENDENTE"
        )

        db.session.add(execucao)


def garantir_execucoes_mes(membro_id, mes, ano):
    tarefas = TarefaEquipe.query.filter_by(
        membro_id=membro_id,
        mes=mes,
        ano=ano,
        ativo=True
    ).all()

    for tarefa in tarefas:
        criar_execucoes_da_tarefa(tarefa)

    db.session.commit()


def buscar_tarefas_mes(membro_id, mes, ano):
    tarefas = TarefaEquipe.query.filter_by(
        membro_id=membro_id,
        mes=mes,
        ano=ano,
        ativo=True
    ).order_by(
        TarefaEquipe.ordem.asc(),
        TarefaEquipe.id.asc()
    ).all()

    return tarefas


def existe_agenda_mes(membro_id, mes, ano):
    agenda = AgendaMesEquipe.query.filter_by(
        membro_id=membro_id,
        mes=mes,
        ano=ano
    ).first()

    return agenda is not None


def criar_registro_agenda_mes(membro_id, mes, ano):
    agenda = AgendaMesEquipe.query.filter_by(
        membro_id=membro_id,
        mes=mes,
        ano=ano
    ).first()

    if agenda:
        return agenda

    agenda = AgendaMesEquipe(
        membro_id=membro_id,
        mes=mes,
        ano=ano
    )

    db.session.add(agenda)

    return agenda


def buscar_mes_base_para_copia(membro_id, mes, ano):
    mes_ant, ano_ant = mes_anterior(mes, ano)

    tarefas_mes_anterior = buscar_tarefas_mes(
        membro_id=membro_id,
        mes=mes_ant,
        ano=ano_ant
    )

    if tarefas_mes_anterior:
        return mes_ant, ano_ant, tarefas_mes_anterior

    tarefas_antigas = TarefaEquipe.query.filter(
        TarefaEquipe.membro_id == membro_id,
        TarefaEquipe.ativo == True
    ).order_by(
        TarefaEquipe.ano.desc(),
        TarefaEquipe.mes.desc(),
        TarefaEquipe.id.asc()
    ).all()

    if tarefas_antigas:
        tarefa_ref = tarefas_antigas[0]

        tarefas_mes_ref = buscar_tarefas_mes(
            membro_id=membro_id,
            mes=tarefa_ref.mes,
            ano=tarefa_ref.ano
        )

        return tarefa_ref.mes, tarefa_ref.ano, tarefas_mes_ref

    return None, None, []


def montar_linhas_tabela(tarefas):
    linhas = []

    for tarefa in tarefas:
        execucoes = ExecucaoTarefaEquipe.query.filter_by(
            tarefa_id=tarefa.id
        ).all()

        mapa = {}

        for execucao in execucoes:
            mapa[execucao.data.day] = execucao

        linhas.append({
            "tarefa": tarefa,
            "execucoes": mapa,
        })

    return linhas


def contar_resumo_mes(tarefas):
    total_programadas = 0
    concluidas = 0
    pendentes = 0
    atrasadas = 0

    hoje = date.today()

    for tarefa in tarefas:
        execucoes = ExecucaoTarefaEquipe.query.filter_by(
            tarefa_id=tarefa.id
        ).all()

        for execucao in execucoes:
            total_programadas += 1

            status = (execucao.status or "").upper()

            if status == "CONCLUIDA":
                concluidas += 1
            elif execucao.data < hoje:
                atrasadas += 1
            else:
                pendentes += 1

    percentual = 0

    if total_programadas:
        percentual = round((concluidas / total_programadas) * 100, 1)

    return {
        "total_programadas": total_programadas,
        "concluidas": concluidas,
        "pendentes": pendentes,
        "atrasadas": atrasadas,
        "percentual": percentual,
    }


def contar_tarefas_membro(membro_id):
    total = TarefaEquipe.query.filter_by(
        membro_id=membro_id,
        ativo=True
    ).count()

    return total


@agenda_equipe_bp.route("/", methods=["GET"])
@gestao_required
def index():

    hoje = date.today()

    mes = request.args.get("mes", type=int) or hoje.month
    ano = request.args.get("ano", type=int) or hoje.year
    membro_id = request.args.get("membro_id", type=int)

    if mes < 1 or mes > 12:
        mes = hoje.month

    membros_raw = buscar_membros()

    if not membro_id and membros_raw:
        membro_id = membros_raw[0].id

    membro_selecionado = buscar_membro_por_id(membro_id)

    membros = []

    for membro in membros_raw:
        membros.append({
            "id": membro.id,
            "nome": membro.nome,
            "cargo": membro.cargo,
            "foto": membro.foto,
            "total_tarefas": contar_tarefas_membro(membro.id),
        })

    agenda_iniciada = False
    tarefas = []
    linhas = []
    resumo_mes = {
        "total_programadas": 0,
        "concluidas": 0,
        "pendentes": 0,
        "atrasadas": 0,
        "percentual": 0,
    }

    if membro_selecionado:
        agenda_iniciada = existe_agenda_mes(
            membro_id=membro_selecionado.id,
            mes=mes,
            ano=ano
        )

        if agenda_iniciada:
            garantir_execucoes_mes(
                membro_id=membro_selecionado.id,
                mes=mes,
                ano=ano
            )

            tarefas = buscar_tarefas_mes(
                membro_id=membro_selecionado.id,
                mes=mes,
                ano=ano
            )

            linhas = montar_linhas_tabela(tarefas)
            resumo_mes = contar_resumo_mes(tarefas)

    return render_template(
        "admin/agenda_equipe.html",
        membros=membros,
        membros_raw=membros_raw,
        membro_selecionado=membro_selecionado,
        mes=mes,
        ano=ano,
        nome_mes=nome_mes_texto(mes),
        dias=dias_do_mes(mes, ano),
        tarefas=tarefas,
        linhas=linhas,
        resumo_mes=resumo_mes,
        agenda_iniciada=agenda_iniciada,
        hoje=hoje,
    )


@agenda_equipe_bp.route("/iniciar-mes", methods=["POST"])
@gestao_required
def iniciar_mes():

    membro_id = request.form.get("membro_id", type=int)
    mes = request.form.get("mes", type=int)
    ano = request.form.get("ano", type=int)

    membro = buscar_membro_por_id(membro_id)

    if not membro:
        flash("Membro inválido.", "danger")
        return redirect("/admin/agenda-equipe/")

    if existe_agenda_mes(membro.id, mes, ano):
        flash("A agenda deste mês já foi iniciada.", "info")
        return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}&mes={mes}&ano={ano}")

    try:
        criar_registro_agenda_mes(
            membro_id=membro.id,
            mes=mes,
            ano=ano
        )

        mes_base, ano_base, tarefas_base = buscar_mes_base_para_copia(
            membro_id=membro.id,
            mes=mes,
            ano=ano
        )

        total_copiadas = 0

        for tarefa_base in tarefas_base:
            nova_tarefa = TarefaEquipe(
                membro_id=membro.id,
                titulo=tarefa_base.titulo,
                descricao=tarefa_base.descricao,
                mes=mes,
                ano=ano,
                periodicidade=tarefa_base.periodicidade,
                dia_semana=tarefa_base.dia_semana,
                dia_mes=tarefa_base.dia_mes,
                ativo=True,
                ordem=tarefa_base.ordem or 0,
            )

            db.session.add(nova_tarefa)
            db.session.flush()

            criar_execucoes_da_tarefa(nova_tarefa)

            total_copiadas += 1

        db.session.commit()

        if total_copiadas:
            flash(
                f"Agenda de {nome_mes_texto(mes)}/{ano} iniciada com {total_copiadas} tarefa(s) copiadas do mês anterior.",
                "success"
            )
        else:
            flash(
                "Agenda iniciada vazia. Cadastre as tarefas deste mês.",
                "success"
            )

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao iniciar agenda do mês: {str(e)}", "danger")

    return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}&mes={mes}&ano={ano}")


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
        tarefas = TarefaEquipe.query.filter_by(
            membro_id=membro.id
        ).all()

        for tarefa in tarefas:
            db.session.delete(tarefa)

        db.session.delete(membro)
        db.session.commit()

        flash("Membro e tarefas vinculadas foram excluídos.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir membro: {str(e)}", "danger")

    return redirect("/admin/agenda-equipe/")


@agenda_equipe_bp.route("/nova", methods=["POST"])
@gestao_required
def nova():

    membro_id = request.form.get("membro_id", type=int)
    mes = request.form.get("mes", type=int)
    ano = request.form.get("ano", type=int)

    membro = buscar_membro_por_id(membro_id)

    if not membro:
        flash("Perfil inválido.", "danger")
        return redirect("/admin/agenda-equipe/")

    if not existe_agenda_mes(membro.id, mes, ano):
        criar_registro_agenda_mes(membro.id, mes, ano)

    titulo = texto(
        request.form.get("titulo")
    )

    descricao = texto(
        request.form.get("descricao")
    )

    periodicidade = normalizar_periodicidade(
        request.form.get("periodicidade")
    )

    dia_semana = request.form.get("dia_semana", type=int)
    dia_mes = request.form.get("dia_mes", type=int)

    if not titulo:
        flash("Informe o título da tarefa.", "danger")
        return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}&mes={mes}&ano={ano}")

    if periodicidade == "SEMANAL" and dia_semana is None:
        dia_semana = 0

    if periodicidade in ["MENSAL", "EXTRA"] and not dia_mes:
        dia_mes = 1

    try:
        maior_ordem = db.session.query(
            db.func.max(TarefaEquipe.ordem)
        ).filter_by(
            membro_id=membro.id,
            mes=mes,
            ano=ano
        ).scalar() or 0

        tarefa = TarefaEquipe(
            membro_id=membro.id,
            titulo=titulo,
            descricao=descricao,
            mes=mes,
            ano=ano,
            periodicidade=periodicidade,
            dia_semana=dia_semana,
            dia_mes=dia_mes,
            ativo=True,
            ordem=maior_ordem + 1,
        )

        db.session.add(tarefa)
        db.session.flush()

        criar_execucoes_da_tarefa(tarefa)

        db.session.commit()

        flash("Tarefa cadastrada no mês selecionado!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao cadastrar tarefa: {str(e)}", "danger")

    return redirect(f"/admin/agenda-equipe/?membro_id={membro.id}&mes={mes}&ano={ano}")


@agenda_equipe_bp.route("/editar/<int:id>", methods=["POST"])
@gestao_required
def editar(id):

    tarefa = TarefaEquipe.query.get_or_404(id)

    titulo = texto(
        request.form.get("titulo")
    )

    descricao = texto(
        request.form.get("descricao")
    )

    periodicidade = normalizar_periodicidade(
        request.form.get("periodicidade")
    )

    dia_semana = request.form.get("dia_semana", type=int)
    dia_mes = request.form.get("dia_mes", type=int)

    if not titulo:
        flash("Informe o título da tarefa.", "danger")
        return redirect(f"/admin/agenda-equipe/?membro_id={tarefa.membro_id}&mes={tarefa.mes}&ano={tarefa.ano}")

    if periodicidade == "SEMANAL" and dia_semana is None:
        dia_semana = 0

    if periodicidade in ["MENSAL", "EXTRA"] and not dia_mes:
        dia_mes = 1

    try:
        tarefa.titulo = titulo
        tarefa.descricao = descricao
        tarefa.periodicidade = periodicidade
        tarefa.dia_semana = dia_semana
        tarefa.dia_mes = dia_mes

        ExecucaoTarefaEquipe.query.filter_by(
            tarefa_id=tarefa.id,
            status="PENDENTE"
        ).delete()

        db.session.flush()

        criar_execucoes_da_tarefa(tarefa)

        db.session.commit()

        flash("Tarefa atualizada com sucesso!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao editar tarefa: {str(e)}", "danger")

    return redirect(f"/admin/agenda-equipe/?membro_id={tarefa.membro_id}&mes={tarefa.mes}&ano={tarefa.ano}")


@agenda_equipe_bp.route("/excluir/<int:id>", methods=["POST"])
@gestao_required
def excluir(id):

    tarefa = TarefaEquipe.query.get_or_404(id)

    membro_id = tarefa.membro_id
    mes = tarefa.mes
    ano = tarefa.ano

    try:
        db.session.delete(tarefa)
        db.session.commit()

        flash("Tarefa excluída do mês selecionado.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir tarefa: {str(e)}", "danger")

    return redirect(f"/admin/agenda-equipe/?membro_id={membro_id}&mes={mes}&ano={ano}")


@agenda_equipe_bp.route("/execucao/<int:id>/alternar", methods=["POST"])
@gestao_required
def alternar_execucao(id):

    execucao = ExecucaoTarefaEquipe.query.get_or_404(id)
    tarefa = execucao.tarefa

    try:
        status_atual = (execucao.status or "").upper()

        if status_atual == "CONCLUIDA":
            execucao.status = "PENDENTE"
        else:
            execucao.status = "CONCLUIDA"

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao atualizar execução: {str(e)}", "danger")

    return redirect(f"/admin/agenda-equipe/?membro_id={tarefa.membro_id}&mes={tarefa.mes}&ano={tarefa.ano}")