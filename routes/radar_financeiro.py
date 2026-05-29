import os
import calendar
import hashlib
from decimal import Decimal
from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, request, redirect, flash, jsonify
from sqlalchemy import or_, and_

from utils.auth import gestao_required
from database import db
from models.conta_radar_financeiro import ContaRadarFinanceiro
from services.telegram_service import (
    enviar_mensagem_telegram,
    montar_mensagem_contas_vencendo_hoje,
)


radar_financeiro_bp = Blueprint(
    "radar_financeiro",
    __name__,
    url_prefix="/gestao/radar-financeiro",
)


# =========================================================
# HELPERS GERAIS
# =========================================================

def texto(valor):
    return "" if valor is None else str(valor).strip()


def texto_upper(valor):
    return texto(valor).upper()


def normalizar_decimal(valor):
    if valor is None or texto(valor) == "":
        return Decimal("0.00")

    if isinstance(valor, Decimal):
        return valor.quantize(Decimal("0.01"))

    if isinstance(valor, (int, float)):
        try:
            return Decimal(str(valor)).quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0.00")

    valor_txt = str(valor).strip().replace("R$", "").replace(" ", "")

    if "," in valor_txt:
        valor_txt = valor_txt.replace(".", "").replace(",", ".")

    try:
        return Decimal(valor_txt).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def dinheiro(valor):
    try:
        return float(valor or 0)
    except Exception:
        return 0.0


def moeda(valor):
    valor = dinheiro(valor)
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_data(valor):
    if not valor:
        return None

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, date):
        return valor

    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except Exception:
        return None


def data_para_date(valor):
    if not valor:
        return None

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, date):
        return valor

    return None


def data_para_input(valor):
    data_ref = data_para_date(valor)
    return data_ref.strftime("%Y-%m-%d") if data_ref else ""


def data_br(valor):
    data_ref = data_para_date(valor)
    return data_ref.strftime("%d/%m/%Y") if data_ref else "-"


def primeiro_dia_mes(mes, ano):
    return date(ano, mes, 1)


def ultimo_dia_mes(mes, ano):
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


def inicio_dia_datetime(data_ref):
    return datetime.combine(data_ref, datetime.min.time())


def fim_dia_datetime(data_ref):
    return datetime.combine(data_ref, datetime.max.time())


def adicionar_um_mes(data_ref):
    if not data_ref:
        data_ref = date.today()

    if data_ref.month == 12:
        novo_mes = 1
        novo_ano = data_ref.year + 1
    else:
        novo_mes = data_ref.month + 1
        novo_ano = data_ref.year

    dia = min(data_ref.day, calendar.monthrange(novo_ano, novo_mes)[1])
    return date(novo_ano, novo_mes, dia)


def adicionar_meses(data_ref, quantidade):
    if not data_ref:
        data_ref = date.today()

    mes_base = data_ref.month - 1 + int(quantidade or 0)
    novo_ano = data_ref.year + (mes_base // 12)
    novo_mes = (mes_base % 12) + 1
    dia = min(data_ref.day, calendar.monthrange(novo_ano, novo_mes)[1])
    return date(novo_ano, novo_mes, dia)


def ajustar_data_para_mes_ano(data_base, mes_destino, ano_destino):
    data_base = data_base or date.today()
    ultimo_destino = calendar.monthrange(ano_destino, mes_destino)[1]
    return date(ano_destino, mes_destino, min(data_base.day, ultimo_destino))


def redirect_radar(mes=None, ano=None, grupo=None):
    if mes and ano:
        url = f"/gestao/radar-financeiro/?mes={mes}&ano={ano}"
        if grupo:
            url += f"&grupo={grupo}"
        return redirect(url)

    return redirect("/gestao/radar-financeiro/")



def mes_ano_contexto_form():
    mes_contexto = (
        request.form.get("mes_contexto", type=int)
        or request.form.get("mes_retorno", type=int)
    )
    ano_contexto = (
        request.form.get("ano_contexto", type=int)
        or request.form.get("ano_retorno", type=int)
    )

    if mes_contexto and ano_contexto and 1 <= mes_contexto <= 12:
        return mes_contexto, ano_contexto

    return None, None


def redirect_contexto_form(data_fallback=None):
    mes_contexto, ano_contexto = mes_ano_contexto_form()

    if mes_contexto and ano_contexto:
        return redirect_radar(mes_contexto, ano_contexto)

    if data_fallback:
        data_ref = data_para_date(data_fallback)
        if data_ref:
            return redirect_radar(data_ref.month, data_ref.year)

    return redirect(request.referrer or "/gestao/radar-financeiro/")


def nome_mes(mes):
    nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
    }
    return nomes.get(int(mes or 0), str(mes or ""))


def nome_mes_curto(mes):
    nomes = {
        1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr",
        5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago",
        9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
    }
    return nomes.get(int(mes or 0), str(mes or ""))


def normalizar_chave(valor):
    return " ".join(texto(valor).upper().split())


def chave_grupo(descricao, fornecedor, categoria, setor):
    base = "|".join([
        normalizar_chave(descricao),
        normalizar_chave(fornecedor),
        normalizar_chave(categoria),
        normalizar_chave(setor),
    ])
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def grupo_key_conta(conta):
    return chave_grupo(
        conta.descricao,
        conta.fornecedor,
        conta.categoria,
        conta.setor,
    )


def ids_limpos_formulario(nome_campo="contas_ids"):
    ids = request.form.getlist(nome_campo)

    if not ids:
        ids = request.form.getlist(f"{nome_campo}[]")

    ids_limpos = []
    for item in ids:
        try:
            ids_limpos.append(int(item))
        except Exception:
            pass

    return list(dict.fromkeys(ids_limpos))


def conta_esta_paga(conta):
    return texto_upper(getattr(conta, "status", None)) == "PAGO"


def conta_esta_cancelada(conta):
    return texto_upper(getattr(conta, "status", None)) == "CANCELADO"


def conta_esta_aberta(conta):
    return texto_upper(getattr(conta, "status", None)) in ["", "PENDENTE", "ADIADO", "ABERTO", "EM ABERTO"]


def tipo_obrigacao_conta(conta):
    if getattr(conta, "total_parcelas", None):
        return "PARCELADA"

    if getattr(conta, "recorrente", False):
        return "RECORRENTE"

    return "UNICA"


def parcela_label(conta):
    if getattr(conta, "parcela_atual", None) and getattr(conta, "total_parcelas", None):
        return f"{conta.parcela_atual}/{conta.total_parcelas}"

    if getattr(conta, "parcela_atual", None):
        return str(conta.parcela_atual)

    return "-"


def competencia_label(data_ref):
    data_ref = data_para_date(data_ref)
    if not data_ref:
        return "-"
    return f"{nome_mes(data_ref.month)}/{data_ref.year}"


def criar_conta_radar(
    descricao,
    fornecedor,
    categoria,
    setor,
    valor,
    data_vencimento,
    status="PENDENTE",
    data_pagamento=None,
    observacoes="",
    parcela_atual=None,
    total_parcelas=None,
    recorrente=False,
    gerado_por_transporte=False,
    conta_origem_id=None,
):
    conta = ContaRadarFinanceiro(
        descricao=texto(descricao) or "SEM DESCRIÇÃO",
        fornecedor=texto(fornecedor),
        categoria=texto(categoria),
        setor=texto_upper(setor) or "ASSISTÊNCIA",
        valor=normalizar_decimal(valor),
        data_vencimento=(inicio_dia_datetime(data_vencimento) if data_vencimento else None),
        data_pagamento=(inicio_dia_datetime(data_pagamento) if data_pagamento else None),
        status=texto_upper(status) or "PENDENTE",
        observacoes=texto(observacoes),
        parcela_atual=parcela_atual,
        total_parcelas=total_parcelas,
        recorrente=bool(recorrente),
        gerado_por_transporte=bool(gerado_por_transporte),
        conta_origem_id=conta_origem_id,
        mes=data_vencimento.month if data_vencimento else None,
        ano=data_vencimento.year if data_vencimento else None,
    )

    db.session.add(conta)
    return conta


def conta_transportada_ja_existe(conta_origem, mes_destino, ano_destino):
    if not conta_origem or not getattr(conta_origem, "id", None):
        return None

    return ContaRadarFinanceiro.query.filter(
        ContaRadarFinanceiro.conta_origem_id == conta_origem.id,
        ContaRadarFinanceiro.mes == mes_destino,
        ContaRadarFinanceiro.ano == ano_destino,
        ContaRadarFinanceiro.status != "CANCELADO",
    ).first()


def conta_eh_parcelada(conta):
    return bool(getattr(conta, "total_parcelas", None))


def conta_eh_recorrente(conta):
    return bool(getattr(conta, "recorrente", False))


def conta_deve_entrar_como_herdada(conta, mes_contexto, ano_contexto):
    if not conta or conta_esta_paga(conta) or conta_esta_cancelada(conta):
        return False

    if not conta_esta_aberta(conta):
        return False

    vencimento = data_para_date(getattr(conta, "data_vencimento", None))

    if not vencimento or not mes_contexto or not ano_contexto:
        return False

    eh_obrigacao_continua = conta_eh_parcelada(conta) or conta_eh_recorrente(conta)

    return eh_obrigacao_continua and vencimento < primeiro_dia_mes(int(mes_contexto), int(ano_contexto))


def conta_continua_herdada(conta, mes_contexto, ano_contexto):
    return conta_deve_entrar_como_herdada(conta, mes_contexto, ano_contexto)


def atualizar_conta_por_form(conta):
    data_vencimento = parse_data(request.form.get("data_vencimento"))
    data_pagamento = parse_data(request.form.get("data_pagamento"))
    status = texto_upper(request.form.get("status")) or "PENDENTE"
    tipo_obrigacao = texto_upper(request.form.get("tipo_obrigacao")) or "UNICA"

    if not data_vencimento:
        raise ValueError("Informe uma data de vencimento válida.")

    conta.descricao = texto(request.form.get("descricao")) or conta.descricao
    conta.fornecedor = texto(request.form.get("fornecedor"))
    conta.categoria = texto(request.form.get("categoria"))
    conta.setor = texto_upper(request.form.get("setor")) or "ASSISTÊNCIA"
    conta.valor = normalizar_decimal(request.form.get("valor"))
    conta.data_vencimento = inicio_dia_datetime(data_vencimento)
    conta.status = status
    conta.observacoes = texto(request.form.get("observacoes"))
    conta.recorrente = tipo_obrigacao == "RECORRENTE" or request.form.get("recorrente") == "on"

    if status == "PAGO":
        conta.data_pagamento = inicio_dia_datetime(data_pagamento or date.today())
    else:
        conta.data_pagamento = None

    if tipo_obrigacao == "PARCELADA":
        conta.parcela_atual = request.form.get("parcela_atual", type=int)
        conta.total_parcelas = request.form.get("total_parcelas", type=int)
    else:
        conta.parcela_atual = None
        conta.total_parcelas = None

    conta.mes = data_vencimento.month
    conta.ano = data_vencimento.year

    return data_vencimento


def calcular_valor_final_com_juros(valor_original, valor_final_informado):
    """
    Recebe o valor original da fatura e, se informado, o valor final com juros.
    Retorna: valor_original, valor_final, juros_calculado.
    Não muda estrutura do banco: o campo valor continua recebendo o valor final.
    """
    valor_original = normalizar_decimal(valor_original)
    valor_final = normalizar_decimal(valor_final_informado)

    if valor_final <= Decimal("0.00"):
        return valor_original, valor_original, Decimal("0.00")

    if valor_final < valor_original:
        raise ValueError("O valor com juros não pode ser menor que o valor original da fatura.")

    juros_calculado = (valor_final - valor_original).quantize(Decimal("0.01"))
    return valor_original, valor_final, juros_calculado


def montar_observacao_valor_com_juros(obs_original, valor_original, valor_final, juros_calculado, contexto="cadastro", numero_parcela=None, total_parcelas=None):
    obs = texto(obs_original)

    if juros_calculado <= Decimal("0.00"):
        return obs

    linhas = []

    if obs:
        linhas.append(obs)

    detalhe = (
        f"Valor com juros calculado automaticamente no {contexto}: "
        f"Valor original: {moeda(valor_original)} | "
        f"Juros/acréscimo: {moeda(juros_calculado)} | "
        f"Valor final: {moeda(valor_final)}"
    )

    if numero_parcela and total_parcelas:
        detalhe = f"Parcela {numero_parcela}/{total_parcelas} - " + detalhe

    linhas.append(detalhe)
    return "\n".join(linhas)


def aplicar_juros_modal_na_conta(conta):
    """
    No modal, o usuário informa o valor original e opcionalmente o valor com juros.
    A diferença é calculada automaticamente e o valor final fica salvo em conta.valor.
    """
    valor_original, valor_final, juros_calculado = calcular_valor_final_com_juros(
        request.form.get("valor"),
        request.form.get("valor_com_juros")
    )

    if juros_calculado <= Decimal("0.00"):
        return False

    conta.valor = valor_final

    conta.observacoes = montar_observacao_valor_com_juros(
        getattr(conta, "observacoes", ""),
        valor_original=valor_original,
        valor_final=valor_final,
        juros_calculado=juros_calculado,
        contexto="modal"
    )

    return True


def conta_recorrente_ja_existe(conta_origem, data_destino):
    """
    Evita duplicar recorrências do mesmo mês/ano quando uma conta é editada.
    Primeiro procura pelo vínculo de origem; depois confere os dados principais da conta.
    """
    if not conta_origem or not data_destino:
        return None

    return ContaRadarFinanceiro.query.filter(
        ContaRadarFinanceiro.status != "CANCELADO",
        ContaRadarFinanceiro.mes == data_destino.month,
        ContaRadarFinanceiro.ano == data_destino.year,
        or_(
            ContaRadarFinanceiro.conta_origem_id == conta_origem.id,
            and_(
                ContaRadarFinanceiro.descricao == conta_origem.descricao,
                ContaRadarFinanceiro.fornecedor == conta_origem.fornecedor,
                ContaRadarFinanceiro.categoria == conta_origem.categoria,
                ContaRadarFinanceiro.setor == conta_origem.setor,
                ContaRadarFinanceiro.data_vencimento >= inicio_dia_datetime(data_destino),
                ContaRadarFinanceiro.data_vencimento <= fim_dia_datetime(data_destino),
                ContaRadarFinanceiro.recorrente == True,
            )
        )
    ).first()


def gerar_recorrencias_futuras_ate_dezembro(conta, data_vencimento):
    """
    Quando uma conta é editada e marcada como recorrente, cria as próximas
    competências até dezembro do mesmo ano, sem duplicar meses já existentes.
    """
    if not conta or not data_vencimento:
        return 0

    if not getattr(conta, "recorrente", False):
        return 0

    if getattr(conta, "total_parcelas", None):
        return 0

    criadas = 0
    mes_inicial = data_vencimento.month

    for mes_destino in range(mes_inicial + 1, 13):
        deslocamento = mes_destino - mes_inicial
        vencimento_recorrente = adicionar_meses(data_vencimento, deslocamento)

        if conta_recorrente_ja_existe(conta, vencimento_recorrente):
            continue

        criar_conta_radar(
            descricao=conta.descricao,
            fornecedor=conta.fornecedor,
            categoria=conta.categoria,
            setor=conta.setor,
            valor=conta.valor,
            data_vencimento=vencimento_recorrente,
            status="PENDENTE",
            data_pagamento=None,
            observacoes=conta.observacoes,
            parcela_atual=None,
            total_parcelas=None,
            recorrente=True,
            gerado_por_transporte=True,
            conta_origem_id=conta.id,
        )
        criadas += 1

    return criadas


# =========================================================
# SERIALIZAÇÃO PARA TEMPLATE
# =========================================================

def status_visual(conta, hoje):
    status = texto_upper(conta.status)
    venc = data_para_date(conta.data_vencimento)

    if status == "PAGO":
        return "PAGO", "pago"

    if status == "CANCELADO":
        return "CANCELADO", "cancelado"

    if status == "ADIADO":
        return "ADIADO", "proxima"

    if venc and venc < hoje:
        return "ATRASADA", "vencido"

    if venc and venc == hoje:
        return "VENCE HOJE", "vence-hoje"

    return "EM ABERTO", "aberto"


def montar_item(conta, hoje):
    venc = data_para_date(conta.data_vencimento)
    pgto = data_para_date(conta.data_pagamento)
    status_label, status_classe = status_visual(conta, hoje)
    dias_atraso = 0
    dias_para_vencer = None

    if venc and not conta_esta_paga(conta):
        if venc < hoje:
            dias_atraso = (hoje - venc).days
        else:
            dias_para_vencer = (venc - hoje).days

    return {
        "id": conta.id,
        "descricao": conta.descricao or "SEM DESCRIÇÃO",
        "fornecedor": conta.fornecedor or "-",
        "categoria": conta.categoria or "-",
        "setor": conta.setor or "GERAL",
        "valor": dinheiro(conta.valor),
        "valor_formatado": moeda(conta.valor),
        "data_vencimento": venc,
        "data_vencimento_input": data_para_input(conta.data_vencimento),
        "data_vencimento_formatada": data_br(conta.data_vencimento),
        "data_pagamento": pgto,
        "data_pagamento_input": data_para_input(conta.data_pagamento),
        "data_pagamento_formatada": data_br(conta.data_pagamento),
        "pago": conta_esta_paga(conta),
        "status": texto_upper(conta.status) or "PENDENTE",
        "status_label": status_label,
        "status_classe": status_classe,
        "observacoes": conta.observacoes or "",
        "recorrente": bool(conta.recorrente),
        "parcelada": bool(conta.total_parcelas),
        "parcela_atual": conta.parcela_atual,
        "total_parcelas": conta.total_parcelas,
        "parcela_label": parcela_label(conta),
        "tipo_obrigacao": tipo_obrigacao_conta(conta),
        "dias_atraso": dias_atraso,
        "dias_para_vencer": dias_para_vencer,
        "competencia": competencia_label(venc),
        "grupo_key": grupo_key_conta(conta),
    }


def coluna(slug, titulo, subtitulo, cor, itens=None, grupos=None, vazia="Sem contas nesta coluna"):
    itens = itens or []
    grupos = grupos or []
    total = sum(dinheiro(item.get("valor")) for item in itens)

    if slug == "herdada":
        total = sum(dinheiro(g.get("total")) for g in grupos)
        badge = sum(int(g.get("qtd") or 0) for g in grupos)
    else:
        badge = len(itens)

    return {
        "slug": slug,
        "titulo": titulo,
        "subtitulo": subtitulo,
        "cor": cor,
        "itens": itens,
        "grupos": grupos,
        "badge": badge,
        "total": total,
        "total_formatado": moeda(total),
        "vazia": vazia,
    }


def montar_grupos_herdados(contas_herdadas, hoje):
    grupos_map = {}

    for conta in contas_herdadas:
        item = montar_item(conta, hoje)
        key = item["grupo_key"]

        if key not in grupos_map:
            grupos_map[key] = {
                "grupo_key": key,
                "descricao": item["descricao"],
                "fornecedor": item["fornecedor"],
                "categoria": item["categoria"],
                "setor": item["setor"],
                "historico": [],
                "total": 0,
                "qtd": 0,
                "maior_atraso": 0,
            }

        grupos_map[key]["historico"].append(item)
        grupos_map[key]["total"] += item["valor"]
        grupos_map[key]["qtd"] += 1
        grupos_map[key]["maior_atraso"] = max(grupos_map[key]["maior_atraso"], item["dias_atraso"] or 0)

    grupos = []
    for grupo in grupos_map.values():
        grupo["historico"] = sorted(
            grupo["historico"],
            key=lambda item: item["data_vencimento"] or date.min,
        )

        atrasos = [item["dias_atraso"] or 0 for item in grupo["historico"]]
        atraso_medio = int(sum(atrasos) / len(atrasos)) if atrasos else 0
        primeiro = grupo["historico"][0] if grupo["historico"] else None
        parcelas = [item["parcela_label"] for item in grupo["historico"] if item["parcela_label"] != "-"]

        grupo.update({
            "total_formatado": moeda(grupo["total"]),
            "valor_parcela_formatado": moeda(grupo["historico"][-1]["valor"]) if grupo["historico"] else None,
            "desde_label": primeiro["competencia"] if primeiro else "-",
            "atraso_medio": atraso_medio,
            "parcelas_resumo": ", ".join(parcelas[:4]) + ("..." if len(parcelas) > 4 else ""),
            "tipo_grupo": "PARCELADA" if any(item.get("parcelada") for item in grupo["historico"]) else "RECORRENTE",
        })
        grupos.append(grupo)

    return sorted(grupos, key=lambda g: (g["historico"][0]["data_vencimento"] if g["historico"] else date.max))


# =========================================================
# TELEGRAM
# =========================================================

def buscar_contas_vencendo_hoje(data_ref=None):
    data_ref = data_ref or date.today()
    inicio = inicio_dia_datetime(data_ref)
    fim = fim_dia_datetime(data_ref)

    return ContaRadarFinanceiro.query.filter(
        ContaRadarFinanceiro.data_vencimento >= inicio,
        ContaRadarFinanceiro.data_vencimento <= fim,
        ContaRadarFinanceiro.status.in_(["PENDENTE", "ADIADO"]),
    ).order_by(
        ContaRadarFinanceiro.data_vencimento.asc(),
        ContaRadarFinanceiro.id.asc(),
    ).all()


def executar_envio_alerta_telegram_hoje():
    hoje = date.today()
    contas = buscar_contas_vencendo_hoje(hoje)

    if not contas:
        return {
            "ok": True,
            "enviado": False,
            "total_contas": 0,
            "mensagem": "Nenhuma conta pendente vencendo hoje.",
        }

    mensagem = montar_mensagem_contas_vencendo_hoje(contas=contas, data_ref=hoje)
    sucesso, retorno = enviar_mensagem_telegram(mensagem)

    return {
        "ok": bool(sucesso),
        "enviado": bool(sucesso),
        "total_contas": len(contas),
        "mensagem": retorno,
    }


# =========================================================
# RADAR FINANCEIRO
# =========================================================

@radar_financeiro_bp.route("")
@radar_financeiro_bp.route("/")
@gestao_required
def index():
    hoje = date.today()
    agora = datetime.now()

    mes = request.args.get("mes", type=int) or agora.month
    ano = request.args.get("ano", type=int) or agora.year
    setor = texto_upper(request.args.get("setor"))
    busca = texto(request.args.get("busca"))
    visao = texto(request.args.get("visao")) or "vencimento"
    grupo_key = texto(request.args.get("grupo"))

    if not 1 <= mes <= 12:
        mes = agora.month

    primeiro_mes = primeiro_dia_mes(mes, ano)
    ultimo_mes = ultimo_dia_mes(mes, ano)

    query = ContaRadarFinanceiro.query.filter(
        ContaRadarFinanceiro.status != "CANCELADO"
    )

    if setor:
        query = query.filter(ContaRadarFinanceiro.setor == setor)

    if busca:
        like = f"%{busca}%"
        query = query.filter(
            or_(
                ContaRadarFinanceiro.descricao.ilike(like),
                ContaRadarFinanceiro.fornecedor.ilike(like),
                ContaRadarFinanceiro.categoria.ilike(like),
                ContaRadarFinanceiro.observacoes.ilike(like),
            )
        )

    contas = query.order_by(
        ContaRadarFinanceiro.data_vencimento.asc().nullslast(),
        ContaRadarFinanceiro.id.asc(),
    ).all()

    herdadas_contas = []
    hoje_itens = []
    proximos_7_itens = []
    atrasadas_mes_itens = []
    pagas_mes_itens = []
    pagas_antigas_itens = []
    ate_fim_mes_itens = []

    for conta in contas:
        venc = data_para_date(conta.data_vencimento)
        pgto = data_para_date(conta.data_pagamento)
        item = montar_item(conta, hoje)

        if conta_esta_paga(conta):
            # PAGAS NO MÊS = tudo que saiu do caixa dentro do mês filtrado.
            # PAGAS DE MESES ANT. = subset das pagas no mês, mas com vencimento anterior
            # ao mês filtrado. Não aparece em meses seguintes e não soma duas vezes no fluxo.
            if pgto and primeiro_mes <= pgto <= ultimo_mes:
                pagas_mes_itens.append(item)

                if venc and venc < primeiro_mes:
                    pagas_antigas_itens.append(item)

            continue

        if not conta_esta_aberta(conta):
            continue

        if not venc:
            ate_fim_mes_itens.append(item)
            continue

        # DÍVIDA HERDADA:
        # entra aqui somente obrigação contínua antiga em aberto
        # (parcelada ou recorrente) com vencimento anterior ao mês filtrado.
        # Contas únicas antigas não são jogadas automaticamente na dívida herdada.
        if conta_deve_entrar_como_herdada(conta, mes, ano):
            herdadas_contas.append(conta)
            continue

        if venc > ultimo_mes:
            continue

        if venc < hoje:
            atrasadas_mes_itens.append(item)
        elif venc == hoje:
            hoje_itens.append(item)
        elif venc <= hoje + timedelta(days=7):
            proximos_7_itens.append(item)
        else:
            ate_fim_mes_itens.append(item)

    grupos_herdados = montar_grupos_herdados(herdadas_contas, hoje)
    grupo_selecionado = next((g for g in grupos_herdados if g["grupo_key"] == grupo_key), None)

    colunas = [
        coluna(
            "herdada",
            "DÍVIDA HERDADA",
            "Contas antigas em aberto",
            "danger",
            grupos=grupos_herdados,
            vazia="Sem dívida herdada",
        ),
        coluna("vence_hoje", "VENCE HOJE", f"Vencem hoje ({hoje.strftime('%d/%m/%Y')})", "warning", hoje_itens, vazia="Sem contas para hoje"),
        coluna("proximos_7", "PRÓXIMOS 7 DIAS", "Contas próximas do vencimento", "purple", proximos_7_itens, vazia="Sem contas nos próximos 7 dias"),
        coluna("atrasadas_mes", "ATRASADAS DO MÊS", "Venceram neste mês", "blue", atrasadas_mes_itens, vazia="Sem atrasadas neste mês"),
        coluna("pagas_mes", "PAGAS NO MÊS", f"Pagas em {nome_mes(mes)}", "success", pagas_mes_itens, vazia="Sem pagas no mês"),
        coluna("pagas_antigas", "PAGAS DE MESES ANT.", "Pagas antes do mês filtrado", "teal", pagas_antigas_itens, vazia="Sem pagas antigas"),
        coluna("ate_fim_mes", "ATÉ FIM DO MÊS", "Contas futuras dentro do mês filtrado", "neutral", ate_fim_mes_itens, vazia="Sem contas futuras no mês"),
    ]

    total_divida_herdada = colunas[0]["total"]
    total_hoje = colunas[1]["total"]
    total_proximos_7 = colunas[2]["total"]
    total_atrasadas_mes = colunas[3]["total"]
    total_pagas_mes = colunas[4]["total"]
    total_pagas_meses_anteriores = colunas[5]["total"]
    total_ate_fim_mes = colunas[6]["total"]

    pressao_imediata = total_divida_herdada + total_hoje + total_proximos_7 + total_atrasadas_mes + total_ate_fim_mes
    receitas_realizadas = 0
    receitas_previstas = 0
    resultado_parcial = receitas_realizadas - total_pagas_mes
    diferenca_estimada = receitas_previstas - pressao_imediata

    if pressao_imediata <= 0:
        risco = "Controlado"
        risco_classe = "success"
    elif total_divida_herdada > 0 or total_atrasadas_mes > 0:
        risco = "Atenção"
        risco_classe = "warning"
    else:
        risco = "Monitorar"
        risco_classe = "neutral"

    top_despesas = sorted(
        pagas_mes_itens,
        key=lambda item: item["valor"],
        reverse=True,
    )[:5]

    top_despesas = [
        {
            "nome": item["descricao"],
            "valor": item["valor"],
            "valor_formatado": item["valor_formatado"],
        }
        for item in top_despesas
    ]

    insight = "Dívida herdada mostra parcelas/recorrências antigas em aberto. Ao pagar, a obrigação sai automaticamente da coluna herdada."
    recomendacao = "Priorize as parcelas herdadas mais antigas e mantenha o mês atual separado das dívidas anteriores."

    return render_template(
        "gestao/radar_financeiro.html",
        hoje=hoje,
        mes=mes,
        ano=ano,
        setor=setor,
        busca=busca,
        visao=visao,
        colunas=colunas,
        grupos_herdados=grupos_herdados,
        grupo_selecionado=grupo_selecionado,
        total_divida_herdada=total_divida_herdada,
        total_hoje=total_hoje,
        total_proximos_7=total_proximos_7,
        total_atrasadas_mes=total_atrasadas_mes,
        total_pagas_mes=total_pagas_mes,
        total_pagas_meses_anteriores=total_pagas_meses_anteriores,
        pressao_imediata=pressao_imediata,
        receitas_realizadas=receitas_realizadas,
        receitas_previstas=receitas_previstas,
        resultado_parcial=resultado_parcial,
        diferenca_estimada=diferenca_estimada,
        risco=risco,
        risco_classe=risco_classe,
        insight=insight,
        recomendacao=recomendacao,
        top_despesas=top_despesas,
        moeda=moeda,
        nome_mes=nome_mes,
        nome_mes_curto=nome_mes_curto,
    )


# =========================================================
# AÇÕES
# =========================================================

@radar_financeiro_bp.route("/novo", methods=["POST"])
@gestao_required
def novo():
    try:
        data_vencimento = parse_data(request.form.get("data_vencimento"))
        data_pagamento = parse_data(request.form.get("data_pagamento"))

        if not data_vencimento:
            flash("Informe uma data de vencimento válida.", "danger")
            return redirect_contexto_form()

        status_padrao = "PAGO" if request.form.get("ja_pago") == "on" else "PENDENTE"

        if status_padrao == "PAGO" and not data_pagamento:
            data_pagamento = date.today()

        tipo_obrigacao = texto_upper(request.form.get("tipo_obrigacao")) or "UNICA"

        # Este campo passa a significar: PRIMEIRA PARCELA A CADASTRAR.
        # Ex.: primeira=4, total=6, vencimento=Maio/2026 => cria 4/6 Maio, 5/6 Junho, 6/6 Julho.
        parcela_atual = request.form.get("parcela_atual", type=int)
        total_parcelas = request.form.get("total_parcelas", type=int)

        recorrente = request.form.get("recorrente") == "on" or tipo_obrigacao == "RECORRENTE"

        descricao = request.form.get("descricao")
        fornecedor = request.form.get("fornecedor")
        categoria = request.form.get("categoria")
        setor = request.form.get("setor")
        valor_original_fatura = request.form.get("valor")
        valor_com_juros_form = request.form.get("valor_com_juros")

        valor_base, valor_final_informado, juros_valor = calcular_valor_final_com_juros(
            valor_original_fatura,
            valor_com_juros_form
        )

        juros_aplicar = texto_upper(request.form.get("juros_aplicar")) or "PRIMEIRA"
        observacoes = request.form.get("observacoes")

        if tipo_obrigacao == "PARCELADA":
            if not parcela_atual or not total_parcelas:
                flash("Informe a primeira parcela a cadastrar e o total de parcelas.", "danger")
                return redirect_contexto_form(data_vencimento)

            if parcela_atual < 1 or total_parcelas < 1 or parcela_atual > total_parcelas:
                flash("Informe parcela inicial e total de parcelas válidos.", "danger")
                return redirect_contexto_form(data_vencimento)

            quantidade_criada = 0

            for numero_parcela in range(parcela_atual, total_parcelas + 1):
                deslocamento = numero_parcela - parcela_atual
                vencimento_parcela = adicionar_meses(data_vencimento, deslocamento)

                status_parcela = "PENDENTE"
                pagamento_parcela = None

                # Se marcou como paga, considera paga somente a primeira parcela informada.
                if status_padrao == "PAGO" and numero_parcela == parcela_atual:
                    status_parcela = "PAGO"
                    pagamento_parcela = data_pagamento

                aplica_juros_parcela = juros_valor > Decimal("0.00") and (
                    juros_aplicar == "TODAS" or numero_parcela == parcela_atual
                )
                valor_parcela = valor_base + juros_valor if aplica_juros_parcela else valor_base

                criar_conta_radar(
                    descricao=descricao,
                    fornecedor=fornecedor,
                    categoria=categoria,
                    setor=setor,
                    valor=valor_parcela,
                    data_vencimento=vencimento_parcela,
                    status=status_parcela,
                    data_pagamento=pagamento_parcela,
                    observacoes=montar_observacao_valor_com_juros(
                        observacoes,
                        valor_original=valor_base,
                        valor_final=valor_parcela,
                        juros_calculado=juros_valor,
                        contexto="cadastro",
                        numero_parcela=numero_parcela,
                        total_parcelas=total_parcelas,
                    ) if aplica_juros_parcela else observacoes,
                    parcela_atual=numero_parcela,
                    total_parcelas=total_parcelas,
                    recorrente=False,
                )
                quantidade_criada += 1

            db.session.commit()
            flash(
                f"Conta parcelada criada com {quantidade_criada} parcela(s), começando em {parcela_atual}/{total_parcelas}.",
                "success"
            )
            return redirect_contexto_form(data_vencimento)

        parcela_atual = None
        total_parcelas = None

        # RECORRENTE MENSAL:
        # Cria automaticamente uma conta por mês, do vencimento inicial até dezembro do mesmo ano.
        # Ex.: vencimento 10/05/2026 => cria 10/05, 10/06, 10/07 ... 10/12.
        # Se marcar como paga, somente a primeira competência entra como PAGO.
        if recorrente:
            quantidade_criada = 0
            mes_inicial = data_vencimento.month
            ano_inicial = data_vencimento.year

            for mes_destino in range(mes_inicial, 13):
                deslocamento = mes_destino - mes_inicial
                vencimento_recorrente = adicionar_meses(data_vencimento, deslocamento)

                status_recorrente = "PENDENTE"
                pagamento_recorrente = None

                if status_padrao == "PAGO" and mes_destino == mes_inicial:
                    status_recorrente = "PAGO"
                    pagamento_recorrente = data_pagamento

                aplica_juros_recorrente = juros_valor > Decimal("0.00") and (
                    juros_aplicar == "TODAS" or mes_destino == mes_inicial
                )

                valor_recorrente = valor_base + juros_valor if aplica_juros_recorrente else valor_base

                criar_conta_radar(
                    descricao=descricao,
                    fornecedor=fornecedor,
                    categoria=categoria,
                    setor=setor,
                    valor=valor_recorrente,
                    data_vencimento=vencimento_recorrente,
                    status=status_recorrente,
                    data_pagamento=pagamento_recorrente,
                    observacoes=montar_observacao_valor_com_juros(
                        observacoes,
                        valor_original=valor_base,
                        valor_final=valor_recorrente,
                        juros_calculado=juros_valor,
                        contexto="cadastro recorrente",
                    ) if aplica_juros_recorrente else observacoes,
                    parcela_atual=None,
                    total_parcelas=None,
                    recorrente=True,
                )

                quantidade_criada += 1

            db.session.commit()
            flash(
                f"Conta recorrente criada com {quantidade_criada} competência(s), de {nome_mes(mes_inicial)}/{ano_inicial} até Dezembro/{ano_inicial}.",
                "success"
            )
            return redirect_contexto_form(data_vencimento)

        valor_conta = valor_final_informado if juros_valor > Decimal("0.00") else valor_base

        criar_conta_radar(
            descricao=descricao,
            fornecedor=fornecedor,
            categoria=categoria,
            setor=setor,
            valor=valor_conta,
            data_vencimento=data_vencimento,
            status=status_padrao,
            data_pagamento=data_pagamento if status_padrao == "PAGO" else None,
            observacoes=montar_observacao_valor_com_juros(
                observacoes,
                valor_original=valor_base,
                valor_final=valor_conta,
                juros_calculado=juros_valor,
                contexto="cadastro"
            ),
            parcela_atual=parcela_atual,
            total_parcelas=total_parcelas,
            recorrente=False,
        )

        db.session.commit()
        flash("Conta criada no Radar.", "success")
        return redirect_contexto_form(data_vencimento)

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao criar conta: {str(e)}", "danger")
        return redirect_contexto_form()


@radar_financeiro_bp.route("/editar/<int:id>", methods=["POST"])
@gestao_required
def editar(id):
    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:
        data_vencimento = atualizar_conta_por_form(conta)
        aplicar_juros_modal_na_conta(conta)
        db.session.flush()

        recorrencias_criadas = gerar_recorrencias_futuras_ate_dezembro(conta, data_vencimento)

        db.session.commit()

        if recorrencias_criadas:
            flash(f"Conta atualizada e {recorrencias_criadas} recorrência(s) futura(s) criada(s) até dezembro.", "success")
        else:
            flash("Conta atualizada com sucesso.", "success")

        return redirect_contexto_form(data_vencimento)

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao editar conta: {str(e)}", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")


@radar_financeiro_bp.route("/pagar/<int:id>", methods=["POST"])
@gestao_required
def pagar(id):
    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:
        data_pagamento = parse_data(request.form.get("data_pagamento")) or date.today()
        conta.status = "PAGO"
        conta.data_pagamento = inicio_dia_datetime(data_pagamento)
        db.session.commit()
        flash("Conta marcada como paga.", "success")
        return redirect_contexto_form(data_pagamento)
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao pagar conta: {str(e)}", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")


@radar_financeiro_bp.route("/api/herdadas/pagar", methods=["POST"])
@gestao_required
def api_herdadas_pagar():
    ids = ids_limpos_formulario("contas_ids")
    data_pagamento = parse_data(request.form.get("data_pagamento")) or date.today()

    if not ids:
        return jsonify({"ok": False, "message": "Selecione ao menos uma parcela."}), 400

    try:
        contas = ContaRadarFinanceiro.query.filter(ContaRadarFinanceiro.id.in_(ids)).all()

        for conta in contas:
            conta.status = "PAGO"
            conta.data_pagamento = inicio_dia_datetime(data_pagamento)

        db.session.commit()

        return jsonify({
            "ok": True,
            "message": f"{len(contas)} parcela(s) marcada(s) como paga(s).",
            "ids": [conta.id for conta in contas],
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": f"Erro ao pagar parcelas: {str(e)}"}), 500


@radar_financeiro_bp.route("/api/herdadas/excluir", methods=["POST"])
@gestao_required
def api_herdadas_excluir():
    ids = ids_limpos_formulario("contas_ids")

    if not ids:
        return jsonify({"ok": False, "message": "Selecione ao menos uma parcela."}), 400

    try:
        contas = ContaRadarFinanceiro.query.filter(ContaRadarFinanceiro.id.in_(ids)).all()

        for conta in contas:
            db.session.delete(conta)

        db.session.commit()

        return jsonify({
            "ok": True,
            "message": f"{len(contas)} parcela(s) excluída(s).",
            "ids": ids,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": f"Erro ao excluir parcelas: {str(e)}"}), 500


@radar_financeiro_bp.route("/api/herdadas/editar/<int:id>", methods=["POST"])
@gestao_required
def api_herdadas_editar(id):
    conta = ContaRadarFinanceiro.query.get_or_404(id)
    mes_contexto = request.form.get("mes_contexto", type=int)
    ano_contexto = request.form.get("ano_contexto", type=int)

    try:
        data_vencimento = atualizar_conta_por_form(conta)
        aplicar_juros_modal_na_conta(conta)
        db.session.flush()

        recorrencias_criadas = gerar_recorrencias_futuras_ate_dezembro(conta, data_vencimento)

        db.session.commit()

        item = montar_item(conta, date.today())

        return jsonify({
            "ok": True,
            "message": "Parcela atualizada com sucesso." + (f" {recorrencias_criadas} recorrência(s) futura(s) criada(s) até dezembro." if recorrencias_criadas else ""),
            "id": conta.id,
            "continua_herdada": conta_continua_herdada(conta, mes_contexto, ano_contexto),
            "item": {
                "competencia": item["competencia"],
                "parcela_label": item["parcela_label"],
                "data_vencimento_formatada": item["data_vencimento_formatada"],
                "valor_formatado": item["valor_formatado"],
                "valor": item["valor"],
                "dias_atraso": item["dias_atraso"],
                "status_label": item["status_label"],
                "status_classe": item["status_classe"],
            },
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": f"Erro ao editar parcela: {str(e)}"}), 500


@radar_financeiro_bp.route("/transportar/<int:id>", methods=["POST"])
@gestao_required
def transportar(id):
    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:
        if not conta_esta_paga(conta):
            flash("Somente contas pagas podem ser transportadas.", "warning")
            return redirect(request.referrer or "/gestao/radar-financeiro/")

        mes_destino = request.form.get("mes_destino", type=int)
        ano_destino = request.form.get("ano_destino", type=int)

        if not mes_destino or not ano_destino or mes_destino < 1 or mes_destino > 12:
            flash("Informe mês e ano de destino válidos.", "danger")
            return redirect(request.referrer or "/gestao/radar-financeiro/")

        if conta_transportada_ja_existe(conta, mes_destino, ano_destino):
            flash("Essa conta já foi transportada para o mês selecionado.", "warning")
            return redirect_radar(mes_destino, ano_destino)

        data_base = data_para_date(conta.data_vencimento) or date.today()
        nova_data = ajustar_data_para_mes_ano(data_base, mes_destino, ano_destino)

        criar_conta_radar(
            descricao=conta.descricao,
            fornecedor=conta.fornecedor,
            categoria=conta.categoria,
            setor=conta.setor,
            valor=conta.valor,
            data_vencimento=nova_data,
            status="PENDENTE",
            data_pagamento=None,
            observacoes=conta.observacoes,
            parcela_atual=conta.parcela_atual,
            total_parcelas=conta.total_parcelas,
            recorrente=conta.recorrente,
            gerado_por_transporte=True,
            conta_origem_id=conta.id,
        )

        db.session.commit()
        flash("Conta transportada para o mês destino.", "success")
        return redirect_radar(mes_destino, ano_destino)

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao transportar conta: {str(e)}", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")


@radar_financeiro_bp.route("/transportar-lote", methods=["POST"])
@gestao_required
def transportar_lote():
    ids = ids_limpos_formulario("contas_ids")
    mes_destino = request.form.get("mes_destino", type=int)
    ano_destino = request.form.get("ano_destino", type=int)
    observacao_extra = texto(request.form.get("observacoes"))

    if not ids:
        flash("Selecione pelo menos uma conta paga para transportar.", "warning")
        return redirect(request.referrer or "/gestao/radar-financeiro/")

    if not mes_destino or not ano_destino or mes_destino < 1 or mes_destino > 12:
        flash("Informe mês e ano de destino válidos.", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")

    total = 0
    duplicadas = 0
    nao_pagas = 0

    try:
        contas = ContaRadarFinanceiro.query.filter(ContaRadarFinanceiro.id.in_(ids)).all()

        for conta in contas:
            if not conta_esta_paga(conta):
                nao_pagas += 1
                continue

            if conta_transportada_ja_existe(conta, mes_destino, ano_destino):
                duplicadas += 1
                continue

            data_base = data_para_date(conta.data_vencimento) or date.today()
            nova_data = ajustar_data_para_mes_ano(data_base, mes_destino, ano_destino)
            observacoes = conta.observacoes or ""
            if observacao_extra:
                observacoes = f"{observacoes}\n{observacao_extra}".strip()

            criar_conta_radar(
                descricao=conta.descricao,
                fornecedor=conta.fornecedor,
                categoria=conta.categoria,
                setor=conta.setor,
                valor=conta.valor,
                data_vencimento=nova_data,
                status="PENDENTE",
                data_pagamento=None,
                observacoes=observacoes,
                parcela_atual=conta.parcela_atual,
                total_parcelas=conta.total_parcelas,
                recorrente=conta.recorrente,
                gerado_por_transporte=True,
                conta_origem_id=conta.id,
            )
            total += 1

        db.session.commit()
        flash(f"{total} conta(s) transportada(s). Duplicadas ignoradas: {duplicadas}. Não pagas ignoradas: {nao_pagas}.", "success")
        return redirect_radar(mes_destino, ano_destino)

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao transportar em lote: {str(e)}", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")


@radar_financeiro_bp.route("/transportar-pagas-lote", methods=["POST"])
@gestao_required
def transportar_pagas_lote():
    return transportar_lote()


@radar_financeiro_bp.route("/cancelar/<int:id>", methods=["POST"])
@gestao_required
def cancelar(id):
    conta = ContaRadarFinanceiro.query.get_or_404(id)
    try:
        conta.status = "CANCELADO"
        db.session.commit()
        flash("Conta cancelada.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao cancelar conta: {str(e)}", "danger")
    return redirect(request.referrer or "/gestao/radar-financeiro/")


@radar_financeiro_bp.route("/excluir/<int:id>", methods=["POST"])
@gestao_required
def excluir(id):
    conta = ContaRadarFinanceiro.query.get_or_404(id)
    try:
        db.session.delete(conta)
        db.session.commit()
        flash("Conta excluída definitivamente.", "success")
        return redirect_contexto_form()
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir conta: {str(e)}", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")


@radar_financeiro_bp.route("/excluir-lote", methods=["POST"])
@gestao_required
def excluir_lote():
    ids = ids_limpos_formulario("contas_ids")
    mes_retorno = request.form.get("mes_retorno", type=int)
    ano_retorno = request.form.get("ano_retorno", type=int)

    if not ids:
        flash("Selecione pelo menos uma conta para excluir.", "warning")
        return redirect(request.referrer or "/gestao/radar-financeiro/")

    try:
        contas = ContaRadarFinanceiro.query.filter(ContaRadarFinanceiro.id.in_(ids)).all()
        total = len(contas)

        for conta in contas:
            db.session.delete(conta)

        db.session.commit()
        flash(f"{total} conta(s) excluída(s) definitivamente.", "success")

        if mes_retorno and ano_retorno:
            return redirect_radar(mes_retorno, ano_retorno)

        return redirect(request.referrer or "/gestao/radar-financeiro/")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir contas: {str(e)}", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")


# =========================================================
# TELEGRAM ROTAS
# =========================================================

@radar_financeiro_bp.route("/enviar-alerta-hoje", methods=["POST"])
@gestao_required
def enviar_alerta_telegram_hoje():
    try:
        resultado = executar_envio_alerta_telegram_hoje()
        if resultado["ok"] and resultado["enviado"]:
            flash(f"Alerta enviado no Telegram com {resultado['total_contas']} conta(s) vencendo hoje.", "success")
        elif resultado["ok"]:
            flash(resultado["mensagem"], "info")
        else:
            flash(resultado["mensagem"], "danger")
    except Exception as e:
        flash(f"Erro ao enviar alerta Telegram: {str(e)}", "danger")

    return redirect(request.referrer or "/gestao/radar-financeiro/")


@radar_financeiro_bp.route("/telegram/automatico", methods=["GET", "POST"])
def enviar_alerta_telegram_automatico():
    token_recebido = request.args.get("token") or request.form.get("token")
    token_correto = os.getenv("ALERTA_TELEGRAM_SECRET")

    if not token_correto:
        return jsonify({"ok": False, "erro": "ALERTA_TELEGRAM_SECRET não configurado."}), 500

    if not token_recebido or token_recebido != token_correto:
        return jsonify({"ok": False, "erro": "Token inválido."}), 403

    try:
        resultado = executar_envio_alerta_telegram_hoje()
        return jsonify(resultado), 200 if resultado.get("ok") else 500
    except Exception as e:
        return jsonify({"ok": False, "enviado": False, "erro": str(e)}), 500
