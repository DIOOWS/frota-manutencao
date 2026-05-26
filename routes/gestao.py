from flask import Blueprint, render_template, request, redirect, flash, jsonify
from utils.auth import gestao_required
from models.lancamento_financeiro import LancamentoFinanceiro
from models.fechamento_mensal import FechamentoMensal
from models.conta_pagar_importada import ContaPagarImportada
from models.conta_receber_importada import ContaReceberImportada
from models.conta_recorrente import ContaRecorrente
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
        ContaPagarImportada.origem_importacao == "PAGAMENTO",
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
        ContaPagarImportada.origem_importacao == "PAGAMENTO",
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
        ContaReceberImportada.origem_importacao == "RECEBIMENTO",
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
        ContaReceberImportada.origem_importacao == "RECEBIMENTO",
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
                ContaPagarImportada.origem_importacao == "PAGAMENTO",
                ContaPagarImportada.data_pagamento >= inicio_dt,
                ContaPagarImportada.data_pagamento <= fim_dt
            ),
            and_(
                ContaPagarImportada.pago == False,
                ContaPagarImportada.origem_importacao == "PAGAMENTO",
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



@gestao_bp.route("/fechamento/excluir", methods=["POST"])
@gestao_required
def excluir_fechamento():

    mes = request.form.get("mes", type=int)
    ano = request.form.get("ano", type=int)

    if not mes or not ano:
        flash("Informe mês e ano válidos para excluir o fechamento.", "danger")
        return redirect("/gestao/fechamento")

    fechamento_existente = FechamentoMensal.query.filter_by(
        mes=mes,
        ano=ano
    ).first()

    if not fechamento_existente:
        flash("Nenhum fechamento encontrado para excluir neste mês.", "warning")
        return redirect(f"/gestao/fechamento?mes={mes}&ano={ano}")

    try:
        db.session.delete(fechamento_existente)
        db.session.commit()

        flash("Fechamento excluído com sucesso!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir fechamento: {str(e)}", "danger")

    return redirect(f"/gestao/fechamento?mes={mes}&ano={ano}")


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
        ContaPagarImportada.origem_importacao == "PAGAMENTO",
        ContaPagarImportada.data_pagamento >= inicio_dt,
        ContaPagarImportada.data_pagamento <= fim_dt
    ).all()

    contas_receber = ContaReceberImportada.query.filter(
        ContaReceberImportada.pago == True,
        ContaReceberImportada.origem_importacao == "RECEBIMENTO",
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
        ContaPagarImportada.origem_importacao == "PAGAMENTO",
        ContaPagarImportada.data_pagamento >= inicio_dt,
        ContaPagarImportada.data_pagamento <= fim_dt
    ).all()

    contas_receber_mes = ContaReceberImportada.query.filter(
        ContaReceberImportada.pago == True,
        ContaReceberImportada.origem_importacao == "RECEBIMENTO",
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
                ContaPagarImportada.origem_importacao == "PAGAMENTO",
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

# =========================================================
# RADAR FINANCEIRO INTELIGENTE
# DÍVIDA HERDADA AGRUPADA + HISTÓRICO POR MÊS
# =========================================================

def radar_moeda(valor):
    valor = dinheiro(valor)
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def radar_nome_mes(mes):
    nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
    }
    return nomes.get(int(mes or 0), str(mes or ""))


def radar_nome_mes_curto(mes):
    nomes = {
        1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr",
        5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago",
        9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
    }
    return nomes.get(int(mes or 0), str(mes or ""))


def radar_data_input(valor):
    data_ref = data_para_date(valor)
    if not data_ref:
        return ""
    return data_ref.strftime("%Y-%m-%d")


def radar_data_br(valor):
    data_ref = data_para_date(valor)
    if not data_ref:
        return "-"
    return data_ref.strftime("%d/%m/%Y")


def radar_competencia_label(data_ref):
    data_ref = data_para_date(data_ref)
    if not data_ref:
        return "-"
    return f"{radar_nome_mes(data_ref.month)}/{data_ref.year}"


def radar_texto(valor, padrao="-"):
    if valor is None:
        return padrao
    valor = str(valor).strip()
    return valor if valor else padrao


def radar_descricao_conta(conta):
    return (
        radar_texto(getattr(conta, "plano_contas", None), "")
        or radar_texto(getattr(conta, "categoria", None), "")
        or radar_texto(getattr(conta, "fornecedor_funcionario", None), "")
        or radar_texto(getattr(conta, "numero_fatura", None), "")
        or f"Conta #{conta.id}"
    )


def radar_fornecedor_conta(conta):
    return radar_texto(getattr(conta, "fornecedor_funcionario", None), "-")


def radar_categoria_conta(conta):
    return radar_texto(getattr(conta, "categoria", None), "-")


def radar_setor_conta(conta):
    return radar_texto(getattr(conta, "setor", None), "GERAL")


def radar_normalizar_chave(valor):
    valor = radar_texto(valor, "")
    return " ".join(valor.upper().split())


def radar_chave_grupo(conta):
    import hashlib

    partes = [
        radar_normalizar_chave(radar_descricao_conta(conta)),
        radar_normalizar_chave(radar_fornecedor_conta(conta)),
        radar_normalizar_chave(radar_categoria_conta(conta)),
        radar_normalizar_chave(radar_setor_conta(conta)),
    ]

    base = "|".join(partes)
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def radar_mesmo_grupo(item, chave):
    return item.get("grupo_key") == chave


def radar_conta_cancelada(conta):
    return status_cancelado(getattr(conta, "status", None))


def radar_conta_aberta(conta):
    return not conta_esta_paga(conta) and not radar_conta_cancelada(conta)


def radar_valor_conta(conta):
    return dinheiro(getattr(conta, "valor", 0))


def radar_item_conta(conta, hoje):
    data_vencimento = data_para_date(getattr(conta, "data_vencimento", None))
    data_pagamento = data_para_date(getattr(conta, "data_pagamento", None))
    valor = radar_valor_conta(conta)
    pago = conta_esta_paga(conta)
    dias_atraso = 0
    dias_para_vencer = None

    if data_vencimento:
        if data_vencimento < hoje and not pago:
            dias_atraso = (hoje - data_vencimento).days
        elif data_vencimento >= hoje and not pago:
            dias_para_vencer = (data_vencimento - hoje).days

    status_label = "PAGO" if pago else "EM ABERTO"
    status_classe = "pago" if pago else "aberto"

    if not pago and data_vencimento:
        if data_vencimento < hoje:
            status_label = "ATRASADA"
            status_classe = "vencido"
        elif data_vencimento == hoje:
            status_label = "HOJE"
            status_classe = "hoje"
        elif data_vencimento <= hoje + timedelta(days=7):
            status_label = f"{dias_para_vencer} dia(s)"
            status_classe = "proximo"
        else:
            status_label = f"{dias_para_vencer} dia(s)"
            status_classe = "futuro"

    if radar_conta_cancelada(conta):
        status_label = "CANCELADA"
        status_classe = "cancelado"

    return {
        "id": conta.id,
        "conta": conta,
        "grupo_key": radar_chave_grupo(conta),
        "descricao": radar_descricao_conta(conta),
        "fornecedor": radar_fornecedor_conta(conta),
        "categoria": radar_categoria_conta(conta),
        "setor": radar_setor_conta(conta),
        "valor": valor,
        "valor_formatado": radar_moeda(valor),
        "data_vencimento": data_vencimento,
        "data_vencimento_formatada": radar_data_br(data_vencimento),
        "data_vencimento_input": radar_data_input(data_vencimento),
        "data_pagamento": data_pagamento,
        "data_pagamento_formatada": radar_data_br(data_pagamento),
        "data_pagamento_input": radar_data_input(data_pagamento),
        "competencia": radar_competencia_label(data_vencimento),
        "pago": pago,
        "status": radar_texto(getattr(conta, "status", None), "PENDENTE"),
        "status_label": status_label,
        "status_classe": status_classe,
        "dias_atraso": dias_atraso,
        "dias_para_vencer": dias_para_vencer,
        "observacoes": radar_texto(getattr(conta, "observacoes", None), ""),
        "numero_fatura": radar_texto(getattr(conta, "numero_fatura", None), "-"),
        "recorrente": str(getattr(conta, "chave_conciliacao", "") or "").startswith("RECORRENTE:"),
    }


def radar_chave_recorrente(recorrencia_id, mes, ano):
    return f"RECORRENTE:{recorrencia_id}:{int(mes):02d}:{int(ano)}"


def radar_mes_ano_iter(inicio, fim):
    mes = inicio.month
    ano = inicio.year

    while (ano, mes) <= (fim.year, fim.month):
        yield mes, ano

        mes += 1

        if mes > 12:
            mes = 1
            ano += 1


def radar_criar_conta_recorrente_mes(recorrencia, mes, ano):
    chave = radar_chave_recorrente(recorrencia.id, mes, ano)

    existente = ContaPagarImportada.query.filter_by(
        chave_conciliacao=chave
    ).first()

    if existente:
        return None

    ultimo_dia = calendar.monthrange(ano, mes)[1]
    dia_vencimento = min(int(recorrencia.dia_vencimento or 1), ultimo_dia)
    data_vencimento = date(ano, mes, dia_vencimento)

    observacoes_base = recorrencia.observacoes or ""
    observacao_recorrencia = (
        f"Conta gerada automaticamente pela recorrência #{recorrencia.id}. "
        f"Competência: {radar_competencia_label(data_vencimento)}."
    )

    conta = ContaPagarImportada(
        numero_fatura=f"REC-{recorrencia.id}-{mes:02d}-{ano}",
        fornecedor_funcionario=recorrencia.fornecedor_funcionario,
        plano_contas=recorrencia.plano_contas or recorrencia.descricao,
        categoria=recorrencia.categoria,
        setor=recorrencia.setor or "GERAL",
        data_documento=datetime.combine(date.today(), datetime.min.time()),
        data_vencimento=datetime.combine(data_vencimento, datetime.min.time()),
        valor=recorrencia.valor,
        pago=False,
        status="PENDENTE",
        observacoes=f"{observacao_recorrencia}\n{observacoes_base}".strip(),
        mes=mes,
        ano=ano,
        chave_conciliacao=chave,
        origem_importacao="RECORRENTE",
    )

    db.session.add(conta)

    return conta


def radar_gerar_recorrencias_ate_mes(mes, ano):
    data_limite = ultimo_dia_mes(mes, ano)

    recorrencias = ContaRecorrente.query.filter_by(
        ativo=True
    ).all()

    total_criadas = 0

    for recorrencia in recorrencias:
        data_inicio = recorrencia.data_inicio or date(ano, mes, 1)
        data_fim = recorrencia.data_fim

        if data_inicio > data_limite:
            continue

        fim_geracao = data_limite

        if data_fim and data_fim < fim_geracao:
            fim_geracao = data_fim

        for mes_ref, ano_ref in radar_mes_ano_iter(data_inicio, fim_geracao):
            criada = radar_criar_conta_recorrente_mes(
                recorrencia=recorrencia,
                mes=mes_ref,
                ano=ano_ref
            )

            if criada:
                total_criadas += 1

    if total_criadas:
        db.session.commit()

    return total_criadas


def radar_filtrar_busca(contas, busca):
    busca = radar_normalizar_chave(busca)

    if not busca:
        return contas

    filtradas = []

    for conta in contas:
        texto_busca = " ".join([
            radar_descricao_conta(conta),
            radar_fornecedor_conta(conta),
            radar_categoria_conta(conta),
            radar_setor_conta(conta),
            radar_texto(getattr(conta, "numero_fatura", None), ""),
            radar_texto(getattr(conta, "observacoes", None), ""),
        ])

        if busca in radar_normalizar_chave(texto_busca):
            filtradas.append(conta)

    return filtradas


def radar_agrupar_herdadas(contas_herdadas, hoje):
    grupos_map = {}

    for conta in contas_herdadas:
        item = radar_item_conta(conta, hoje)
        chave = item["grupo_key"]

        if chave not in grupos_map:
            grupos_map[chave] = {
                "grupo_key": chave,
                "descricao": item["descricao"],
                "fornecedor": item["fornecedor"],
                "categoria": item["categoria"],
                "setor": item["setor"],
                "total": 0,
                "total_formatado": radar_moeda(0),
                "qtd": 0,
                "desde_data": item["data_vencimento"],
                "desde_label": item["competencia"],
                "maior_atraso": 0,
                "atraso_medio": 0,
                "historico": [],
            }

        grupo = grupos_map[chave]
        grupo["total"] += item["valor"]
        grupo["qtd"] += 1
        grupo["historico"].append(item)

        if item["data_vencimento"]:
            if not grupo["desde_data"] or item["data_vencimento"] < grupo["desde_data"]:
                grupo["desde_data"] = item["data_vencimento"]
                grupo["desde_label"] = item["competencia"]

        grupo["maior_atraso"] = max(grupo["maior_atraso"], item["dias_atraso"] or 0)

    grupos = []

    for grupo in grupos_map.values():
        grupo["historico"] = sorted(
            grupo["historico"],
            key=lambda x: (x["data_vencimento"] or date.max, x["id"])
        )

        if grupo["historico"]:
            grupo["desde_label"] = grupo["historico"][0]["competencia"]

        grupo["total_formatado"] = radar_moeda(grupo["total"])
        atrasos = [h["dias_atraso"] for h in grupo["historico"] if h["dias_atraso"]]
        grupo["atraso_medio"] = round(sum(atrasos) / len(atrasos)) if atrasos else 0
        grupos.append(grupo)

    return sorted(
        grupos,
        key=lambda g: (g["desde_data"] or date.max, -g["total"])
    )


def radar_somar_itens(lista):
    return sum(dinheiro(item.get("valor")) for item in lista)


def radar_somar_grupos(lista):
    return sum(dinheiro(item.get("total")) for item in lista)


def radar_classificar_risco(pressao, receitas_previstas):
    pressao = dinheiro(pressao)
    receitas_previstas = dinheiro(receitas_previstas)

    if pressao <= 0:
        return "CONTROLADO", "controlado"

    if receitas_previstas <= 0:
        return "ATENÇÃO", "atencao"

    percentual = (pressao / receitas_previstas) * 100

    if percentual <= 50:
        return "CONTROLADO", "controlado"

    if percentual <= 80:
        return "ATENÇÃO", "atencao"

    if percentual <= 100:
        return "ALTO RISCO", "alto-risco"

    return "CRÍTICO", "critico"


def radar_recomendacao(total_divida_herdada, total_proximos, diferenca):
    if total_divida_herdada > 0:
        return "Priorize pagar os meses mais antigos das dívidas herdadas para cortar a bola de neve."

    if diferenca < 0:
        return "A pressão do mês está acima das entradas previstas. Revise despesas e renegocie vencimentos."

    if total_proximos > 0:
        return "Organize o caixa para cobrir os próximos vencimentos sem atrasar novas contas."

    return "Cenário saudável. Continue mantendo as obrigações em dia."


def radar_insight(total_divida_herdada, grupos_herdados, total_pagas_antigas):
    qtd_grupos = len(grupos_herdados)

    if total_divida_herdada > 0:
        return (
            f"Você possui {radar_moeda(total_divida_herdada)} em dívidas herdadas "
            f"agrupadas em {qtd_grupos} tipo(s). Pague os meses em ordem para colocar as contas em dia."
        )

    if total_pagas_antigas > 0:
        return (
            f"Você já pagou {radar_moeda(total_pagas_antigas)} de meses anteriores neste mês. "
            "Isso ajuda a limpar o histórico e reduzir a pressão futura."
        )

    return "Nenhuma dívida herdada aberta encontrada para este período. O fluxo está mais limpo."


def radar_receitas_realizadas_mes(mes, ano):
    inicio_dt = inicio_mes_datetime(mes, ano)
    fim_dt = fim_mes_datetime(mes, ano)

    total = 0

    contas_receber = ContaReceberImportada.query.filter(
        ContaReceberImportada.pago == True,
        ContaReceberImportada.origem_importacao == "RECEBIMENTO",
        ContaReceberImportada.data_pagamento >= inicio_dt,
        ContaReceberImportada.data_pagamento <= fim_dt
    ).all()

    for conta in contas_receber:
        total += valor_conta_receber(conta)

    lancamentos = LancamentoFinanceiro.query.filter(
        LancamentoFinanceiro.tipo == "RECEITA",
        LancamentoFinanceiro.mes == mes,
        LancamentoFinanceiro.ano == ano
    ).all()

    for lancamento in lancamentos:
        if status_pago(lancamento.status):
            total += dinheiro(lancamento.valor)

    return total


@gestao_bp.route("/radar-financeiro/")
@gestao_required
def radar_financeiro():

    hoje = date.today()

    mes = request.args.get("mes", type=int) or hoje.month
    ano = request.args.get("ano", type=int) or hoje.year
    setor = request.args.get("setor", "").strip().upper()
    busca = request.args.get("busca", "").strip()
    visao = request.args.get("visao", "vencimento").strip().lower()
    grupo_key = request.args.get("grupo", "").strip()

    if mes < 1 or mes > 12:
        mes = hoje.month

    inicio_mes = primeiro_dia_mes(mes, ano)
    fim_mes = ultimo_dia_mes(mes, ano)
    inicio_dt = inicio_mes_datetime(mes, ano)
    fim_dt = fim_mes_datetime(mes, ano)

    # Gera automaticamente as obrigações recorrentes até o mês visualizado.
    # Assim, se uma conta recorrente nasceu em março e você abre junho,
    # março, abril, maio e junho serão criados se ainda não existirem.
    radar_gerar_recorrencias_ate_mes(mes, ano)

    query = ContaPagarImportada.query.filter(
        ContaPagarImportada.origem_importacao.in_(["PAGAMENTO", "MANUAL", "VENCIMENTO", "IMPORTACAO", "RECORRENTE"])
    )

    if setor:
        query = query.filter(
            ContaPagarImportada.setor.ilike(f"%{setor}%")
        )

    contas_base = query.order_by(
        ContaPagarImportada.data_vencimento.asc().nullslast(),
        ContaPagarImportada.id.asc()
    ).all()

    contas_base = radar_filtrar_busca(contas_base, busca)

    contas_abertas = [
        c for c in contas_base
        if radar_conta_aberta(c)
    ]

    contas_pagas = [
        c for c in contas_base
        if conta_esta_paga(c)
    ]

    # =====================================================
    # HERDADAS
    # Contas abertas que nasceram/venceram antes do mês filtrado.
    # Cada conta mantém sua própria data, e a coluna agrupa por tipo.
    # =====================================================
    contas_herdadas = [
        c for c in contas_abertas
        if data_para_date(c.data_vencimento)
        and data_para_date(c.data_vencimento) < inicio_mes
    ]

    grupos_herdados = radar_agrupar_herdadas(contas_herdadas, hoje)

    # =====================================================
    # FLUXO NORMAL DO MÊS
    # Aqui não entram as herdadas, para não duplicar no radar.
    # =====================================================
    abertas_mes = [
        c for c in contas_abertas
        if data_para_date(c.data_vencimento)
        and inicio_mes <= data_para_date(c.data_vencimento) <= fim_mes
    ]

    vence_hoje = []
    proximos_7 = []
    ate_fim_mes = []
    atrasadas_mes = []

    for conta in abertas_mes:
        data_venc = data_para_date(conta.data_vencimento)

        if not data_venc:
            continue

        item = radar_item_conta(conta, hoje)

        if data_venc < hoje:
            atrasadas_mes.append(item)
        elif data_venc == hoje:
            vence_hoje.append(item)
        elif data_venc <= hoje + timedelta(days=7):
            proximos_7.append(item)
        else:
            ate_fim_mes.append(item)

    pagas_mes_contas = [
        c for c in contas_pagas
        if data_para_date(c.data_pagamento)
        and inicio_mes <= data_para_date(c.data_pagamento) <= fim_mes
        and (
            not data_para_date(c.data_vencimento)
            or data_para_date(c.data_vencimento) >= inicio_mes
        )
    ]

    pagas_antigas_contas = [
        c for c in contas_pagas
        if data_para_date(c.data_pagamento)
        and inicio_mes <= data_para_date(c.data_pagamento) <= fim_mes
        and data_para_date(c.data_vencimento)
        and data_para_date(c.data_vencimento) < inicio_mes
    ]

    pagas_mes = [
        radar_item_conta(c, hoje)
        for c in sorted(
            pagas_mes_contas,
            key=lambda conta: (data_para_date(conta.data_pagamento) or date.max, conta.id)
        )
    ]

    pagas_meses_anteriores = [
        radar_item_conta(c, hoje)
        for c in sorted(
            pagas_antigas_contas,
            key=lambda conta: (data_para_date(conta.data_pagamento) or date.max, conta.id)
        )
    ]

    total_divida_herdada = radar_somar_grupos(grupos_herdados)
    total_atrasadas_mes = radar_somar_itens(atrasadas_mes)
    total_hoje = radar_somar_itens(vence_hoje)
    total_proximos_7 = radar_somar_itens(proximos_7)
    total_ate_fim_mes = radar_somar_itens(ate_fim_mes)
    total_pagas_mes = radar_somar_itens(pagas_mes)
    total_pagas_meses_anteriores = radar_somar_itens(pagas_meses_anteriores)

    receitas_realizadas = radar_receitas_realizadas_mes(mes, ano)

    # Receita prevista simples: realizado + contas a receber abertas até fim do mês.
    receitas_previstas = receitas_realizadas
    contas_receber_abertas = ContaReceberImportada.query.filter(
        ContaReceberImportada.pago == False,
        ContaReceberImportada.origem_importacao == "RECEBIMENTO",
        ContaReceberImportada.data_vencimento <= fim_dt
    ).all()

    for conta_receber in contas_receber_abertas:
        receitas_previstas += valor_conta_receber(conta_receber)

    pressao_imediata = (
        total_divida_herdada
        + total_atrasadas_mes
        + total_hoje
        + total_proximos_7
    )

    diferenca_estimada = receitas_previstas - pressao_imediata
    resultado_parcial = receitas_realizadas - (total_pagas_mes + total_pagas_meses_anteriores)

    risco, risco_classe = radar_classificar_risco(
        pressao=pressao_imediata,
        receitas_previstas=receitas_previstas
    )

    recomendacao = radar_recomendacao(
        total_divida_herdada=total_divida_herdada,
        total_proximos=total_proximos_7,
        diferenca=diferenca_estimada
    )

    insight = radar_insight(
        total_divida_herdada=total_divida_herdada,
        grupos_herdados=grupos_herdados,
        total_pagas_antigas=total_pagas_meses_anteriores
    )

    grupo_selecionado = None

    if grupo_key:
        for grupo in grupos_herdados:
            if grupo["grupo_key"] == grupo_key:
                grupo_selecionado = grupo
                break

    if not grupo_selecionado and grupos_herdados:
        grupo_selecionado = grupos_herdados[0]

    top_despesas = []

    despesas_counter = Counter()

    for item in pagas_mes + pagas_meses_anteriores:
        despesas_counter[item["descricao"]] += item["valor"]

    for nome, valor in despesas_counter.most_common(5):
        percentual = 0
        total_pago_geral = total_pagas_mes + total_pagas_meses_anteriores

        if total_pago_geral:
            percentual = (dinheiro(valor) / total_pago_geral) * 100

        top_despesas.append({
            "nome": nome,
            "valor": valor,
            "valor_formatado": radar_moeda(valor),
            "percentual": percentual,
        })

    colunas = [
        {
            "slug": "herdada",
            "titulo": "DÍVIDA HERDADA",
            "subtitulo": "Contas de meses anteriores não pagas",
            "cor": "danger",
            "total": total_divida_herdada,
            "total_formatado": radar_moeda(total_divida_herdada),
            "badge": sum(g["qtd"] for g in grupos_herdados),
            "grupos": grupos_herdados,
            "vazia": "Sem dívidas herdadas",
        },
        {
            "slug": "hoje",
            "titulo": "VENCE HOJE",
            "subtitulo": f"Vencem hoje ({hoje.strftime('%d/%m/%Y')})",
            "cor": "warning",
            "total": total_hoje,
            "total_formatado": radar_moeda(total_hoje),
            "badge": len(vence_hoje),
            "itens": vence_hoje,
            "vazia": "Sem contas para hoje",
        },
        {
            "slug": "proximos",
            "titulo": "PRÓXIMOS 7 DIAS",
            "subtitulo": "Pressão imediata do caixa",
            "cor": "purple",
            "total": total_proximos_7,
            "total_formatado": radar_moeda(total_proximos_7),
            "badge": len(proximos_7),
            "itens": proximos_7,
            "vazia": "Sem vencimentos próximos",
        },
        {
            "slug": "fim_mes",
            "titulo": "ATÉ FIM DO MÊS",
            "subtitulo": f"Vencem até {fim_mes.strftime('%d/%m')}",
            "cor": "blue",
            "total": total_ate_fim_mes,
            "total_formatado": radar_moeda(total_ate_fim_mes),
            "badge": len(ate_fim_mes),
            "itens": ate_fim_mes,
            "vazia": "Sem contas até fim do mês",
        },
        {
            "slug": "pagas_mes",
            "titulo": "PAGAS NO MÊS",
            "subtitulo": f"Pagas em {radar_nome_mes(mes)}",
            "cor": "success",
            "total": total_pagas_mes,
            "total_formatado": radar_moeda(total_pagas_mes),
            "badge": len(pagas_mes),
            "itens": pagas_mes,
            "vazia": "Sem contas pagas no mês",
        },
        {
            "slug": "pagas_antigas",
            "titulo": "PAGAS DE MESES ANT.",
            "subtitulo": "Dívidas antigas pagas agora",
            "cor": "teal",
            "total": total_pagas_meses_anteriores,
            "total_formatado": radar_moeda(total_pagas_meses_anteriores),
            "badge": len(pagas_meses_anteriores),
            "itens": pagas_meses_anteriores,
            "vazia": "Sem dívidas antigas pagas",
        },
    ]

    return render_template(
        "gestao/radar_financeiro.html",
        hoje=hoje,
        mes=mes,
        ano=ano,
        setor=setor,
        busca=busca,
        visao=visao,
        grupo_key=grupo_key,

        moeda=radar_moeda,
        nome_mes=radar_nome_mes,
        nome_mes_curto=radar_nome_mes_curto,

        colunas=colunas,
        grupos_herdados=grupos_herdados,
        grupo_selecionado=grupo_selecionado,

        total_divida_herdada=total_divida_herdada,
        total_atrasadas_mes=total_atrasadas_mes,
        total_hoje=total_hoje,
        total_proximos_7=total_proximos_7,
        total_ate_fim_mes=total_ate_fim_mes,
        total_pagas_mes=total_pagas_mes,
        total_pagas_meses_anteriores=total_pagas_meses_anteriores,

        receitas_realizadas=receitas_realizadas,
        receitas_previstas=receitas_previstas,
        pressao_imediata=pressao_imediata,
        diferenca_estimada=diferenca_estimada,
        resultado_parcial=resultado_parcial,
        risco=risco,
        risco_classe=risco_classe,
        recomendacao=recomendacao,
        insight=insight,
        top_despesas=top_despesas,
    )


@gestao_bp.route("/radar-financeiro/novo", methods=["POST"])
@gestao_required
def radar_financeiro_novo():

    descricao = request.form.get("descricao", "").strip()
    fornecedor = request.form.get("fornecedor", "").strip()
    categoria = request.form.get("categoria", "").strip()
    setor = normalizar_texto(request.form.get("setor")) or "GERAL"
    valor = dinheiro(
        str(request.form.get("valor") or "0")
        .replace(".", "")
        .replace(",", ".")
    )
    data_vencimento = parse_data(request.form.get("data_vencimento"))
    observacoes = request.form.get("observacoes", "").strip()

    if not descricao:
        flash("Informe a descrição da conta.", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")

    if not data_vencimento:
        flash("Informe a data de vencimento.", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")

    recorrente = request.form.get("recorrente") == "on"
    recorrencia = None

    if recorrente:
        recorrencia = ContaRecorrente(
            descricao=descricao,
            fornecedor_funcionario=fornecedor,
            plano_contas=descricao,
            categoria=categoria,
            setor=setor,
            valor=valor,
            dia_vencimento=data_vencimento.day,
            data_inicio=data_vencimento,
            ativo=True,
            observacoes=observacoes,
        )

        db.session.add(recorrencia)
        db.session.flush()

    chave_conciliacao = None
    origem_importacao = "PAGAMENTO"

    if recorrencia:
        chave_conciliacao = radar_chave_recorrente(
            recorrencia_id=recorrencia.id,
            mes=data_vencimento.month,
            ano=data_vencimento.year
        )
        origem_importacao = "RECORRENTE"

    observacoes_conta = observacoes

    if recorrencia:
        observacoes_conta = (
            f"Conta gerada pela recorrência #{recorrencia.id}. "
            f"Competência: {radar_competencia_label(data_vencimento)}.\n"
            f"{observacoes or ''}"
        ).strip()

    conta = ContaPagarImportada(
        numero_fatura=request.form.get("numero_fatura") or (f"REC-{recorrencia.id}-{data_vencimento.month:02d}-{data_vencimento.year}" if recorrencia else None),
        fornecedor_funcionario=fornecedor,
        plano_contas=descricao,
        categoria=categoria,
        setor=setor,
        data_documento=datetime.combine(date.today(), datetime.min.time()),
        data_vencimento=datetime.combine(data_vencimento, datetime.min.time()),
        valor=valor,
        pago=False,
        status="PENDENTE",
        observacoes=observacoes_conta,
        mes=data_vencimento.month,
        ano=data_vencimento.year,
        chave_conciliacao=chave_conciliacao,
        origem_importacao=origem_importacao,
    )

    if request.form.get("ja_pago") == "on":
        data_pagamento = parse_data(request.form.get("data_pagamento")) or date.today()
        conta.pago = True
        conta.status = "PAGO"
        conta.data_pagamento = datetime.combine(data_pagamento, datetime.min.time())

    db.session.add(conta)
    db.session.commit()

    if recorrencia:
        flash("Conta cadastrada e recorrência mensal criada. Os próximos meses serão gerados automaticamente.", "success")
    else:
        flash("Conta cadastrada no Radar Financeiro.", "success")

    return redirect(request.referrer or "/gestao/radar-financeiro/")


@gestao_bp.route("/radar-financeiro/editar/<int:id>", methods=["POST"])
@gestao_required
def radar_financeiro_editar(id):

    conta = ContaPagarImportada.query.get_or_404(id)

    descricao = request.form.get("descricao", "").strip()
    fornecedor = request.form.get("fornecedor", "").strip()
    categoria = request.form.get("categoria", "").strip()
    setor = normalizar_texto(request.form.get("setor")) or "GERAL"
    status = normalizar_texto(request.form.get("status")) or "PENDENTE"
    valor = dinheiro(
        str(request.form.get("valor") or "0")
        .replace(".", "")
        .replace(",", ".")
    )
    data_vencimento = parse_data(request.form.get("data_vencimento"))
    data_pagamento = parse_data(request.form.get("data_pagamento"))
    observacoes = request.form.get("observacoes", "").strip()

    if not descricao:
        flash("Informe a descrição da conta.", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")

    conta.plano_contas = descricao
    conta.fornecedor_funcionario = fornecedor
    conta.categoria = categoria
    conta.setor = setor
    conta.valor = valor
    conta.status = status
    conta.observacoes = observacoes

    if data_vencimento:
        conta.data_vencimento = datetime.combine(data_vencimento, datetime.min.time())
        conta.mes = data_vencimento.month
        conta.ano = data_vencimento.year

    if status == "PAGO":
        conta.pago = True
        conta.data_pagamento = datetime.combine(
            data_pagamento or date.today(),
            datetime.min.time()
        )
    else:
        conta.pago = False
        if data_pagamento:
            conta.data_pagamento = datetime.combine(data_pagamento, datetime.min.time())
        else:
            conta.data_pagamento = None

    db.session.commit()

    flash("Conta atualizada com sucesso.", "success")

    return redirect(request.referrer or "/gestao/radar-financeiro/")


@gestao_bp.route("/radar-financeiro/pagar/<int:id>", methods=["POST"])
@gestao_required
def radar_financeiro_pagar(id):

    conta = ContaPagarImportada.query.get_or_404(id)

    data_pagamento = parse_data(request.form.get("data_pagamento")) or date.today()

    conta.pago = True
    conta.status = "PAGO"
    conta.data_pagamento = datetime.combine(
        data_pagamento,
        datetime.min.time()
    )

    observacao_extra = request.form.get("observacao", "").strip()

    if observacao_extra:
        observacao_antiga = conta.observacoes or ""
        conta.observacoes = f"{observacao_antiga}\nPagamento: {observacao_extra}".strip()

    db.session.commit()

    flash("Conta marcada como paga. Se ela era herdada, agora aparecerá em Pagas de Meses Anteriores.", "success")

    return redirect(request.referrer or "/gestao/radar-financeiro/")


@gestao_bp.route("/radar-financeiro/cancelar/<int:id>", methods=["POST"])
@gestao_required
def radar_financeiro_cancelar(id):

    conta = ContaPagarImportada.query.get_or_404(id)

    conta.status = "CANCELADO"
    conta.pago = False

    db.session.commit()

    flash("Conta cancelada no Radar Financeiro.", "success")

    return redirect(request.referrer or "/gestao/radar-financeiro/")


@gestao_bp.route("/radar-financeiro/excluir/<int:id>", methods=["POST"])
@gestao_required
def radar_financeiro_excluir(id):

    conta = ContaPagarImportada.query.get_or_404(id)

    db.session.delete(conta)
    db.session.commit()

    flash("Conta excluída definitivamente.", "success")

    return redirect(request.referrer or "/gestao/radar-financeiro/")


@gestao_bp.route("/radar-financeiro/transportar/<int:id>", methods=["POST"])
@gestao_required
def radar_financeiro_transportar(id):

    conta = ContaPagarImportada.query.get_or_404(id)

    mes_destino = request.form.get("mes_destino", type=int)
    ano_destino = request.form.get("ano_destino", type=int)

    if not mes_destino or not ano_destino:
        flash("Informe mês e ano de destino.", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")

    data_vencimento_atual = data_para_date(conta.data_vencimento) or date.today()
    dia = min(data_vencimento_atual.day, calendar.monthrange(ano_destino, mes_destino)[1])
    nova_data = date(ano_destino, mes_destino, dia)

    observacao_origem = (
        f"Conta criada por transporte de {radar_competencia_label(data_vencimento_atual)}. "
        f"Vencimento original: {radar_data_br(data_vencimento_atual)}."
    )

    nova_conta = ContaPagarImportada(
        numero_fatura=conta.numero_fatura,
        fornecedor_funcionario=conta.fornecedor_funcionario,
        plano_contas=conta.plano_contas,
        categoria=conta.categoria,
        setor=conta.setor,
        data_documento=datetime.combine(date.today(), datetime.min.time()),
        data_vencimento=datetime.combine(nova_data, datetime.min.time()),
        valor=conta.valor,
        pago=False,
        status="PENDENTE",
        observacoes=f"{observacao_origem}\n{conta.observacoes or ''}".strip(),
        mes=mes_destino,
        ano=ano_destino,
        chave_conciliacao=None,
        origem_importacao="PAGAMENTO",
    )

    observacao_antiga = conta.observacoes or ""
    conta.status = "TRANSPORTADO"
    conta.observacoes = (
        f"{observacao_antiga}\n"
        f"Transportada para {radar_nome_mes(mes_destino)}/{ano_destino} em {date.today().strftime('%d/%m/%Y')}."
    ).strip()

    db.session.add(nova_conta)
    db.session.commit()

    flash("Conta transportada mantendo histórico no mês original e criando nova obrigação no destino.", "success")

    return redirect(request.referrer or "/gestao/radar-financeiro/")


@gestao_bp.route("/radar-financeiro/transportar-pagas-lote", methods=["POST"])
@gestao_required
def radar_financeiro_transportar_pagas_lote():

    ids = request.form.getlist("contas_ids")
    mes_destino = request.form.get("mes_destino", type=int)
    ano_destino = request.form.get("ano_destino", type=int)

    if not ids:
        flash("Selecione ao menos uma conta paga para transportar.", "warning")
        return redirect(request.referrer or "/gestao/radar-financeiro/")

    if not mes_destino or not ano_destino:
        flash("Informe mês e ano de destino.", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro/")

    total = 0

    for id_conta in ids:
        conta = ContaPagarImportada.query.get(id_conta)

        if not conta:
            continue

        data_vencimento_atual = data_para_date(conta.data_vencimento) or date.today()
        dia = min(data_vencimento_atual.day, calendar.monthrange(ano_destino, mes_destino)[1])
        nova_data = date(ano_destino, mes_destino, dia)

        nova_conta = ContaPagarImportada(
            numero_fatura=conta.numero_fatura,
            fornecedor_funcionario=conta.fornecedor_funcionario,
            plano_contas=conta.plano_contas,
            categoria=conta.categoria,
            setor=conta.setor,
            data_documento=datetime.combine(date.today(), datetime.min.time()),
            data_vencimento=datetime.combine(nova_data, datetime.min.time()),
            valor=conta.valor,
            pago=False,
            status="PENDENTE",
            observacoes=(
                f"Conta transportada em lote a partir de {radar_competencia_label(data_vencimento_atual)}. "
                f"Vencimento original: {radar_data_br(data_vencimento_atual)}."
            ),
            mes=mes_destino,
            ano=ano_destino,
            chave_conciliacao=None,
            origem_importacao="PAGAMENTO",
        )

        db.session.add(nova_conta)
        total += 1

    db.session.commit()

    flash(f"{total} conta(s) transportada(s) para {radar_nome_mes(mes_destino)}/{ano_destino}.", "success")

    return redirect(request.referrer or "/gestao/radar-financeiro/")
