from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, render_template, request, jsonify, send_file
from sqlalchemy import or_
import hashlib
import re
import unicodedata
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from database import db
from utils.auth import gestao_required

from models.conta_pagar_importada import ContaPagarImportada
from models.conta_receber_importada import ContaReceberImportada
from models.planejamento_financeiro import PlanejamentoFinanceiro, PlanejamentoPagamento

from .radar_financeiro import (
    moeda,
    nome_mes,
    primeiro_dia_mes,
    ultimo_dia_mes,
    fim_dia_datetime,
)


planejamento_financeiro_bp = Blueprint(
    "planejamento_financeiro",
    __name__,
    url_prefix="/gestao/planejamento-financeiro",
)


def dinheiro_decimal(valor):
    if valor is None or valor == "":
        return Decimal("0")

    try:
        return Decimal(str(valor))
    except Exception:
        return Decimal("0")


def data_para_date_local(valor):
    if not valor:
        return None

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, date):
        return valor

    texto = str(valor).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato).date()
        except Exception:
            pass

    return None


def formatar_data(valor):
    data_ref = data_para_date_local(valor)
    if not data_ref:
        return "-"

    return data_ref.strftime("%d/%m/%Y")


def texto_limpo(valor, padrao="-"):
    if valor is None:
        return padrao

    texto = str(valor).strip()
    return texto if texto else padrao


def buscar_primeiro(conta, campos, padrao="-"):
    for campo in campos:
        valor = getattr(conta, campo, None)
        if valor not in (None, ""):
            return texto_limpo(valor, padrao)

    return padrao


def conta_esta_cancelada(conta):
    status = texto_limpo(getattr(conta, "status", None), "").upper()
    return status in ("CANCELADO", "CANCELADA")


def conta_esta_paga_local(conta):
    if bool(getattr(conta, "pago", False)):
        return True

    status = texto_limpo(getattr(conta, "status", None), "").upper()
    return status in ("PAGO", "RECEBIDO", "OK", "QUITADO", "BAIXADO")




def normalizar_chave(valor):
    """Normaliza texto para gerar uma chave estável entre reimportações."""
    if valor is None:
        return ""

    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto).strip().upper()
    return texto


def valor_chave(valor):
    return str(dinheiro_decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def gerar_chave_conta(conta):
    """
    Chave estável da conta. Não depende do ID criado pela importação.

    Usa os campos mais consistentes do relatório para reconhecer a mesma conta
    depois que a importação é apagada e recriada.
    """
    vencimento = data_para_date_local(getattr(conta, "data_vencimento", None))
    vencimento_txt = vencimento.isoformat() if vencimento else ""

    fornecedor = buscar_primeiro(
        conta,
        ["fornecedor_funcionario", "fornecedor", "cliente"],
        "",
    )
    conta_nome = buscar_primeiro(
        conta,
        ["plano_contas", "categoria", "descricao", "nome"],
        "",
    )
    documento = buscar_primeiro(
        conta,
        ["numero_fatura", "documento", "numero_documento", "nf", "nota_fiscal"],
        "",
    )
    parcela = buscar_primeiro(
        conta,
        ["parcela_label", "parcela", "numero_parcela"],
        "",
    )

    base = "|".join([
        normalizar_chave(fornecedor),
        normalizar_chave(conta_nome),
        normalizar_chave(documento),
        normalizar_chave(parcela),
        vencimento_txt,
        valor_chave(getattr(conta, "valor", 0)),
    ])

    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def preencher_snapshot_planejamento(registro, conta, chave_conta=None):
    """Atualiza o vínculo atual e preserva dados essenciais do planejamento."""
    registro.conta_id = int(getattr(conta, "id", 0))
    registro.chave_conta = chave_conta or gerar_chave_conta(conta)
    registro.descricao_snapshot = buscar_primeiro(
        conta, ["plano_contas", "categoria", "descricao", "nome"], "SEM CONTA"
    )
    registro.fornecedor_snapshot = buscar_primeiro(
        conta, ["fornecedor_funcionario", "fornecedor", "cliente"], "-"
    )
    registro.valor_snapshot = dinheiro_decimal(getattr(conta, "valor", 0))
    registro.vencimento_snapshot = data_para_date_local(getattr(conta, "data_vencimento", None))
    registro.observacao_snapshot = buscar_primeiro(
        conta, ["observacoes", "observacao", "historico", "descricao"], "-"
    )


def localizar_planejamento(conta, mes, ano, por_id=None, por_chave=None):
    conta_id = int(getattr(conta, "id", 0))
    chave = gerar_chave_conta(conta)

    registro = None
    if por_id is not None:
        registro = por_id.get(conta_id)
    if not registro and por_chave is not None:
        registro = por_chave.get(chave)

    if registro:
        mudou = registro.conta_id != conta_id or registro.chave_conta != chave
        preencher_snapshot_planejamento(registro, conta, chave)
        if mudou:
            db.session.flush()
        return registro

    return PlanejamentoFinanceiro.query.filter(
        PlanejamentoFinanceiro.origem == "IMPORTADA",
        PlanejamentoFinanceiro.mes == mes,
        PlanejamentoFinanceiro.ano == ano,
        or_(
            PlanejamentoFinanceiro.conta_id == conta_id,
            PlanejamentoFinanceiro.chave_conta == chave,
        ),
    ).first()


def montar_item_planejamento(conta, mes, ano, hoje):
    primeiro_mes = primeiro_dia_mes(mes, ano)
    ultimo_mes = ultimo_dia_mes(mes, ano)
    vencimento = data_para_date_local(getattr(conta, "data_vencimento", None))

    valor = dinheiro_decimal(getattr(conta, "valor", 0))

    conta_nome = buscar_primeiro(
        conta,
        [
            "plano_contas",
            "categoria",
            "descricao",
            "nome",
            "fornecedor_funcionario",
            "fornecedor",
        ],
        "SEM CONTA",
    )

    fornecedor = buscar_primeiro(
        conta,
        ["fornecedor_funcionario", "fornecedor", "cliente"],
        "-",
    )

    categoria = buscar_primeiro(
        conta,
        ["categoria", "plano_contas"],
        "-",
    )

    documento = buscar_primeiro(
        conta,
        ["numero_fatura", "documento", "numero_documento", "nf", "nota_fiscal"],
        "-",
    )

    observacao = buscar_primeiro(
        conta,
        ["observacoes", "observacao", "historico", "descricao"],
        "-",
    )

    parcela_label = buscar_primeiro(
        conta,
        ["parcela_label", "parcela", "numero_parcela"],
        "",
    )

    if parcela_label == "-":
        parcela_label = ""

    status_visual = "SEM DATA"
    is_herdada = False
    is_mes_atual = False
    dias_atraso = 0

    if vencimento:
        is_herdada = vencimento < primeiro_mes
        is_mes_atual = primeiro_mes <= vencimento <= ultimo_mes

        if vencimento < primeiro_mes:
            status_visual = "HERDADA"
        elif vencimento < hoje:
            status_visual = "ATRASADA"
        elif vencimento == hoje:
            status_visual = "VENCE HOJE"
        else:
            status_visual = "MÊS ATUAL"

        if vencimento < hoje:
            dias_atraso = (hoje - vencimento).days

    return {
        "id": int(getattr(conta, "id", 0)),
        "descricao": conta_nome,
        "conta_nome": conta_nome,
        "fornecedor": fornecedor,
        "categoria": categoria,
        "documento": documento,
        "observacao": observacao,
        "parcela_label": parcela_label,
        "vencimento": formatar_data(vencimento),
        "data_vencimento_obj": vencimento,
        "valor": valor,
        "valor_formatado": moeda(valor),
        "is_herdada": is_herdada,
        "is_mes_atual": is_mes_atual,
        "status_planejamento_visual": status_visual,
        "dias_atraso": dias_atraso,
    }


def buscar_contas_do_mes(mes, ano):
    """
    Busca todas as contas em aberto até o fim do mês selecionado.
    Isso inclui herdadas/atrasadas e contas do mês atual.
    Tudo vem em ordem de pagamento: vencimento mais antigo primeiro.
    """
    ultimo_mes = ultimo_dia_mes(mes, ano)

    return ContaPagarImportada.query.filter(
        ContaPagarImportada.origem_importacao == "DESPESA_COMPLETA",
        ContaPagarImportada.pago == False,
        or_(
            ContaPagarImportada.status.is_(None),
            ContaPagarImportada.status != "CANCELADO",
        ),
        ContaPagarImportada.data_vencimento <= fim_dia_datetime(ultimo_mes),
    ).order_by(
        ContaPagarImportada.data_vencimento.asc(),
        ContaPagarImportada.id.asc(),
    ).all()




def buscar_contas_exportacao_e_tela(mes, ano):
    """
    Busca contas até o fim da competência, incluindo pagas.
    Necessário para manter histórico: se uma conta planejada em julho foi paga no Radar,
    ela continua aparecendo/exportando em julho como PAGA.
    """
    ultimo_mes = ultimo_dia_mes(mes, ano)

    return ContaPagarImportada.query.filter(
        ContaPagarImportada.origem_importacao == "DESPESA_COMPLETA",
        or_(
            ContaPagarImportada.status.is_(None),
            ContaPagarImportada.status != "CANCELADO",
        ),
        ContaPagarImportada.data_vencimento <= fim_dia_datetime(ultimo_mes),
    ).order_by(
        ContaPagarImportada.data_vencimento.asc(),
        ContaPagarImportada.id.asc(),
    ).all()


def inicio_dia_datetime_local(data_ref):
    return datetime.combine(data_ref, datetime.min.time())




def valor_receber_decimal(conta):
    """Retorna o valor de contas a receber importadas com segurança."""
    return dinheiro_decimal(
        getattr(conta, "total", None)
        or getattr(conta, "valor", None)
        or getattr(conta, "valor_recebido", None)
        or 0
    )


def calcular_resumo_caixa_competencia(mes, ano):
    """
    Resumo do topo da tela.
    - Recebido: entradas confirmadas no Radar/Importações dentro da competência.
    - Pago: despesas confirmadas no Radar dentro da competência.
    - Saldo da conta: recebido - pago.
    """
    primeiro_mes = primeiro_dia_mes(mes, ano)
    ultimo_mes = ultimo_dia_mes(mes, ano)
    inicio_dt = inicio_dia_datetime_local(primeiro_mes)
    fim_dt = fim_dia_datetime(ultimo_mes)

    contas_recebidas = ContaReceberImportada.query.filter(
        ContaReceberImportada.pago == True,
        ContaReceberImportada.origem_importacao == "RECEBIMENTO",
        ContaReceberImportada.data_pagamento >= inicio_dt,
        ContaReceberImportada.data_pagamento <= fim_dt,
    ).all()

    contas_pagas = ContaPagarImportada.query.filter(
        ContaPagarImportada.pago == True,
        ContaPagarImportada.origem_importacao == "DESPESA_COMPLETA",
        ContaPagarImportada.data_pagamento >= inicio_dt,
        ContaPagarImportada.data_pagamento <= fim_dt,
    ).all()

    total_recebido = sum(valor_receber_decimal(c) for c in contas_recebidas)
    total_pago = sum(dinheiro_decimal(getattr(c, "valor", 0)) for c in contas_pagas)
    saldo_conta = total_recebido - total_pago

    return total_recebido, total_pago, saldo_conta


def conta_paga_na_competencia(conta, mes, ano):
    """
    Define se a conta paga no Radar pertence à competência do planejamento.
    Regra principal: data_pagamento dentro do mês/ano selecionado.
    Fallback: se não tiver data_pagamento, usa vencimento dentro do mês/ano.
    """
    primeiro_mes = primeiro_dia_mes(mes, ano)
    ultimo_mes = ultimo_dia_mes(mes, ano)

    data_pagamento = data_para_date_local(getattr(conta, "data_pagamento", None))
    if data_pagamento:
        return primeiro_mes <= data_pagamento <= ultimo_mes

    vencimento = data_para_date_local(getattr(conta, "data_vencimento", None))
    if vencimento:
        return primeiro_mes <= vencimento <= ultimo_mes

    return False


def buscar_planejamentos(mes, ano, contas=None):
    registros = PlanejamentoFinanceiro.query.filter_by(
        origem="IMPORTADA",
        mes=mes,
        ano=ano,
    ).all()

    por_id = {int(r.conta_id): r for r in registros if r.conta_id is not None}
    por_chave = {r.chave_conta: r for r in registros if getattr(r, "chave_conta", None)}

    # Migra automaticamente os registros antigos ainda ligados ao ID atual.
    alterou = False
    for conta in contas or []:
        conta_id = int(getattr(conta, "id", 0))
        registro = por_id.get(conta_id)
        if registro and not getattr(registro, "chave_conta", None):
            chave = gerar_chave_conta(conta)
            preencher_snapshot_planejamento(registro, conta, chave)
            por_chave[chave] = registro
            alterou = True

    if alterou:
        db.session.commit()

    return por_id, por_chave


def sincronizar_pagas_do_radar(mes, ano):
    """Sincroniza pagas sem perder vínculos quando os IDs da importação mudarem."""
    primeiro_mes = primeiro_dia_mes(mes, ano)
    ultimo_mes = ultimo_dia_mes(mes, ano)
    inicio_dt = inicio_dia_datetime_local(primeiro_mes)
    fim_dt = fim_dia_datetime(ultimo_mes)

    contas = ContaPagarImportada.query.filter(
        ContaPagarImportada.origem_importacao == "DESPESA_COMPLETA",
        or_(
            ContaPagarImportada.data_pagamento >= inicio_dt,
            ContaPagarImportada.data_vencimento >= inicio_dt,
        ),
        or_(
            ContaPagarImportada.data_pagamento <= fim_dt,
            ContaPagarImportada.data_vencimento <= fim_dt,
        ),
    ).all()

    por_id, por_chave = buscar_planejamentos(mes, ano, contas)
    criadas = 0
    atualizadas = 0

    for conta in contas:
        if conta_esta_cancelada(conta) or not conta_esta_paga_local(conta):
            continue
        if not conta_paga_na_competencia(conta, mes, ano):
            continue

        chave = gerar_chave_conta(conta)
        registro = por_id.get(int(conta.id)) or por_chave.get(chave)

        if registro:
            if registro.conta_id != conta.id or registro.chave_conta != chave:
                preencher_snapshot_planejamento(registro, conta, chave)
                atualizadas += 1
            continue

        novo = PlanejamentoFinanceiro(
            conta_id=int(conta.id),
            chave_conta=chave,
            origem="IMPORTADA",
            mes=mes,
            ano=ano,
            status_planejamento="SINCRONIZADA_RADAR",
        )
        preencher_snapshot_planejamento(novo, conta, chave)
        db.session.add(novo)
        por_id[int(conta.id)] = novo
        por_chave[chave] = novo
        criadas += 1

    db.session.commit()
    return criadas, atualizadas


@planejamento_financeiro_bp.route("/")
@gestao_required
def index():
    hoje = date.today()
    agora = datetime.now()

    mes = request.args.get("mes", type=int) or agora.month
    ano = request.args.get("ano", type=int) or agora.year

    if not 1 <= mes <= 12:
        mes = agora.month

    contas = buscar_contas_exportacao_e_tela(mes, ano)
    planejamentos_id, planejamentos_chave = buscar_planejamentos(mes, ano, contas)

    # Planejamentos ativos em outras competências. Eles continuam aparecendo
    # em Aguardando Decisão, porém marcados como indisponíveis na interface.
    outros_planejamentos = PlanejamentoFinanceiro.query.filter(
        PlanejamentoFinanceiro.origem == "IMPORTADA",
        or_(
            PlanejamentoFinanceiro.mes != mes,
            PlanejamentoFinanceiro.ano != ano,
        ),
    ).order_by(
        PlanejamentoFinanceiro.ano.asc(),
        PlanejamentoFinanceiro.mes.asc(),
    ).all()

    outros_por_id = {}
    outros_por_chave = {}

    for planejamento_antigo in outros_planejamentos:
        conta_antiga = None
        if planejamento_antigo.conta_id is not None:
            conta_antiga = ContaPagarImportada.query.get(int(planejamento_antigo.conta_id))

        # Planejamentos de contas já pagas ou canceladas não bloqueiam.
        if conta_antiga and (conta_esta_paga_local(conta_antiga) or conta_esta_cancelada(conta_antiga)):
            continue

        if planejamento_antigo.conta_id is not None:
            outros_por_id.setdefault(int(planejamento_antigo.conta_id), planejamento_antigo)

        if planejamento_antigo.chave_conta:
            outros_por_chave.setdefault(planejamento_antigo.chave_conta, planejamento_antigo)

    aguardando = []
    planejadas = []
    executadas = []

    for conta in contas:
        if conta_esta_cancelada(conta):
            continue

        item = montar_item_planejamento(conta, mes, ano, hoje)
        registro = localizar_planejamento(conta, mes, ano, planejamentos_id, planejamentos_chave)

        if registro:
            pagamentos = pagamentos_do_planejamento(registro)
            if pagamentos:
                for pagamento in pagamentos:
                    item_pagamento = criar_item_pagamento(item, registro, pagamento)
                    if conta_esta_paga_local(conta):
                        item_pagamento["status_execucao"] = "PAGA"
                        item_pagamento["data_pagamento"] = formatar_data(getattr(conta, "data_pagamento", None))
                        executadas.append(item_pagamento)
                    else:
                        item_pagamento["status_execucao"] = "PLANEJADA"
                        item_pagamento["data_pagamento"] = "-"
                        planejadas.append(item_pagamento)

            if not conta_esta_paga_local(conta):
                item_saldo = criar_item_saldo_restante(item, registro)
                if dinheiro_decimal(item_saldo.get("valor")) > 0:
                    aguardando.append(item_saldo)
        elif not conta_esta_paga_local(conta):
            item["status_execucao"] = "AGUARDANDO"
            item["data_pagamento"] = "-"

            chave_atual = gerar_chave_conta(conta)
            planejamento_outro_mes = (
                outros_por_id.get(int(conta.id))
                or outros_por_chave.get(chave_atual)
            )

            if planejamento_outro_mes:
                item["planejada_outro_mes"] = True
                item["competencia_planejada"] = (
                    f"{nome_mes(planejamento_outro_mes.mes).upper()}/"
                    f"{planejamento_outro_mes.ano}"
                )
            else:
                item["planejada_outro_mes"] = False
                item["competencia_planejada"] = ""

            aguardando.append(item)

    planejadas.sort(key=lambda i: (
        data_para_date_local(i.get("data_prevista")) or date.max,
        normalizar_chave(i.get("fornecedor")),
        normalizar_chave(i.get("conta_nome")),
    ))
    executadas.sort(key=lambda i: (
        data_para_date_local(i.get("data_prevista"))
        or data_para_date_local(i.get("data_pagamento"))
        or date.max,
        normalizar_chave(i.get("fornecedor")),
        normalizar_chave(i.get("conta_nome")),
    ))

    total_aguardando = sum(dinheiro_decimal(i.get("valor")) for i in aguardando)
    total_planejado = sum(dinheiro_decimal(i.get("valor_planejado", i.get("valor"))) for i in planejadas)
    total_executado = sum(dinheiro_decimal(i.get("valor")) for i in executadas)
    total_recebido, total_pago_competencia, saldo_competencia = calcular_resumo_caixa_competencia(mes, ano)

    return render_template(
        "gestao/planejamento_financeiro.html",
        mes=mes,
        ano=ano,
        nome_mes=nome_mes,
        moeda=moeda,
        aguardando=aguardando,
        planejadas=planejadas,
        executadas=executadas,
        total_aguardando=total_aguardando,
        total_planejado=total_planejado,
        total_executado=total_executado,
        total_recebido=total_recebido,
        total_pago_competencia=total_pago_competencia,
        saldo_competencia=saldo_competencia,
    )




def montar_listas_planejamento(mes, ano):
    hoje = date.today()
    contas = buscar_contas_exportacao_e_tela(mes, ano)
    planejamentos_id, planejamentos_chave = buscar_planejamentos(mes, ano, contas)

    aguardando = []
    planejadas = []
    pagas = []

    for conta in contas:
        if conta_esta_cancelada(conta):
            continue

        item = montar_item_planejamento(conta, mes, ano, hoje)
        item["data_pagamento"] = formatar_data(getattr(conta, "data_pagamento", None))
        registro = localizar_planejamento(conta, mes, ano, planejamentos_id, planejamentos_chave)

        if registro:
            pagamentos = pagamentos_do_planejamento(registro)
            if pagamentos:
                for pagamento in pagamentos:
                    item_pagamento = criar_item_pagamento(item, registro, pagamento)
                    if conta_esta_paga_local(conta):
                        item_pagamento["status_execucao"] = "PAGA"
                        pagas.append(item_pagamento)
                    else:
                        item_pagamento["status_execucao"] = "PLANEJADA"
                        planejadas.append(item_pagamento)

            if not conta_esta_paga_local(conta):
                item_saldo = criar_item_saldo_restante(item, registro)
                if dinheiro_decimal(item_saldo.get("valor")) > 0:
                    aguardando.append(item_saldo)
        elif not conta_esta_paga_local(conta):
            item["status_execucao"] = "AGUARDANDO"
            aguardando.append(item)

    planejadas.sort(key=lambda i: (
        data_para_date_local(i.get("data_prevista")) or date.max,
        normalizar_chave(i.get("fornecedor")),
        normalizar_chave(i.get("conta_nome")),
    ))
    pagas.sort(key=lambda i: (
        data_para_date_local(i.get("data_prevista"))
        or data_para_date_local(i.get("data_pagamento"))
        or date.max,
        normalizar_chave(i.get("fornecedor")),
        normalizar_chave(i.get("conta_nome")),
    ))

    return aguardando, planejadas, pagas


def valor_decimal_item(item):
    return dinheiro_decimal(item.get("valor_planejado", item.get("valor", 0)))


def pagamentos_do_planejamento(registro):
    """Retorna os pagamentos separados; migra registros antigos de forma transparente."""
    pagamentos = list(getattr(registro, "pagamentos_planejados", []) or [])
    if pagamentos:
        return sorted(
            pagamentos,
            key=lambda p: (data_para_date_local(p.data_prevista) or date.max, p.id or 0),
        )

    valor_legado = dinheiro_decimal(getattr(registro, "valor_planejado", None))
    if valor_legado <= 0:
        return []

    # Objeto leve para compatibilidade com planejamentos criados antes da tabela filha.
    class PagamentoLegado:
        pass

    pagamento = PagamentoLegado()
    pagamento.id = None
    pagamento.tipo = texto_limpo(getattr(registro, "tipo_planejamento", None), "TOTAL").upper()
    pagamento.valor = valor_legado
    pagamento.data_prevista = data_para_date_local(getattr(registro, "data_prevista", None))
    pagamento.observacao = getattr(registro, "observacao_previsao", None)
    return [pagamento]


def total_ja_planejado(registro):
    return sum(dinheiro_decimal(p.valor) for p in pagamentos_do_planejamento(registro))


def criar_item_pagamento(item_base, registro, pagamento):
    item = dict(item_base)
    valor_original = dinheiro_decimal(item_base.get("valor", 0))
    valor_pagamento = dinheiro_decimal(getattr(pagamento, "valor", 0))
    total_planejado = total_ja_planejado(registro)
    saldo_restante = max(Decimal("0"), valor_original - total_planejado)

    item["valor_original"] = valor_original
    item["valor_original_formatado"] = moeda(valor_original)
    item["valor_planejado"] = valor_pagamento
    item["valor_planejado_formatado"] = moeda(valor_pagamento)
    item["saldo_restante"] = saldo_restante
    item["saldo_restante_formatado"] = moeda(saldo_restante)
    item["tipo_planejamento"] = texto_limpo(getattr(pagamento, "tipo", None), "PARCIAL").upper()
    item["data_prevista"] = formatar_data(getattr(pagamento, "data_prevista", None))
    item["observacao_previsao"] = texto_limpo(getattr(pagamento, "observacao", None), "-")
    item["pagamento_planejado_id"] = getattr(pagamento, "id", None)
    return item


def criar_item_saldo_restante(item_base, registro):
    item = dict(item_base)
    valor_original = dinheiro_decimal(item_base.get("valor", 0))
    saldo = max(Decimal("0"), valor_original - total_ja_planejado(registro))
    item["valor"] = saldo
    item["valor_formatado"] = moeda(saldo)
    item["valor_original"] = valor_original
    item["valor_original_formatado"] = moeda(valor_original)
    item["saldo_restante"] = saldo
    item["saldo_restante_formatado"] = moeda(saldo)
    item["is_saldo_restante"] = True
    item["status_planejamento_visual"] = "SALDO RESTANTE"
    item["descricao"] = f"{item_base.get('descricao', 'CONTA')} (SALDO)"
    item["conta_nome"] = item["descricao"]
    item["observacao"] = (
        f"Saldo ainda não planejado. Valor original: {moeda(valor_original)}."
    )
    item["status_execucao"] = "AGUARDANDO"
    item["planejada_outro_mes"] = False
    item["competencia_planejada"] = ""
    return item


def aplicar_dados_previsao_item(item, registro):
    """Acrescenta ao item os dados previstos sem perder o valor original da conta."""
    valor_original = dinheiro_decimal(item.get("valor", 0))
    valor_planejado = dinheiro_decimal(getattr(registro, "valor_planejado", None))
    if valor_planejado <= 0:
        valor_planejado = valor_original

    tipo = texto_limpo(getattr(registro, "tipo_planejamento", None), "TOTAL").upper()
    data_prevista = data_para_date_local(getattr(registro, "data_prevista", None))
    saldo_restante = max(Decimal("0"), valor_original - valor_planejado)

    item["valor_original"] = valor_original
    item["valor_original_formatado"] = moeda(valor_original)
    item["valor_planejado"] = valor_planejado
    item["valor_planejado_formatado"] = moeda(valor_planejado)
    item["saldo_restante"] = saldo_restante
    item["saldo_restante_formatado"] = moeda(saldo_restante)
    item["tipo_planejamento"] = tipo
    item["data_prevista"] = formatar_data(data_prevista)
    item["observacao_previsao"] = texto_limpo(getattr(registro, "observacao_previsao", None), "-")
    return item


def estilos_excel():
    cores = {
        "azul": "0B4EDB",
        "azul_escuro": "061B3D",
        "azul_claro": "EAF2FF",
        "verde": "087539",
        "verde_claro": "EAF8F0",
        "amarelo": "F59E0B",
        "amarelo_claro": "FFF7DD",
        "vermelho": "E11D2E",
        "vermelho_claro": "FFECEE",
        "cinza": "F4F7FB",
        "cinza_texto": "64748B",
        "branco": "FFFFFF",
        "borda": "DCE5F1",
    }
    borda = Border(
        left=Side(style="thin", color=cores["borda"]),
        right=Side(style="thin", color=cores["borda"]),
        top=Side(style="thin", color=cores["borda"]),
        bottom=Side(style="thin", color=cores["borda"]),
    )
    return cores, borda


def preparar_aba(ws, titulo, subtitulo, total_colunas):
    cores, _ = estilos_excel()
    ws.sheet_view.showGridLines = False
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_colunas)
    titulo_cell = ws.cell(1, 1, titulo)
    titulo_cell.font = Font(bold=True, color=cores["branco"], size=16)
    titulo_cell.fill = PatternFill("solid", fgColor=cores["azul_escuro"])
    titulo_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 32

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_colunas)
    sub_cell = ws.cell(2, 1, subtitulo)
    sub_cell.font = Font(bold=True, color=cores["azul_escuro"], size=10)
    sub_cell.fill = PatternFill("solid", fgColor=cores["cinza"])
    sub_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 23


def escrever_cabecalho(ws, linha, colunas):
    cores, borda = estilos_excel()
    for indice, cabecalho in enumerate(colunas, start=1):
        cell = ws.cell(linha, indice, cabecalho)
        cell.font = Font(bold=True, color=cores["branco"], size=10)
        cell.fill = PatternFill("solid", fgColor=cores["azul"])
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = borda
    ws.row_dimensions[linha].height = 28


def estilizar_status(cell, status):
    cores, _ = estilos_excel()
    status = texto_limpo(status, "-").upper()
    if status == "PAGA":
        cell.fill = PatternFill("solid", fgColor=cores["verde_claro"])
        cell.font = Font(bold=True, color=cores["verde"])
    elif status == "PLANEJADA":
        cell.fill = PatternFill("solid", fgColor=cores["azul_claro"])
        cell.font = Font(bold=True, color=cores["azul"])
    elif status == "PARCIAL":
        cell.fill = PatternFill("solid", fgColor=cores["amarelo_claro"])
        cell.font = Font(bold=True, color="A65B00")
    else:
        cell.fill = PatternFill("solid", fgColor=cores["vermelho_claro"])
        cell.font = Font(bold=True, color=cores["vermelho"])


def valor_original_item(item):
    return dinheiro_decimal(item.get("valor_original", item.get("valor", 0)))


def valor_planejado_item(item):
    if item.get("status_execucao") == "AGUARDANDO":
        return Decimal("0")
    return dinheiro_decimal(item.get("valor_planejado", item.get("valor", 0)))


def saldo_item(item):
    if item.get("status_execucao") == "AGUARDANDO":
        return valor_original_item(item)
    return dinheiro_decimal(item.get("saldo_restante", 0))


def data_agenda_item(item):
    return (
        data_para_date_local(item.get("data_prevista"))
        or data_para_date_local(item.get("data_pagamento"))
        or data_para_date_local(item.get("vencimento"))
    )


def escrever_aba_agenda(wb, competencia, planejadas, pagas):
    ws = wb.create_sheet("Agenda de Pagamentos")
    itens = list(planejadas) + list(pagas)
    itens.sort(key=lambda i: (
        data_agenda_item(i) or date.max,
        normalizar_chave(i.get("fornecedor")),
        normalizar_chave(i.get("conta_nome")),
    ))
    total = sum(valor_planejado_item(i) for i in itens)
    preparar_aba(
        ws,
        f"AGENDA DE PAGAMENTOS - {competencia.upper()}",
        f"Exportado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | "
        f"{len(itens)} conta(s) | Total previsto: {moeda(total)}",
        11,
    )
    colunas = [
        "Data prevista", "Status", "Conta", "Fornecedor", "Parcela",
        "Tipo", "Valor original", "Valor planejado", "Saldo restante",
        "Pago em", "Observação",
    ]
    escrever_cabecalho(ws, 4, colunas)
    _, borda = estilos_excel()
    linha = 5
    for item in itens:
        data_prevista = data_agenda_item(item)
        valores = [
            data_prevista,
            item.get("status_execucao", "-"),
            item.get("conta_nome", "-"),
            item.get("fornecedor", "-"),
            item.get("parcela_label", "-"),
            item.get("tipo_planejamento", "TOTAL"),
            float(valor_original_item(item)),
            float(valor_planejado_item(item)),
            float(saldo_item(item)),
            data_para_date_local(item.get("data_pagamento")),
            item.get("observacao_previsao") or item.get("observacao", "-"),
        ]
        for coluna, valor in enumerate(valores, start=1):
            cell = ws.cell(linha, coluna, valor)
            cell.border = borda
            cell.alignment = Alignment(vertical="center", wrap_text=coluna in (3, 4, 11))
            if coluna in (1, 10) and valor:
                cell.number_format = "dd/mm/yyyy"
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif coluna in (7, 8, 9):
                cell.number_format = 'R$ #,##0.00'
                cell.alignment = Alignment(horizontal="right", vertical="center")
        estilizar_status(ws.cell(linha, 2), item.get("status_execucao"))
        if texto_limpo(item.get("tipo_planejamento"), "TOTAL").upper() == "PARCIAL":
            estilizar_status(ws.cell(linha, 6), "PARCIAL")
        linha += 1

    if itens:
        ws.auto_filter.ref = f"A4:K{linha - 1}"
    ws.freeze_panes = "A5"
    larguras = [15, 14, 34, 30, 12, 12, 17, 18, 18, 14, 42]
    for idx, largura in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = largura
    return ws


def escrever_aba_resumo_diario(wb, competencia, planejadas, pagas):
    ws = wb.create_sheet("Resumo Diário")
    itens = list(planejadas) + list(pagas)
    resumo = {}
    for item in itens:
        dia = data_agenda_item(item)
        if not dia:
            continue
        dados = resumo.setdefault(dia, {"quantidade": 0, "planejado": Decimal("0"), "pago": Decimal("0")})
        dados["quantidade"] += 1
        dados["planejado"] += valor_planejado_item(item)
        if item.get("status_execucao") == "PAGA":
            dados["pago"] += dinheiro_decimal(item.get("valor", 0))

    preparar_aba(
        ws,
        f"RESUMO DIÁRIO - {competencia.upper()}",
        "Consolidação do desembolso por data prevista.",
        5,
    )
    escrever_cabecalho(ws, 4, ["Data", "Quantidade", "Valor planejado", "Valor pago", "Falta executar"])
    _, borda = estilos_excel()
    linha = 5
    for dia in sorted(resumo):
        dados = resumo[dia]
        falta = max(Decimal("0"), dados["planejado"] - dados["pago"])
        valores = [dia, dados["quantidade"], float(dados["planejado"]), float(dados["pago"]), float(falta)]
        for coluna, valor in enumerate(valores, start=1):
            cell = ws.cell(linha, coluna, valor)
            cell.border = borda
            cell.alignment = Alignment(horizontal="center" if coluna <= 2 else "right", vertical="center")
            if coluna == 1:
                cell.number_format = "dd/mm/yyyy"
            elif coluna >= 3:
                cell.number_format = 'R$ #,##0.00'
        linha += 1
    if resumo:
        ws.auto_filter.ref = f"A4:E{linha - 1}"
    ws.freeze_panes = "A5"
    for idx, largura in enumerate([15, 14, 20, 18, 18], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = largura
    return ws


def escrever_aba_parciais(wb, competencia, planejadas, pagas):
    ws = wb.create_sheet("Pagamentos Parciais")
    itens = [
        i for i in list(planejadas) + list(pagas)
        if texto_limpo(i.get("tipo_planejamento"), "TOTAL").upper() == "PARCIAL"
    ]
    itens.sort(key=lambda i: (data_agenda_item(i) or date.max, normalizar_chave(i.get("conta_nome"))))
    preparar_aba(
        ws,
        f"PAGAMENTOS PARCIAIS - {competencia.upper()}",
        f"{len(itens)} conta(s) com pagamento parcial | Saldo total: {moeda(sum(saldo_item(i) for i in itens))}",
        9,
    )
    escrever_cabecalho(ws, 4, [
        "Data prevista", "Status", "Conta", "Fornecedor", "Valor original",
        "Valor planejado", "Saldo restante", "% planejado", "Observação",
    ])
    _, borda = estilos_excel()
    linha = 5
    for item in itens:
        original = valor_original_item(item)
        planejado = valor_planejado_item(item)
        percentual = float(planejado / original) if original > 0 else 0
        valores = [
            data_agenda_item(item), item.get("status_execucao", "-"),
            item.get("conta_nome", "-"), item.get("fornecedor", "-"),
            float(original), float(planejado), float(saldo_item(item)), percentual,
            item.get("observacao_previsao") or item.get("observacao", "-"),
        ]
        for coluna, valor in enumerate(valores, start=1):
            cell = ws.cell(linha, coluna, valor)
            cell.border = borda
            cell.alignment = Alignment(vertical="center", wrap_text=coluna in (3, 4, 9))
            if coluna == 1 and valor:
                cell.number_format = "dd/mm/yyyy"
            elif coluna in (5, 6, 7):
                cell.number_format = 'R$ #,##0.00'
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif coluna == 8:
                cell.number_format = "0.00%"
                cell.alignment = Alignment(horizontal="center", vertical="center")
        estilizar_status(ws.cell(linha, 2), item.get("status_execucao"))
        linha += 1
    if itens:
        ws.auto_filter.ref = f"A4:I{linha - 1}"
    ws.freeze_panes = "A5"
    for idx, largura in enumerate([15, 14, 34, 30, 18, 18, 18, 15, 42], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = largura
    return ws


def escrever_aba_geral(wb, competencia, aguardando, planejadas, pagas):
    ws = wb.create_sheet("Planejamento Geral")
    itens = list(aguardando) + list(planejadas) + list(pagas)
    itens.sort(key=lambda i: (
        0 if i.get("status_execucao") == "PLANEJADA" else 1 if i.get("status_execucao") == "PAGA" else 2,
        data_agenda_item(i) or date.max,
        normalizar_chave(i.get("conta_nome")),
    ))
    preparar_aba(
        ws,
        f"PLANEJAMENTO GERAL - {competencia.upper()}",
        f"{len(itens)} conta(s) entre aguardando, planejadas e pagas.",
        13,
    )
    escrever_cabecalho(ws, 4, [
        "Status", "Vencimento", "Data prevista", "Pago em", "Conta", "Fornecedor",
        "Parcela", "Tipo", "Valor original", "Valor planejado", "Saldo restante",
        "Observação da conta", "Observação do planejamento",
    ])
    _, borda = estilos_excel()
    linha = 5
    for item in itens:
        valores = [
            item.get("status_execucao", "-"),
            data_para_date_local(item.get("vencimento")),
            data_para_date_local(item.get("data_prevista")),
            data_para_date_local(item.get("data_pagamento")),
            item.get("conta_nome", "-"), item.get("fornecedor", "-"),
            item.get("parcela_label", "-"), item.get("tipo_planejamento", "-"),
            float(valor_original_item(item)), float(valor_planejado_item(item)),
            float(saldo_item(item)), item.get("observacao", "-"),
            item.get("observacao_previsao", "-"),
        ]
        for coluna, valor in enumerate(valores, start=1):
            cell = ws.cell(linha, coluna, valor)
            cell.border = borda
            cell.alignment = Alignment(vertical="center", wrap_text=coluna in (5, 6, 12, 13))
            if coluna in (2, 3, 4) and valor:
                cell.number_format = "dd/mm/yyyy"
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif coluna in (9, 10, 11):
                cell.number_format = 'R$ #,##0.00'
                cell.alignment = Alignment(horizontal="right", vertical="center")
        estilizar_status(ws.cell(linha, 1), item.get("status_execucao"))
        linha += 1
    if itens:
        ws.auto_filter.ref = f"A4:M{linha - 1}"
    ws.freeze_panes = "A5"
    larguras = [14, 14, 15, 14, 34, 30, 12, 12, 18, 18, 18, 38, 40]
    for idx, largura in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = largura
    return ws


def escrever_aba_executivo(wb, competencia, aguardando, planejadas, pagas, mes, ano):
    ws = wb.create_sheet("Resumo Executivo")
    preparar_aba(
        ws,
        f"RESUMO EXECUTIVO - {competencia.upper()}",
        f"Posição gerencial exportada em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
        6,
    )
    cores, borda = estilos_excel()
    total_recebido, total_pago_caixa, saldo_caixa = calcular_resumo_caixa_competencia(mes, ano)
    total_aguardando = sum(valor_original_item(i) for i in aguardando)
    total_planejado = sum(valor_planejado_item(i) for i in planejadas)
    total_executado = sum(dinheiro_decimal(i.get("valor", 0)) for i in pagas)
    saldo_parcial = sum(saldo_item(i) for i in list(planejadas) + list(pagas))
    quantidade_parciais = sum(
        1 for i in list(planejadas) + list(pagas)
        if texto_limpo(i.get("tipo_planejamento"), "TOTAL").upper() == "PARCIAL"
    )
    quantidade_integrais = len(planejadas) + len(pagas) - quantidade_parciais

    indicadores = [
        ("Recebido na competência", total_recebido, "moeda", cores["azul_claro"]),
        ("Pago na competência", total_pago_caixa, "moeda", cores["verde_claro"]),
        ("Saldo da conta", saldo_caixa, "moeda", cores["amarelo_claro"]),
        ("Valor aguardando decisão", total_aguardando, "moeda", cores["vermelho_claro"]),
        ("Valor planejado", total_planejado, "moeda", cores["azul_claro"]),
        ("Valor executado", total_executado, "moeda", cores["verde_claro"]),
        ("Saldo de pagamentos parciais", saldo_parcial, "moeda", cores["amarelo_claro"]),
        ("Contas aguardando", len(aguardando), "numero", cores["cinza"]),
        ("Contas planejadas", len(planejadas), "numero", cores["azul_claro"]),
        ("Contas pagas", len(pagas), "numero", cores["verde_claro"]),
        ("Planejamentos parciais", quantidade_parciais, "numero", cores["amarelo_claro"]),
        ("Planejamentos integrais", quantidade_integrais, "numero", cores["cinza"]),
    ]

    linha = 4
    for indice, (rotulo, valor, tipo, fundo) in enumerate(indicadores):
        coluna_base = 1 if indice % 2 == 0 else 4
        if indice % 2 == 0 and indice > 0:
            linha += 3
        ws.merge_cells(start_row=linha, start_column=coluna_base, end_row=linha, end_column=coluna_base + 2)
        rotulo_cell = ws.cell(linha, coluna_base, rotulo)
        rotulo_cell.font = Font(bold=True, color=cores["cinza_texto"], size=10)
        rotulo_cell.fill = PatternFill("solid", fgColor=fundo)
        rotulo_cell.border = borda
        rotulo_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.merge_cells(start_row=linha + 1, start_column=coluna_base, end_row=linha + 1, end_column=coluna_base + 2)
        valor_cell = ws.cell(linha + 1, coluna_base, float(valor) if tipo == "moeda" else int(valor))
        valor_cell.font = Font(bold=True, color=cores["azul_escuro"], size=15)
        valor_cell.fill = PatternFill("solid", fgColor=fundo)
        valor_cell.border = borda
        valor_cell.alignment = Alignment(horizontal="center", vertical="center")
        if tipo == "moeda":
            valor_cell.number_format = 'R$ #,##0.00'
        ws.row_dimensions[linha].height = 22
        ws.row_dimensions[linha + 1].height = 30

    for coluna in range(1, 7):
        ws.column_dimensions[get_column_letter(coluna)].width = 18
    return ws


@planejamento_financeiro_bp.route("/sincronizar-radar", methods=["POST"])
@gestao_required
def sincronizar_radar():
    agora = datetime.now()
    mes = request.form.get("mes", type=int) or agora.month
    ano = request.form.get("ano", type=int) or agora.year

    if not 1 <= mes <= 12:
        mes = agora.month

    try:
        criadas, atualizadas = sincronizar_pagas_do_radar(mes, ano)
        return jsonify({
            "ok": True,
            "message": f"Sincronização concluída. {criadas} conta(s) adicionada(s) e {atualizadas} vínculo(s) recuperado(s).",
            "criadas": criadas,
            "atualizadas": atualizadas,
        })
    except Exception as erro:
        db.session.rollback()
        return jsonify({
            "ok": False,
            "message": f"Erro ao sincronizar Radar: {str(erro)}",
        }), 500


@planejamento_financeiro_bp.route("/exportar")
@gestao_required
def exportar_planejamento():
    agora = datetime.now()
    mes = request.args.get("mes", type=int) or agora.month
    ano = request.args.get("ano", type=int) or agora.year

    if not 1 <= mes <= 12:
        mes = agora.month

    aguardando, planejadas, pagas = montar_listas_planejamento(mes, ano)
    competencia = f"{nome_mes(mes)}/{ano}"

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    escrever_aba_agenda(wb, competencia, planejadas, pagas)
    escrever_aba_resumo_diario(wb, competencia, planejadas, pagas)
    escrever_aba_parciais(wb, competencia, planejadas, pagas)
    escrever_aba_geral(wb, competencia, aguardando, planejadas, pagas)
    escrever_aba_executivo(wb, competencia, aguardando, planejadas, pagas, mes, ano)

    wb.active = 0
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    nome_arquivo = f"planejamento_financeiro_{nome_mes(mes).lower()}_{ano}.xlsx".replace(" ", "_")
    return send_file(
        output,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@planejamento_financeiro_bp.route("/planejar/<int:conta_id>", methods=["POST"])
@gestao_required
def planejar(conta_id):
    mes = request.form.get("mes", type=int)
    ano = request.form.get("ano", type=int)

    if not mes or not ano:
        return jsonify({"ok": False, "message": "Mês e ano inválidos."}), 400

    conta = ContaPagarImportada.query.get(conta_id)
    if not conta:
        return jsonify({"ok": False, "message": "Conta não encontrada. Sincronize a importação e tente novamente."}), 404

    chave = gerar_chave_conta(conta)

    tipo_planejamento = texto_limpo(request.form.get("tipo_planejamento"), "TOTAL").upper()
    if tipo_planejamento not in ("TOTAL", "PARCIAL"):
        return jsonify({"ok": False, "message": "Tipo de planejamento inválido."}), 400

    valor_original = dinheiro_decimal(getattr(conta, "valor", 0))
    data_prevista = data_para_date_local(request.form.get("data_prevista"))
    observacao_previsao = texto_limpo(request.form.get("observacao_previsao"), "")

    if tipo_planejamento == "PARCIAL":
        valor_planejado = dinheiro_decimal(request.form.get("valor_planejado"))
        if valor_planejado <= 0:
            return jsonify({"ok": False, "message": "Informe um valor previsto maior que zero."}), 400
        if valor_planejado > valor_original:
            return jsonify({"ok": False, "message": "O valor previsto não pode ultrapassar o valor total da conta."}), 400
        if not data_prevista:
            return jsonify({"ok": False, "message": "Informe a data prevista para o pagamento."}), 400
    else:
        valor_planejado = valor_original
        if not data_prevista:
            data_prevista = data_para_date_local(getattr(conta, "data_vencimento", None))

    # Bloqueia a mesma conta/parcela enquanto existir planejamento ativo
    # em outra competência.
    #
    # A verificação usa conta_id OU chave_conta:
    # - conta_id cobre a mesma linha ainda existente na importação;
    # - chave_conta cobre reimportações em que o ID foi recriado.
    #
    # Não limitamos apenas ao status "PLANEJADA", pois registros antigos
    # podem ter status vazio ou outro texto. O que define se ainda está
    # ativo é a conta vinculada continuar em aberto.
    planejamentos_outros_meses = PlanejamentoFinanceiro.query.filter(
        PlanejamentoFinanceiro.origem == "IMPORTADA",
        or_(
            PlanejamentoFinanceiro.conta_id == conta_id,
            PlanejamentoFinanceiro.chave_conta == chave,
        ),
        or_(
            PlanejamentoFinanceiro.mes != mes,
            PlanejamentoFinanceiro.ano != ano,
        ),
    ).order_by(
        PlanejamentoFinanceiro.ano.asc(),
        PlanejamentoFinanceiro.mes.asc(),
    ).all()

    planejamento_ativo = None

    for planejamento_anterior in planejamentos_outros_meses:
        conta_vinculada = None

        if planejamento_anterior.conta_id is not None:
            conta_vinculada = ContaPagarImportada.query.get(
                int(planejamento_anterior.conta_id)
            )

        # Se a conta vinculada existe e já foi paga ou cancelada,
        # o planejamento antigo não deve bloquear uma nova competência.
        if conta_vinculada:
            if conta_esta_paga_local(conta_vinculada):
                continue
            if conta_esta_cancelada(conta_vinculada):
                continue

        # Se o vínculo antigo não existe mais, mas o planejamento permanece
        # no banco, ele continua sendo considerado ativo até ser removido.
        planejamento_ativo = planejamento_anterior
        break

    if planejamento_ativo:
        competencia_existente = (
            f"{nome_mes(planejamento_ativo.mes)}/"
            f"{planejamento_ativo.ano}"
        )

        return jsonify({
            "ok": False,
            "message": (
                "Esta mesma conta/parcela já está planejada em "
                f"{competencia_existente} e ainda está em aberto. "
                "Remova o planejamento anterior ou registre o pagamento."
            ),
            "competencia": competencia_existente,
        }), 409

    existe = PlanejamentoFinanceiro.query.filter(
        PlanejamentoFinanceiro.origem == "IMPORTADA",
        PlanejamentoFinanceiro.mes == mes,
        PlanejamentoFinanceiro.ano == ano,
        or_(
            PlanejamentoFinanceiro.conta_id == conta_id,
            PlanejamentoFinanceiro.chave_conta == chave,
        ),
    ).first()

    registro_novo = existe is None
    if existe:
        preencher_snapshot_planejamento(existe, conta, chave)
        existe.status_planejamento = "PLANEJADA"
    else:
        existe = PlanejamentoFinanceiro(
            conta_id=conta_id,
            chave_conta=chave,
            origem="IMPORTADA",
            mes=mes,
            ano=ano,
            status_planejamento="PLANEJADA",
        )
        preencher_snapshot_planejamento(existe, conta, chave)
        db.session.add(existe)
        db.session.flush()

    # Migra automaticamente um planejamento antigo para a nova tabela de pagamentos.
    pagamentos_existentes = list(getattr(existe, "pagamentos_planejados", []) or [])
    if not registro_novo and not pagamentos_existentes:
        valor_legado = dinheiro_decimal(getattr(existe, "valor_planejado", None))
        if valor_legado > 0:
            pagamento_legado = PlanejamentoPagamento(
                planejamento_id=existe.id,
                tipo=texto_limpo(getattr(existe, "tipo_planejamento", None), "TOTAL").upper(),
                valor=valor_legado,
                data_prevista=data_para_date_local(getattr(existe, "data_prevista", None)),
                observacao=getattr(existe, "observacao_previsao", None),
            )
            db.session.add(pagamento_legado)
            db.session.flush()
            pagamentos_existentes.append(pagamento_legado)

    total_anterior = sum(dinheiro_decimal(p.valor) for p in pagamentos_existentes)
    saldo_disponivel = max(Decimal("0"), valor_original - total_anterior)

    if saldo_disponivel <= 0:
        return jsonify({
            "ok": False,
            "message": "Esta conta já está totalmente planejada.",
        }), 409

    if tipo_planejamento == "TOTAL":
        # Quando a linha representa um saldo, planeja somente o saldo restante.
        valor_planejado = saldo_disponivel
    elif valor_planejado > saldo_disponivel:
        return jsonify({
            "ok": False,
            "message": f"O valor previsto não pode ultrapassar o saldo restante de {moeda(saldo_disponivel)}.",
        }), 400

    pagamento = PlanejamentoPagamento(
        planejamento_id=existe.id,
        tipo=tipo_planejamento,
        valor=valor_planejado,
        data_prevista=data_prevista,
        observacao=observacao_previsao or None,
    )
    db.session.add(pagamento)

    total_atualizado = total_anterior + valor_planejado
    existe.valor_planejado = total_atualizado
    existe.tipo_planejamento = "TOTAL" if total_atualizado >= valor_original else "PARCIAL"
    existe.data_prevista = data_prevista
    existe.observacao_previsao = observacao_previsao or None

    db.session.commit()
    saldo_final = max(Decimal("0"), valor_original - total_atualizado)
    if saldo_final > 0:
        mensagem = (
            f"Valor parcial previsto. O saldo de {moeda(saldo_final)} voltou para Aguardando Decisão."
        )
    else:
        mensagem = "Conta totalmente planejada."

    return jsonify({
        "ok": True,
        "message": mensagem,
        "saldo_restante": float(saldo_final),
        "saldo_restante_formatado": moeda(saldo_final),
    })


@planejamento_financeiro_bp.route("/remover/<int:conta_id>", methods=["POST"])
@gestao_required
def remover(conta_id):
    mes = request.form.get("mes", type=int)
    ano = request.form.get("ano", type=int)

    if not mes or not ano:
        return jsonify({"ok": False, "message": "Mês e ano inválidos."}), 400

    conta = ContaPagarImportada.query.get(conta_id)
    chave = gerar_chave_conta(conta) if conta else None

    filtros = [
        PlanejamentoFinanceiro.origem == "IMPORTADA",
        PlanejamentoFinanceiro.mes == mes,
        PlanejamentoFinanceiro.ano == ano,
    ]

    if chave:
        filtros.append(or_(
            PlanejamentoFinanceiro.conta_id == conta_id,
            PlanejamentoFinanceiro.chave_conta == chave,
        ))
    else:
        filtros.append(PlanejamentoFinanceiro.conta_id == conta_id)

    registro = PlanejamentoFinanceiro.query.filter(*filtros).first()

    if registro:
        db.session.delete(registro)
        db.session.commit()

    return jsonify({"ok": True, "message": "Conta removida do planejamento."})