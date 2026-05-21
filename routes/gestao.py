from flask import Blueprint, render_template, request, redirect, flash, jsonify
from utils.auth import gestao_required
from models.lancamento_financeiro import LancamentoFinanceiro
from models.fechamento_mensal import FechamentoMensal
from models.conta_pagar_importada import ContaPagarImportada
from models.conta_receber_importada import ContaReceberImportada
from database import db
from datetime import datetime, date, timedelta
from collections import Counter
from sqlalchemy import or_, and_
import calendar


gestao_bp = Blueprint("gestao", __name__, url_prefix="/gestao")


# =========================================================
# HELPERS GERAIS
# =========================================================

def dinheiro(valor):
    try:
        return float(valor or 0)
    except Exception:
        return 0


def normalizar_texto(valor):
    if not valor:
        return None

    return str(valor).strip().upper()


def parse_data(data_str):
    if not data_str:
        return None

    return datetime.strptime(data_str, "%Y-%m-%d").date()


def mes_ano_anterior(mes, ano):
    if mes == 1:
        return 12, ano - 1

    return mes - 1, ano


def obter_fechamento_anterior(mes, ano):
    mes_ant, ano_ant = mes_ano_anterior(mes, ano)

    return FechamentoMensal.query.filter_by(
        mes=mes_ant,
        ano=ano_ant
    ).first()


def obter_saldo_inicial_automatico(mes, ano):
    fechamento_anterior = obter_fechamento_anterior(mes, ano)

    if fechamento_anterior:
        return dinheiro(fechamento_anterior.saldo_final)

    return 0


def obter_saldo_inicial_mes(mes, ano):
    fechamento_atual = FechamentoMensal.query.filter_by(
        mes=mes,
        ano=ano
    ).first()

    if fechamento_atual:
        return dinheiro(fechamento_atual.saldo_inicial)

    return obter_saldo_inicial_automatico(mes, ano)


def status_pago(valor):
    status = normalizar_texto(valor)

    return status in [
        "PAGO",
        "RECEBIDO",
        "OK",
        "QUITADO",
        "BAIXADO"
    ]


def status_cancelado(valor):
    status = normalizar_texto(valor)

    return status in [
        "CANCELADO",
        "CANCELADA"
    ]


def calcular_variacao_percentual(valor_atual, valor_anterior):
    valor_atual = dinheiro(valor_atual)
    valor_anterior = dinheiro(valor_anterior)

    if valor_anterior == 0:
        if valor_atual == 0:
            return 0

        return None

    return ((valor_atual - valor_anterior) / abs(valor_anterior)) * 100


def primeiro_dia_mes(mes, ano):
    return date(ano, mes, 1)


def ultimo_dia_mes(mes, ano):
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, ultimo_dia)


def inicio_mes_datetime(mes, ano):
    return datetime.combine(primeiro_dia_mes(mes, ano), datetime.min.time())


def fim_mes_datetime(mes, ano):
    return datetime.combine(ultimo_dia_mes(mes, ano), datetime.max.time())


def data_para_date(valor):
    if not valor:
        return None

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, date):
        return valor

    return None


def nome_dia_semana(data_ref):
    dias = {
        0: "segunda-feira",
        1: "terça-feira",
        2: "quarta-feira",
        3: "quinta-feira",
        4: "sexta-feira",
        5: "sábado",
        6: "domingo",
    }

    return dias.get(data_ref.weekday(), "")


def conta_esta_paga(conta):
    if getattr(conta, "pago", False):
        return True

    status = normalizar_texto(getattr(conta, "status", None))

    return status in [
        "PAGO",
        "RECEBIDO",
        "OK",
        "QUITADO",
        "BAIXADO"
    ]


def valor_conta_receber(conta):
    return dinheiro(
        getattr(conta, "total", None)
        or getattr(conta, "valor", 0)
    )


def data_movimento_fluxo(conta):
    """
    Fluxo é caixa realizado.
    Portanto a data correta é data_pagamento.
    Se não tiver data_pagamento, não entra no fluxo.
    """

    return data_para_date(getattr(conta, "data_pagamento", None))


# =========================================================
# CÁLCULO FINANCEIRO
# IMPORTADAS + LANÇAMENTOS MANUAIS
# =========================================================

def calcular_totais_financeiros(mes, ano, saldo_inicial=0):

    inicio_dt = inicio_mes_datetime(mes, ano)
    fim_dt = fim_mes_datetime(mes, ano)
    fim_dia = ultimo_dia_mes(mes, ano)

    total_entradas = 0
    total_saidas = 0
    total_a_pagar = 0
    total_a_receber = 0

    despesas_counter = Counter()
    despesas_assistencia_counter = Counter()
    despesas_logistica_counter = Counter()

    receitas_counter = Counter()
    clientes_counter = Counter()

    # =====================================================
    # SAÍDAS REALIZADAS
    # Contas pagas pela DATA DE PAGAMENTO dentro do mês
    # =====================================================
    contas_pagar_pagas = ContaPagarImportada.query.filter(
        ContaPagarImportada.pago == True,
        ContaPagarImportada.data_pagamento >= inicio_dt,
        ContaPagarImportada.data_pagamento <= fim_dt
    ).all()

    for c in contas_pagar_pagas:
        valor = dinheiro(c.valor)
        total_saidas += valor

        categoria = c.categoria or c.plano_contas or "SEM CATEGORIA"
        setor = c.setor or "ASSISTÊNCIA"

        despesas_counter[categoria] += valor

        if setor == "LOGÍSTICA":
            despesas_logistica_counter[categoria] += valor
        else:
            despesas_assistencia_counter[categoria] += valor

    # =====================================================
    # A PAGAR
    # Contas abertas com vencimento até o fim do mês filtrado
    # Inclui atrasadas de meses anteriores
    # =====================================================
    contas_pagar_abertas = ContaPagarImportada.query.filter(
        ContaPagarImportada.pago == False,
        ContaPagarImportada.data_vencimento <= fim_dt
    ).all()

    for c in contas_pagar_abertas:
        valor = dinheiro(c.valor)
        total_a_pagar += valor

    # =====================================================
    # ENTRADAS REALIZADAS
    # Contas recebidas pela DATA DE PAGAMENTO dentro do mês
    # =====================================================
    contas_receber_recebidas = ContaReceberImportada.query.filter(
        ContaReceberImportada.pago == True,
        ContaReceberImportada.data_pagamento >= inicio_dt,
        ContaReceberImportada.data_pagamento <= fim_dt
    ).all()

    for c in contas_receber_recebidas:
        valor = valor_conta_receber(c)
        total_entradas += valor

        categoria = c.categoria or c.plano_contas or "SEM CATEGORIA"
        cliente = c.cliente or "SEM CLIENTE"

        receitas_counter[categoria] += valor
        clientes_counter[cliente] += valor

    # =====================================================
    # A RECEBER
    # Contas abertas com vencimento até o fim do mês filtrado
    # Inclui atrasadas de meses anteriores
    # =====================================================
    contas_receber_abertas = ContaReceberImportada.query.filter(
        ContaReceberImportada.pago == False,
        ContaReceberImportada.data_vencimento <= fim_dt
    ).all()

    for c in contas_receber_abertas:
        valor = valor_conta_receber(c)
        total_a_receber += valor

    # =====================================================
    # LANÇAMENTOS MANUAIS
    # Mantém por mes/ano porque o lançamento manual já grava
    # o mês com base na data informada no cadastro
    # =====================================================
    lancamentos = LancamentoFinanceiro.query.filter_by(
        mes=mes,
        ano=ano
    ).all()

    for l in lancamentos:

        if status_cancelado(l.status):
            continue

        valor = dinheiro(l.valor)
        tipo = normalizar_texto(l.tipo)
        categoria = l.categoria or "SEM CATEGORIA"
        setor = l.setor or "GERAL"
        cliente = l.cliente or "SEM CLIENTE"

        if tipo == "RECEITA":

            if status_pago(l.status):
                total_entradas += valor

                receitas_counter[categoria] += valor
                clientes_counter[cliente] += valor
            else:
                total_a_receber += valor

        elif tipo == "DESPESA":

            if status_pago(l.status):
                total_saidas += valor

                despesas_counter[categoria] += valor

                if setor == "LOGÍSTICA":
                    despesas_logistica_counter[categoria] += valor
                else:
                    despesas_assistencia_counter[categoria] += valor
            else:
                total_a_pagar += valor

    lucro_mes = total_entradas - total_saidas
    saldo_final = dinheiro(saldo_inicial) + total_entradas - total_saidas

    margem_operacional = 0

    if total_entradas > 0:
        margem_operacional = (lucro_mes / total_entradas) * 100

    return {
        "total_entradas": total_entradas,
        "total_saidas": total_saidas,
        "total_a_pagar": total_a_pagar,
        "total_a_receber": total_a_receber,
        "lucro_mes": lucro_mes,
        "saldo_final": saldo_final,
        "margem_operacional": margem_operacional,

        "ranking_despesas": despesas_counter.most_common(),
        "ranking_despesas_assistencia": despesas_assistencia_counter.most_common(),
        "ranking_despesas_logistica": despesas_logistica_counter.most_common(),
        "ranking_receitas": receitas_counter.most_common(),
        "ranking_clientes": clientes_counter.most_common(),
    }


# =========================================================
# EVOLUÇÃO FINANCEIRA MENSAL
# =========================================================

def calcular_evolucao_mensal(ano):
    labels = []
    entradas = []
    saidas = []
    lucros = []
    saldos_finais = []
    margens = []
    tabela = []

    nomes_meses = [
        "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez"
    ]

    for mes in range(1, 13):
        saldo_inicial = obter_saldo_inicial_mes(mes, ano)

        totais = calcular_totais_financeiros(
            mes=mes,
            ano=ano,
            saldo_inicial=saldo_inicial
        )

        total_entradas = dinheiro(totais["total_entradas"])
        total_saidas = dinheiro(totais["total_saidas"])
        lucro_mes = dinheiro(totais["lucro_mes"])
        saldo_final = dinheiro(totais["saldo_final"])
        margem_operacional = dinheiro(totais["margem_operacional"])

        labels.append(nomes_meses[mes - 1])
        entradas.append(round(total_entradas, 2))
        saidas.append(round(total_saidas, 2))
        lucros.append(round(lucro_mes, 2))
        saldos_finais.append(round(saldo_final, 2))
        margens.append(round(margem_operacional, 2))

        tabela.append({
            "mes": mes,
            "nome_mes": nomes_meses[mes - 1],
            "ano": ano,
            "saldo_inicial": round(dinheiro(saldo_inicial), 2),
            "entradas": round(total_entradas, 2),
            "saidas": round(total_saidas, 2),
            "lucro": round(lucro_mes, 2),
            "saldo_final": round(saldo_final, 2),
            "margem": round(margem_operacional, 2),
        })

    return {
        "labels": labels,
        "entradas": entradas,
        "saidas": saidas,
        "lucros": lucros,
        "saldos_finais": saldos_finais,
        "margens": margens,
        "tabela": tabela,
    }


# =========================================================
# INTELIGÊNCIA FINANCEIRA / TOMADA DE DECISÃO
# =========================================================

def calcular_inteligencia_financeira(totais, evolucao_mensal, mes, ano, saldo_inicial):
    total_entradas = dinheiro(totais["total_entradas"])
    total_saidas = dinheiro(totais["total_saidas"])
    total_a_pagar = dinheiro(totais["total_a_pagar"])
    total_a_receber = dinheiro(totais["total_a_receber"])
    lucro_mes = dinheiro(totais["lucro_mes"])
    saldo_final = dinheiro(totais["saldo_final"])
    margem = dinheiro(totais["margem_operacional"])

    percentual_saidas = 0
    if total_entradas > 0:
        percentual_saidas = (total_saidas / total_entradas) * 100

    saldo_projetado_pos_obrigacoes = saldo_final + total_a_receber - total_a_pagar

    faltante_equilibrio = 0
    sobra_equilibrio = 0

    if total_saidas > total_entradas:
        faltante_equilibrio = total_saidas - total_entradas
    else:
        sobra_equilibrio = total_entradas - total_saidas

    despesas_top = totais["ranking_despesas"][:5]
    despesas_top3 = totais["ranking_despesas"][:3]

    total_top5 = sum(dinheiro(valor) for _, valor in despesas_top)
    total_top3 = sum(dinheiro(valor) for _, valor in despesas_top3)
    economia_10_top3 = total_top3 * 0.10

    percentual_top5_saidas = 0
    if total_saidas > 0:
        percentual_top5_saidas = (total_top5 / total_saidas) * 100

    maior_despesa_nome = None
    maior_despesa_valor = 0
    maior_despesa_percentual = 0

    if despesas_top:
        maior_despesa_nome = despesas_top[0][0]
        maior_despesa_valor = dinheiro(despesas_top[0][1])

        if total_saidas > 0:
            maior_despesa_percentual = (maior_despesa_valor / total_saidas) * 100

    meses_com_movimento_lista = [
        item for item in evolucao_mensal["tabela"]
        if dinheiro(item["entradas"]) != 0 or dinheiro(item["saidas"]) != 0
    ]

    meses_positivos_lista = [
        item for item in meses_com_movimento_lista
        if dinheiro(item["lucro"]) > 0
    ]

    meses_negativos_lista = [
        item for item in meses_com_movimento_lista
        if dinheiro(item["lucro"]) < 0
    ]

    melhor_mes = None
    pior_mes = None
    media_resultado = 0
    resultado_acumulado_ano = 0
    entradas_acumuladas_ano = 0
    saidas_acumuladas_ano = 0
    margem_media_ano = 0

    if meses_com_movimento_lista:
        melhor_mes = max(meses_com_movimento_lista, key=lambda item: dinheiro(item["lucro"]))
        pior_mes = min(meses_com_movimento_lista, key=lambda item: dinheiro(item["lucro"]))
        resultado_acumulado_ano = sum(dinheiro(item["lucro"]) for item in meses_com_movimento_lista)
        entradas_acumuladas_ano = sum(dinheiro(item["entradas"]) for item in meses_com_movimento_lista)
        saidas_acumuladas_ano = sum(dinheiro(item["saidas"]) for item in meses_com_movimento_lista)
        media_resultado = resultado_acumulado_ano / len(meses_com_movimento_lista)

        if entradas_acumuladas_ano > 0:
            margem_media_ano = (resultado_acumulado_ano / entradas_acumuladas_ano) * 100

    aproveitamento_ano = 0
    if meses_com_movimento_lista:
        aproveitamento_ano = (len(meses_positivos_lista) / len(meses_com_movimento_lista)) * 100

    tendencia_ano = "Sem base suficiente"
    tendencia_ano_classe = "neutral"
    leitura_ano_resumo = "Ainda não há movimento suficiente para leitura estratégica do ano."

    if meses_com_movimento_lista:
        if len(meses_positivos_lista) == 0 and len(meses_negativos_lista) > 0:
            tendencia_ano = "Ano em zona crítica"
            tendencia_ano_classe = "danger"
            leitura_ano_resumo = "Todos os meses com movimento fecharam negativos. A prioridade é recuperar margem e cortar vazamentos recorrentes."
        elif resultado_acumulado_ano < 0:
            tendencia_ano = "Ano pressionado"
            tendencia_ano_classe = "warning"
            leitura_ano_resumo = "O ano ainda está negativo. Existem meses bons, mas eles não compensaram os meses ruins."
        elif margem_media_ano < 10:
            tendencia_ano = "Ano positivo, mas apertado"
            tendencia_ano_classe = "warning"
            leitura_ano_resumo = "O ano está positivo, porém com margem baixa. Qualquer despesa fora do padrão pode virar prejuízo."
        else:
            tendencia_ano = "Ano saudável"
            tendencia_ano_classe = "success"
            leitura_ano_resumo = "A operação acumulada do ano está positiva e com margem operacional favorável."

    diagnostico_ano = []

    if meses_com_movimento_lista:
        diagnostico_ano.append(
            f"Foram analisados {len(meses_com_movimento_lista)} mês(es) com movimento: {len(meses_positivos_lista)} positivo(s) e {len(meses_negativos_lista)} negativo(s)."
        )

        diagnostico_ano.append(
            f"O resultado acumulado do ano está em R$ {resultado_acumulado_ano:,.2f}, com média mensal de R$ {media_resultado:,.2f}."
        )

        if len(meses_positivos_lista) == 0 and len(meses_negativos_lista) > 0:
            diagnostico_ano.append(
                "Nenhum mês analisado fechou positivo. Isso indica que o negócio ainda não encontrou ponto de equilíbrio no ano."
            )
        elif aproveitamento_ano < 50:
            diagnostico_ano.append(
                "Menos da metade dos meses fechou positivo. O foco deve ser padronizar receita e controlar despesas recorrentes."
            )
        else:
            diagnostico_ano.append(
                "A maior parte dos meses analisados fechou positiva. O foco agora é proteger margem e caixa."
            )
    else:
        diagnostico_ano.append(
            "Sem meses com movimento financeiro suficiente para montar diagnóstico anual."
        )

    leitura_vazamentos = "Sem despesas suficientes para leitura dos vazamentos."
    prioridade_corte = "Sem prioridade definida"
    prioridade_corte_classe = "neutral"

    if despesas_top:
        leitura_vazamentos = (
            f"Os 5 maiores grupos consumiram {percentual_top5_saidas:.2f}% das saídas. "
            f"O maior vazamento é {maior_despesa_nome}, com {maior_despesa_percentual:.2f}% do total de saídas."
        )

        if percentual_top5_saidas >= 60 or maior_despesa_percentual >= 25:
            prioridade_corte = "Prioridade alta"
            prioridade_corte_classe = "danger"
        elif percentual_top5_saidas >= 35 or maior_despesa_percentual >= 15:
            prioridade_corte = "Prioridade média"
            prioridade_corte_classe = "warning"
        else:
            prioridade_corte = "Prioridade controlada"
            prioridade_corte_classe = "success"

    hoje = datetime.now()
    projecao = None
    mes_atual = hoje.month == mes and hoje.year == ano

    if mes_atual and hoje.day > 0:
        dias_no_mes = calendar.monthrange(ano, mes)[1]
        dias_restantes = max(dias_no_mes - hoje.day, 0)

        entradas_projetadas = (total_entradas / hoje.day) * dias_no_mes
        saidas_projetadas = (total_saidas / hoje.day) * dias_no_mes
        resultado_projetado = entradas_projetadas - saidas_projetadas
        saldo_final_projetado = dinheiro(saldo_inicial) + resultado_projetado
        caixa_projetado_pos_obrigacoes = saldo_final_projetado + total_a_receber - total_a_pagar

        media_diaria_entradas = total_entradas / hoje.day
        media_diaria_saidas = total_saidas / hoje.day
        media_diaria_resultado = lucro_mes / hoje.day

        necessario_equilibrio_projetado = 0
        if resultado_projetado < 0:
            necessario_equilibrio_projetado = abs(resultado_projetado)

        risco = "Baixo"
        risco_classe = "success"
        leitura = "Mantendo o ritmo atual, o mês tende a fechar positivo."

        if resultado_projetado < 0:
            risco = "Alto"
            risco_classe = "danger"
            leitura = "Mantendo o ritmo atual, o mês tende a fechar negativo. É preciso reduzir saídas ou antecipar recebimentos."
        elif margem < 10:
            risco = "Médio"
            risco_classe = "warning"
            leitura = "O mês tende a fechar positivo, mas com margem apertada. Controle novas despesas."

        projecao = {
            "dia_atual": hoje.day,
            "dias_no_mes": dias_no_mes,
            "dias_restantes": dias_restantes,
            "entradas_projetadas": entradas_projetadas,
            "saidas_projetadas": saidas_projetadas,
            "resultado_projetado": resultado_projetado,
            "saldo_final_projetado": saldo_final_projetado,
            "caixa_projetado_pos_obrigacoes": caixa_projetado_pos_obrigacoes,
            "media_diaria_entradas": media_diaria_entradas,
            "media_diaria_saidas": media_diaria_saidas,
            "media_diaria_resultado": media_diaria_resultado,
            "necessario_equilibrio_projetado": necessario_equilibrio_projetado,
            "risco": risco,
            "risco_classe": risco_classe,
            "leitura": leitura,
        }

    nivel = "success"
    titulo_situacao = "Operação saudável"
    resumo_situacao = "O mês apresenta resultado positivo e margem operacional favorável."

    if lucro_mes < 0:
        nivel = "danger"
        titulo_situacao = "Resultado negativo"
        resumo_situacao = "As saídas superaram as entradas. O foco imediato deve ser reduzir custos e acelerar recebimentos."
    elif margem < 10:
        nivel = "warning"
        titulo_situacao = "Margem apertada"
        resumo_situacao = "O mês está positivo, mas com margem baixa. Qualquer aumento de custo pode comprometer o resultado."
    elif percentual_saidas >= 80:
        nivel = "warning"
        titulo_situacao = "Despesas pressionando"
        resumo_situacao = "As saídas estão consumindo uma parte alta das entradas. Vale revisar os maiores custos."
    elif saldo_projetado_pos_obrigacoes < 0:
        nivel = "danger"
        titulo_situacao = "Risco de caixa"
        resumo_situacao = "Mesmo com o saldo atual, as obrigações em aberto podem deixar o caixa negativo."

    alertas = []

    if total_entradas == 0 and total_saidas == 0:
        alertas.append({
            "nivel": "warning",
            "titulo": "Sem movimento financeiro",
            "descricao": "Não há entradas nem saídas realizadas para o mês filtrado.",
            "acao": "Verifique se as importações possuem data de pagamento nas contas pagas/recebidas."
        })

    if lucro_mes < 0:
        alertas.append({
            "nivel": "danger",
            "titulo": "Prejuízo no mês",
            "descricao": "O mês está fechando com mais saídas realizadas do que entradas realizadas.",
            "acao": "Ataque as maiores despesas e priorize recebimentos em aberto."
        })

    if percentual_saidas >= 80 and total_entradas > 0:
        alertas.append({
            "nivel": "warning",
            "titulo": "Custo consumindo receita",
            "descricao": f"As saídas representam {percentual_saidas:.2f}% das entradas.",
            "acao": "Busque reduzir custos variáveis ou renegociar os maiores pagamentos."
        })

    if total_a_pagar > saldo_final:
        alertas.append({
            "nivel": "danger",
            "titulo": "A pagar maior que saldo final",
            "descricao": "As obrigações em aberto são maiores que o saldo final atual.",
            "acao": "Priorize recebimentos e evite novos compromissos antes de reforçar o caixa."
        })

    if total_a_receber > total_entradas and total_a_receber > 0:
        alertas.append({
            "nivel": "warning",
            "titulo": "Recebíveis importantes em aberto",
            "descricao": "O valor a receber é maior que o que já entrou no mês.",
            "acao": "Acompanhe cobranças e antecipe recebimentos quando possível."
        })

    if maior_despesa_nome:
        alertas.append({
            "nivel": "info",
            "titulo": "Maior vazamento financeiro",
            "descricao": f"{maior_despesa_nome} representa R$ {maior_despesa_valor:,.2f} e {maior_despesa_percentual:.2f}% das saídas.",
            "acao": "Analise se esse custo pode ser reduzido, renegociado ou controlado por limite."
        })

    if not alertas:
        alertas.append({
            "nivel": "success",
            "titulo": "Sem alertas críticos",
            "descricao": "Os principais indicadores do mês estão dentro de um cenário saudável.",
            "acao": "Mantenha o acompanhamento e preserve a margem operacional."
        })

    acoes_recomendadas = []

    if lucro_mes < 0:
        acoes_recomendadas.append("Reduzir imediatamente as 3 maiores despesas realizadas do mês.")
        acoes_recomendadas.append("Priorizar cobrança dos valores em aberto.")
        acoes_recomendadas.append("Revisar se alguma despesa pontual distorceu o mês.")

    if economia_10_top3 > 0:
        acoes_recomendadas.append(
            f"Reduzir 10% nas 3 maiores despesas aumentaria o resultado em aproximadamente R$ {economia_10_top3:,.2f}."
        )

    if total_a_receber > 0:
        acoes_recomendadas.append(
            f"Receber os valores em aberto pode reforçar o caixa em R$ {total_a_receber:,.2f}."
        )

    if total_a_pagar > 0:
        acoes_recomendadas.append(
            f"Planejar os pagamentos em aberto de R$ {total_a_pagar:,.2f} para não pressionar o caixa."
        )

    if mes_atual and projecao and projecao["resultado_projetado"] < 0:
        acoes_recomendadas.append(
            f"Para o mês atual não fechar negativo, será necessário melhorar aproximadamente R$ {projecao['necessario_equilibrio_projetado']:,.2f} até o fim do mês."
        )

    if not acoes_recomendadas:
        acoes_recomendadas.append("Manter controle do orçamento e acompanhar os maiores custos semanalmente.")

    return {
        "nivel": nivel,
        "titulo_situacao": titulo_situacao,
        "resumo_situacao": resumo_situacao,
        "percentual_saidas": percentual_saidas,
        "saldo_projetado_pos_obrigacoes": saldo_projetado_pos_obrigacoes,
        "faltante_equilibrio": faltante_equilibrio,
        "sobra_equilibrio": sobra_equilibrio,
        "despesas_top": despesas_top,
        "despesas_top3": despesas_top3,
        "total_top3": total_top3,
        "total_top5": total_top5,
        "percentual_top5_saidas": percentual_top5_saidas,
        "economia_10_top3": economia_10_top3,
        "maior_despesa_nome": maior_despesa_nome,
        "maior_despesa_valor": maior_despesa_valor,
        "maior_despesa_percentual": maior_despesa_percentual,
        "leitura_vazamentos": leitura_vazamentos,
        "prioridade_corte": prioridade_corte,
        "prioridade_corte_classe": prioridade_corte_classe,
        "meses_com_movimento": len(meses_com_movimento_lista),
        "meses_positivos": len(meses_positivos_lista),
        "meses_negativos": len(meses_negativos_lista),
        "melhor_mes": melhor_mes,
        "pior_mes": pior_mes,
        "media_resultado": media_resultado,
        "resultado_acumulado_ano": resultado_acumulado_ano,
        "entradas_acumuladas_ano": entradas_acumuladas_ano,
        "saidas_acumuladas_ano": saidas_acumuladas_ano,
        "margem_media_ano": margem_media_ano,
        "aproveitamento_ano": aproveitamento_ano,
        "tendencia_ano": tendencia_ano,
        "tendencia_ano_classe": tendencia_ano_classe,
        "leitura_ano_resumo": leitura_ano_resumo,
        "diagnostico_ano": diagnostico_ano,
        "mes_atual": mes_atual,
        "projecao": projecao,
        "alertas": alertas,
        "acoes_recomendadas": acoes_recomendadas,
    }


# =========================================================
# DASHBOARD FINANCEIRO
# =========================================================

@gestao_bp.route("/dashboard")
@gestao_required
def dashboard():

    hoje = datetime.now()

    mes = request.args.get("mes", type=int) or hoje.month
    ano = request.args.get("ano", type=int) or hoje.year

    fechamento = FechamentoMensal.query.filter_by(
        mes=mes,
        ano=ano
    ).first()

    saldo_inicial = obter_saldo_inicial_mes(mes, ano)

    totais = calcular_totais_financeiros(
        mes=mes,
        ano=ano,
        saldo_inicial=saldo_inicial
    )

    evolucao_mensal = calcular_evolucao_mensal(ano)

    inteligencia_financeira = calcular_inteligencia_financeira(
        totais=totais,
        evolucao_mensal=evolucao_mensal,
        mes=mes,
        ano=ano,
        saldo_inicial=saldo_inicial
    )

    return render_template(
        "gestao/dashboard.html",
        mes=mes,
        ano=ano,
        fechamento=fechamento,

        saldo_inicial=saldo_inicial,
        total_entradas=totais["total_entradas"],
        total_saidas=totais["total_saidas"],
        lucro_mes=totais["lucro_mes"],
        saldo_final=totais["saldo_final"],
        total_a_pagar=totais["total_a_pagar"],
        total_a_receber=totais["total_a_receber"],
        margem_operacional=totais["margem_operacional"],

        evolucao_mensal=evolucao_mensal,
        inteligencia_financeira=inteligencia_financeira,

        ranking_despesas=totais["ranking_despesas"],
        ranking_despesas_assistencia=totais["ranking_despesas_assistencia"],
        ranking_despesas_logistica=totais["ranking_despesas_logistica"],
        ranking_receitas=totais["ranking_receitas"],
        ranking_clientes=totais["ranking_clientes"]
    )


# =========================================================
# API - DETALHES DAS CONTAS POR CATEGORIA DE DESPESA
# =========================================================

def pegar_primeiro_valor(objeto, campos, padrao="-"):
    for campo in campos:
        valor = getattr(objeto, campo, None)

        if valor not in [None, ""]:
            return valor

    return padrao


def formatar_data_json(valor):
    if not valor:
        return "-"

    try:
        return valor.strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def categoria_item_despesa(objeto):
    categoria = getattr(objeto, "categoria", None)
    plano_contas = getattr(objeto, "plano_contas", None)

    return (categoria or plano_contas or "SEM CATEGORIA").strip().upper()


@gestao_bp.route("/api/despesas-categoria")
@gestao_required
def api_despesas_categoria():
    categoria = request.args.get("categoria", "").strip().upper()
    mes = request.args.get("mes", type=int)
    ano = request.args.get("ano", type=int)

    if not categoria or not mes or not ano:
        return jsonify({
            "ok": False,
            "mensagem": "Categoria, mês e ano são obrigatórios.",
            "categoria": categoria,
            "total": 0,
            "total_pago": 0,
            "total_aberto": 0,
            "quantidade": 0,
            "itens": []
        }), 400

    inicio_dt = inicio_mes_datetime(mes, ano)
    fim_dt = fim_mes_datetime(mes, ano)

    itens = []
    total = 0
    total_pago = 0
    total_aberto = 0

    contas_pagar = ContaPagarImportada.query.filter(
        or_(
            and_(
                ContaPagarImportada.pago == True,
                ContaPagarImportada.data_pagamento >= inicio_dt,
                ContaPagarImportada.data_pagamento <= fim_dt
            ),
            and_(
                ContaPagarImportada.pago == False,
                ContaPagarImportada.data_vencimento <= fim_dt
            )
        )
    ).all()

    for conta in contas_pagar:
        categoria_conta = categoria_item_despesa(conta)

        if categoria_conta != categoria:
            continue

        valor = dinheiro(getattr(conta, "valor", 0))
        pago = bool(conta_esta_paga(conta))

        total += valor

        if pago:
            total_pago += valor
            status = "PAGO"
            data = getattr(conta, "data_pagamento", None)
        else:
            total_aberto += valor
            status = "EM ABERTO"
            data = getattr(conta, "data_vencimento", None)

        conta_nome = (
            getattr(conta, "plano_contas", None)
            or getattr(conta, "categoria", None)
            or categoria
        )

        observacao = getattr(conta, "observacoes", None) or "-"
        setor = getattr(conta, "setor", None) or "-"

        itens.append({
            "origem": "IMPORTADA",
            "tipo": "DESPESA",
            "data": formatar_data_json(data),
            "conta": str(conta_nome),
            "fornecedor_funcionario": str(getattr(conta, "fornecedor_funcionario", None) or "-"),
            "numero_fatura": str(getattr(conta, "numero_fatura", None) or "-"),
            "observacao": str(observacao),
            "setor": str(setor),
            "status": status,
            "valor": valor
        })

    lancamentos = LancamentoFinanceiro.query.filter_by(
        mes=mes,
        ano=ano
    ).all()

    for lancamento in lancamentos:
        if status_cancelado(getattr(lancamento, "status", None)):
            continue

        tipo = normalizar_texto(getattr(lancamento, "tipo", None))

        if tipo != "DESPESA":
            continue

        categoria_lancamento = (
            getattr(lancamento, "categoria", None) or "SEM CATEGORIA"
        ).strip().upper()

        if categoria_lancamento != categoria:
            continue

        valor = dinheiro(getattr(lancamento, "valor", 0))
        pago = status_pago(getattr(lancamento, "status", None))

        total += valor

        if pago:
            total_pago += valor
            status = getattr(lancamento, "status", None) or "PAGO"
        else:
            total_aberto += valor
            status = getattr(lancamento, "status", None) or "EM ABERTO"

        conta_nome = (
            getattr(lancamento, "subcategoria", None)
            or getattr(lancamento, "categoria", None)
            or categoria_lancamento
        )

        observacao = (
            getattr(lancamento, "observacoes", None)
            or getattr(lancamento, "observacao", None)
            or getattr(lancamento, "descricao", None)
            or "-"
        )

        itens.append({
            "origem": "MANUAL",
            "tipo": "DESPESA",
            "data": formatar_data_json(getattr(lancamento, "data", None)),
            "conta": str(conta_nome),
            "fornecedor_funcionario": getattr(lancamento, "cliente", None) or "-",
            "numero_fatura": "-",
            "observacao": str(observacao),
            "setor": getattr(lancamento, "setor", None) or "-",
            "status": status,
            "valor": valor
        })

    itens = sorted(
        itens,
        key=lambda item: item["valor"],
        reverse=True
    )

    return jsonify({
        "ok": True,
        "categoria": categoria,
        "mes": mes,
        "ano": ano,
        "total": total,
        "total_pago": total_pago,
        "total_aberto": total_aberto,
        "quantidade": len(itens),
        "itens": itens
    })


# =========================================================
# FECHAMENTO MENSAL
# =========================================================

@gestao_bp.route("/fechamento", methods=["GET", "POST"])
@gestao_required
def fechamento():

    hoje = datetime.now()

    mes = request.args.get("mes", type=int) or hoje.month
    ano = request.args.get("ano", type=int) or hoje.year

    fechamento_existente = FechamentoMensal.query.filter_by(
        mes=mes,
        ano=ano
    ).first()

    saldo_inicial = obter_saldo_inicial_mes(mes, ano)
    saldo_inicial_automatico = obter_saldo_inicial_automatico(mes, ano)

    if request.method == "POST":
        mes = request.form.get("mes", type=int)
        ano = request.form.get("ano", type=int)

        saldo_inicial = dinheiro(request.form.get("saldo_inicial"))

        totais = calcular_totais_financeiros(
            mes=mes,
            ano=ano,
            saldo_inicial=saldo_inicial
        )

        fechamento_existente = FechamentoMensal.query.filter_by(
            mes=mes,
            ano=ano
        ).first()

        if fechamento_existente:
            fechamento_existente.saldo_inicial = saldo_inicial
            fechamento_existente.total_entradas = totais["total_entradas"]
            fechamento_existente.total_saidas = totais["total_saidas"]
            fechamento_existente.lucro_mes = totais["lucro_mes"]
            fechamento_existente.saldo_final = totais["saldo_final"]
            fechamento_existente.total_a_pagar = totais["total_a_pagar"]
            fechamento_existente.total_a_receber = totais["total_a_receber"]
            fechamento_existente.margem_operacional = totais["margem_operacional"]
            fechamento_existente.fechado = True
        else:
            fechamento_existente = FechamentoMensal(
                mes=mes,
                ano=ano,
                saldo_inicial=saldo_inicial,
                total_entradas=totais["total_entradas"],
                total_saidas=totais["total_saidas"],
                lucro_mes=totais["lucro_mes"],
                saldo_final=totais["saldo_final"],
                total_a_pagar=totais["total_a_pagar"],
                total_a_receber=totais["total_a_receber"],
                margem_operacional=totais["margem_operacional"],
                fechado=True
            )

            db.session.add(fechamento_existente)

        db.session.commit()

        flash("Fechamento mensal salvo com sucesso!", "success")
        return redirect(f"/gestao/fechamento?mes={mes}&ano={ano}")

    totais = calcular_totais_financeiros(
        mes=mes,
        ano=ano,
        saldo_inicial=saldo_inicial
    )

    return render_template(
        "gestao/fechamento.html",
        mes=mes,
        ano=ano,
        fechamento=fechamento_existente,
        saldo_inicial=saldo_inicial,
        saldo_inicial_automatico=saldo_inicial_automatico,
        total_entradas=totais["total_entradas"],
        total_saidas=totais["total_saidas"],
        lucro_mes=totais["lucro_mes"],
        saldo_final=totais["saldo_final"],
        total_a_pagar=totais["total_a_pagar"],
        total_a_receber=totais["total_a_receber"],
        margem_operacional=totais["margem_operacional"]
    )


# =========================================================
# LANÇAMENTOS MANUAIS
# =========================================================

@gestao_bp.route("/lancamentos")
@gestao_required
def lancamentos():

    query = LancamentoFinanceiro.query

    mes = request.args.get("mes", type=int)
    ano = request.args.get("ano", type=int)
    tipo = request.args.get("tipo")
    status = request.args.get("status")
    categoria = request.args.get("categoria")

    if mes:
        query = query.filter(LancamentoFinanceiro.mes == mes)

    if ano:
        query = query.filter(LancamentoFinanceiro.ano == ano)

    if tipo:
        query = query.filter(LancamentoFinanceiro.tipo == tipo)

    if status:
        query = query.filter(LancamentoFinanceiro.status == status)

    if categoria:
        query = query.filter(
            LancamentoFinanceiro.categoria.ilike(f"%{categoria}%")
        )

    lancamentos = query.order_by(
        LancamentoFinanceiro.data.desc(),
        LancamentoFinanceiro.id.desc()
    ).all()

    return render_template(
        "gestao/lancamentos.html",
        lancamentos=lancamentos,
        mes=mes,
        ano=ano,
        tipo=tipo,
        status=status,
        categoria=categoria
    )


@gestao_bp.route("/lancamentos/novo", methods=["GET", "POST"])
@gestao_required
def novo_lancamento():

    if request.method == "POST":

        data = parse_data(request.form.get("data"))

        if not data:
            flash("Informe uma data válida.", "danger")
            return redirect("/gestao/lancamentos/novo")

        lancamento = LancamentoFinanceiro(
            data=data,
            tipo=normalizar_texto(request.form.get("tipo")),
            categoria=normalizar_texto(request.form.get("categoria")),
            subcategoria=normalizar_texto(request.form.get("subcategoria")),
            setor=normalizar_texto(request.form.get("setor")),
            cliente=normalizar_texto(request.form.get("cliente")),
            descricao=request.form.get("descricao"),
            valor=request.form.get("valor") or 0,
            status=normalizar_texto(request.form.get("status")),
            origem=normalizar_texto(request.form.get("origem")),
            recorrente=True if request.form.get("recorrente") == "on" else False,
            mes=data.month,
            ano=data.year
        )

        db.session.add(lancamento)
        db.session.commit()

        flash("Lançamento criado com sucesso!", "success")
        return redirect("/gestao/lancamentos")

    return render_template(
        "gestao/form_lancamento.html",
        lancamento=None
    )


@gestao_bp.route("/lancamentos/editar/<int:id>", methods=["GET", "POST"])
@gestao_required
def editar_lancamento(id):

    lancamento = LancamentoFinanceiro.query.get_or_404(id)

    if request.method == "POST":

        data = parse_data(request.form.get("data"))

        if not data:
            flash("Informe uma data válida.", "danger")
            return redirect(f"/gestao/lancamentos/editar/{id}")

        lancamento.data = data
        lancamento.tipo = normalizar_texto(request.form.get("tipo"))
        lancamento.categoria = normalizar_texto(request.form.get("categoria"))
        lancamento.subcategoria = normalizar_texto(request.form.get("subcategoria"))
        lancamento.setor = normalizar_texto(request.form.get("setor"))
        lancamento.cliente = normalizar_texto(request.form.get("cliente"))
        lancamento.descricao = request.form.get("descricao")
        lancamento.valor = request.form.get("valor") or 0
        lancamento.status = normalizar_texto(request.form.get("status"))
        lancamento.origem = normalizar_texto(request.form.get("origem"))
        lancamento.recorrente = True if request.form.get("recorrente") == "on" else False
        lancamento.mes = data.month
        lancamento.ano = data.year

        db.session.commit()

        flash("Lançamento atualizado com sucesso!", "success")
        return redirect("/gestao/lancamentos")

    return render_template(
        "gestao/form_lancamento.html",
        lancamento=lancamento
    )


@gestao_bp.route("/lancamentos/excluir/<int:id>")
@gestao_required
def excluir_lancamento(id):

    lancamento = LancamentoFinanceiro.query.get_or_404(id)

    db.session.delete(lancamento)
    db.session.commit()

    flash("Lançamento excluído com sucesso!", "success")
    return redirect("/gestao/lancamentos")


# =========================================================
# FLUXO DIÁRIO FINANCEIRO
# SOMENTE MOVIMENTAÇÃO REALIZADA
# =========================================================

def calcular_totais_reais_periodo(data_inicio, data_fim):
    total_despesas = 0
    total_receitas = 0

    inicio_dt = datetime.combine(data_inicio, datetime.min.time())
    fim_dt = datetime.combine(data_fim, datetime.max.time())

    contas_pagar = ContaPagarImportada.query.filter(
        ContaPagarImportada.pago == True,
        ContaPagarImportada.data_pagamento >= inicio_dt,
        ContaPagarImportada.data_pagamento <= fim_dt
    ).all()

    contas_receber = ContaReceberImportada.query.filter(
        ContaReceberImportada.pago == True,
        ContaReceberImportada.data_pagamento >= inicio_dt,
        ContaReceberImportada.data_pagamento <= fim_dt
    ).all()

    for conta in contas_pagar:
        total_despesas += dinheiro(getattr(conta, "valor", 0))

    for conta in contas_receber:
        total_receitas += valor_conta_receber(conta)

    lancamentos = LancamentoFinanceiro.query.filter(
        LancamentoFinanceiro.data >= data_inicio,
        LancamentoFinanceiro.data <= data_fim
    ).all()

    for lancamento in lancamentos:
        if status_cancelado(getattr(lancamento, "status", None)):
            continue

        if not status_pago(getattr(lancamento, "status", None)):
            continue

        tipo = normalizar_texto(getattr(lancamento, "tipo", None))
        valor = dinheiro(getattr(lancamento, "valor", 0))

        if tipo == "DESPESA":
            total_despesas += valor
        elif tipo == "RECEITA":
            total_receitas += valor

    return total_despesas, total_receitas


@gestao_bp.route("/fluxo-diario")
@gestao_required
def fluxo_diario():

    hoje = datetime.now()

    mes = request.args.get("mes", type=int) or hoje.month
    ano = request.args.get("ano", type=int) or hoje.year
    visao = request.args.get("visao") or "mes_ano"

    if visao not in ["mes", "ano", "mes_ano"]:
        visao = "mes_ano"

    primeiro_dia = primeiro_dia_mes(mes, ano)
    ultimo_dia = ultimo_dia_mes(mes, ano)
    ultimo_dia_numero = ultimo_dia.day

    inicio_dt = datetime.combine(primeiro_dia, datetime.min.time())
    fim_dt = datetime.combine(ultimo_dia, datetime.max.time())

    # =====================================================
    # TRANSPORTE DOS MESES ANTERIORES
    # Tudo que realmente entrou/saiu de 01/01 até o dia
    # anterior ao mês filtrado
    # =====================================================
    if mes > 1:
        data_inicio_transporte = date(ano, 1, 1)
        data_fim_transporte = primeiro_dia - timedelta(days=1)

        despesas_transporte, receitas_transporte = calcular_totais_reais_periodo(
            data_inicio=data_inicio_transporte,
            data_fim=data_fim_transporte
        )
    else:
        despesas_transporte = 0
        receitas_transporte = 0

    saldo_transporte = dinheiro(receitas_transporte) - dinheiro(despesas_transporte)

    # =====================================================
    # CONTAS IMPORTADAS REALIZADAS NO MÊS
    # Fluxo usa data_pagamento, não data_vencimento
    # =====================================================
    contas_pagar_mes = ContaPagarImportada.query.filter(
        ContaPagarImportada.pago == True,
        ContaPagarImportada.data_pagamento >= inicio_dt,
        ContaPagarImportada.data_pagamento <= fim_dt
    ).all()

    contas_receber_mes = ContaReceberImportada.query.filter(
        ContaReceberImportada.pago == True,
        ContaReceberImportada.data_pagamento >= inicio_dt,
        ContaReceberImportada.data_pagamento <= fim_dt
    ).all()

    lancamentos_mes = LancamentoFinanceiro.query.filter(
        LancamentoFinanceiro.data >= primeiro_dia,
        LancamentoFinanceiro.data <= ultimo_dia
    ).all()

    despesas_por_dia = {}
    receitas_por_dia = {}

    total_despesas_mes = 0
    total_receitas_mes = 0

    for conta in contas_pagar_mes:
        valor = dinheiro(getattr(conta, "valor", 0))
        data_mov = data_movimento_fluxo(conta)

        if not data_mov:
            continue

        total_despesas_mes += valor
        despesas_por_dia[data_mov] = despesas_por_dia.get(data_mov, 0) + valor

    for conta in contas_receber_mes:
        valor = valor_conta_receber(conta)
        data_mov = data_movimento_fluxo(conta)

        if not data_mov:
            continue

        total_receitas_mes += valor
        receitas_por_dia[data_mov] = receitas_por_dia.get(data_mov, 0) + valor

    for lancamento in lancamentos_mes:
        if status_cancelado(getattr(lancamento, "status", None)):
            continue

        if not status_pago(getattr(lancamento, "status", None)):
            continue

        data_mov = data_para_date(getattr(lancamento, "data", None))

        if not data_mov:
            continue

        tipo = normalizar_texto(getattr(lancamento, "tipo", None))
        valor = dinheiro(getattr(lancamento, "valor", 0))

        if tipo == "DESPESA":
            total_despesas_mes += valor
            despesas_por_dia[data_mov] = despesas_por_dia.get(data_mov, 0) + valor
        elif tipo == "RECEITA":
            total_receitas_mes += valor
            receitas_por_dia[data_mov] = receitas_por_dia.get(data_mov, 0) + valor

    saldo_mes = dinheiro(total_receitas_mes) - dinheiro(total_despesas_mes)

    total_receitas_ano = dinheiro(receitas_transporte) + dinheiro(total_receitas_mes)
    total_despesas_ano = dinheiro(despesas_transporte) + dinheiro(total_despesas_mes)
    saldo_ano = dinheiro(total_receitas_ano) - dinheiro(total_despesas_ano)

    linhas = []
    acumulado = dinheiro(saldo_transporte)

    linhas.append({
        "tipo": "transporte",
        "dia": "** TRANSPORTE MESES ANTERIORES **",
        "data": None,
        "despesas": dinheiro(despesas_transporte),
        "receitas": dinheiro(receitas_transporte),
        "saldo": dinheiro(saldo_transporte),
        "acumulado": dinheiro(saldo_transporte)
    })

    for dia in range(1, ultimo_dia_numero + 1):

        data_ref = date(ano, mes, dia)

        despesas = dinheiro(despesas_por_dia.get(data_ref, 0))
        receitas = dinheiro(receitas_por_dia.get(data_ref, 0))
        saldo_dia = dinheiro(receitas) - dinheiro(despesas)

        acumulado += saldo_dia

        linhas.append({
            "tipo": "dia",
            "dia": f"{dia:02d}/{mes:02d} - {nome_dia_semana(data_ref)}",
            "data": data_ref,
            "despesas": despesas,
            "receitas": receitas,
            "saldo": saldo_dia,
            "acumulado": acumulado
        })

    return render_template(
        "gestao/fluxo_diario.html",
        mes=mes,
        ano=ano,
        visao=visao,
        linhas=linhas,

        total_despesas_mes=total_despesas_mes,
        total_receitas_mes=total_receitas_mes,
        saldo_mes=saldo_mes,

        despesas_transporte=despesas_transporte,
        receitas_transporte=receitas_transporte,
        saldo_transporte=saldo_transporte,

        total_despesas_ano=total_despesas_ano,
        total_receitas_ano=total_receitas_ano,
        saldo_ano=saldo_ano
    )


# =========================================================
# RADAR DE PAGAMENTOS
# SOMENTE DESPESAS - PAGAS E PENDENTES
# =========================================================

def status_visual_conta_pagar(conta, hoje):
    data_vencimento = data_para_date(conta.data_vencimento)

    if conta_esta_paga(conta):
        return {
            "label": "PAGO",
            "classe": "pago",
            "grupo": "pagas"
        }

    if not data_vencimento:
        return {
            "label": "SEM DATA",
            "classe": "sem-data",
            "grupo": "sem_data"
        }

    if data_vencimento < hoje:
        return {
            "label": "ATRASADA",
            "classe": "atrasada",
            "grupo": "atrasadas"
        }

    if data_vencimento == hoje:
        return {
            "label": "VENCE HOJE",
            "classe": "vence-hoje",
            "grupo": "vence_hoje"
        }

    if data_vencimento <= hoje + timedelta(days=7):
        return {
            "label": "PRÓXIMOS 7 DIAS",
            "classe": "proxima",
            "grupo": "proximas"
        }

    return {
        "label": "FUTURA",
        "classe": "futura",
        "grupo": "futuras"
    }


def montar_item_radar_pagar(conta, hoje):
    status_info = status_visual_conta_pagar(conta, hoje)

    data_vencimento = data_para_date(conta.data_vencimento)
    data_pagamento = data_para_date(conta.data_pagamento)

    dias = None

    if data_vencimento and not conta_esta_paga(conta):
        dias = (data_vencimento - hoje).days

    return {
        "id": conta.id,
        "numero_fatura": conta.numero_fatura or "-",
        "fornecedor_funcionario": conta.fornecedor_funcionario or "-",
        "plano_contas": conta.plano_contas or "-",
        "categoria": conta.categoria or "-",
        "setor": conta.setor or "-",
        "data_vencimento": data_vencimento,
        "data_pagamento": data_pagamento,
        "valor": dinheiro(conta.valor),
        "pago": bool(conta_esta_paga(conta)),
        "status": conta.status or "-",
        "observacoes": conta.observacoes or "-",
        "status_label": status_info["label"],
        "status_classe": status_info["classe"],
        "grupo": status_info["grupo"],
        "dias": dias
    }


def somar_itens_radar(lista):
    return sum(dinheiro(item.get("valor")) for item in lista)


@gestao_bp.route("/radar-pagamentos")
@gestao_required
def radar_pagamentos():

    hoje = date.today()

    mes = request.args.get("mes", type=int) or hoje.month
    ano = request.args.get("ano", type=int) or hoje.year
    setor = request.args.get("setor", "").strip().upper()
    filtro = request.args.get("filtro", "todos").strip().lower()

    inicio_dt = inicio_mes_datetime(mes, ano)
    fim_dt = fim_mes_datetime(mes, ano)

    # =====================================================
    # RADAR USA VENCIMENTO
    # Mostra:
    # - contas pagas com vencimento dentro do mês filtrado
    # - contas abertas vencidas até o fim do mês filtrado
    #   incluindo atrasadas de meses anteriores
    # - contas sem data que foram importadas no mês/ano
    # =====================================================
    query = ContaPagarImportada.query.filter(
        or_(
            and_(
                ContaPagarImportada.pago == True,
                ContaPagarImportada.data_vencimento >= inicio_dt,
                ContaPagarImportada.data_vencimento <= fim_dt
            ),
            and_(
                ContaPagarImportada.pago == False,
                ContaPagarImportada.data_vencimento <= fim_dt
            ),
            and_(
                ContaPagarImportada.data_vencimento == None,
                ContaPagarImportada.mes == mes,
                ContaPagarImportada.ano == ano
            )
        )
    )

    if setor:
        query = query.filter(
            ContaPagarImportada.setor.ilike(f"%{setor}%")
        )

    contas = query.order_by(
        ContaPagarImportada.data_vencimento.asc().nullslast(),
        ContaPagarImportada.id.desc()
    ).all()

    itens = [
        montar_item_radar_pagar(conta, hoje)
        for conta in contas
    ]

    atrasadas = [item for item in itens if item["grupo"] == "atrasadas"]
    vence_hoje = [item for item in itens if item["grupo"] == "vence_hoje"]
    proximas = [item for item in itens if item["grupo"] == "proximas"]
    futuras = [item for item in itens if item["grupo"] == "futuras"]
    pagas = [item for item in itens if item["grupo"] == "pagas"]
    sem_data = [item for item in itens if item["grupo"] == "sem_data"]
    abertas = [item for item in itens if not item["pago"]]

    if filtro == "pagas":
        itens_filtrados = pagas
    elif filtro == "abertas":
        itens_filtrados = abertas
    elif filtro == "atrasadas":
        itens_filtrados = atrasadas
    elif filtro == "hoje":
        itens_filtrados = vence_hoje
    elif filtro == "proximas":
        itens_filtrados = proximas
    elif filtro == "futuras":
        itens_filtrados = futuras
    elif filtro == "sem_data":
        itens_filtrados = sem_data
    else:
        itens_filtrados = itens

    total_geral = somar_itens_radar(itens)
    total_pagas = somar_itens_radar(pagas)
    total_abertas = somar_itens_radar(abertas)
    total_atrasadas = somar_itens_radar(atrasadas)
    total_hoje = somar_itens_radar(vence_hoje)
    total_proximas = somar_itens_radar(proximas)
    total_futuras = somar_itens_radar(futuras)

    return render_template(
        "gestao/radar_pagamentos.html",
        hoje=hoje,
        mes=mes,
        ano=ano,
        setor=setor,
        filtro=filtro,

        itens=itens,
        itens_filtrados=itens_filtrados,

        atrasadas=atrasadas,
        vence_hoje=vence_hoje,
        proximas=proximas,
        futuras=futuras,
        pagas=pagas,
        abertas=abertas,
        sem_data=sem_data,

        total_geral=total_geral,
        total_pagas=total_pagas,
        total_abertas=total_abertas,
        total_atrasadas=total_atrasadas,
        total_hoje=total_hoje,
        total_proximas=total_proximas,
        total_futuras=total_futuras
    )


@gestao_bp.route("/radar-pagamentos/pagar/<int:id>", methods=["POST"])
@gestao_required
def radar_marcar_pago(id):

    conta = ContaPagarImportada.query.get_or_404(id)

    data_pagamento_str = request.form.get("data_pagamento")
    observacao_extra = request.form.get("observacao", "").strip()

    data_pagamento = parse_data(data_pagamento_str)

    if not data_pagamento:
        data_pagamento = date.today()

    conta.pago = True
    conta.status = "PAGO"
    conta.data_pagamento = datetime.combine(
        data_pagamento,
        datetime.min.time()
    )

    if observacao_extra:
        observacao_antiga = conta.observacoes or ""
        conta.observacoes = f"{observacao_antiga}\nPagamento: {observacao_extra}".strip()

    db.session.commit()

    flash("Conta marcada como paga com sucesso!", "success")

    return redirect(request.referrer or "/gestao/radar-pagamentos")


@gestao_bp.route("/radar-pagamentos/adiar/<int:id>", methods=["POST"])
@gestao_required
def radar_adiar_pagamento(id):

    conta = ContaPagarImportada.query.get_or_404(id)

    nova_data_str = request.form.get("nova_data_vencimento")
    motivo = request.form.get("motivo", "").strip()

    nova_data = parse_data(nova_data_str)

    if not nova_data:
        flash("Informe uma nova data válida.", "danger")
        return redirect(request.referrer or "/gestao/radar-pagamentos")

    data_antiga = data_para_date(conta.data_vencimento)

    conta.data_vencimento = datetime.combine(
        nova_data,
        datetime.min.time()
    )

    # Mantém mes/ano sincronizado para listagens administrativas,
    # mas as telas financeiras agora usam data_vencimento/data_pagamento.
    conta.mes = nova_data.month
    conta.ano = nova_data.year

    if not conta_esta_paga(conta):
        conta.status = "ADIADO"

    observacao_antiga = conta.observacoes or ""

    texto_adiamento = (
        f"Adiamento: vencimento alterado de "
        f"{data_antiga.strftime('%d/%m/%Y') if data_antiga else '-'} "
        f"para {nova_data.strftime('%d/%m/%Y')}."
    )

    if motivo:
        texto_adiamento += f" Motivo: {motivo}"

    conta.observacoes = f"{observacao_antiga}\n{texto_adiamento}".strip()

    db.session.commit()

    flash("Pagamento adiado com sucesso!", "success")

    return redirect(request.referrer or "/gestao/radar-pagamentos")