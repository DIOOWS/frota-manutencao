from flask import Blueprint, render_template, request, redirect, session, jsonify
from models.manutencao import Manutencao
from models.usuario import Usuario
from collections import Counter
from datetime import datetime
import os

from utils.assistente_intencoes import detectar_intencao


assistente_bp = Blueprint("assistente", __name__, url_prefix="/assistente")


# ==========================================
# 🔧 HELPERS
# ==========================================
def formatar_data(data):
    if not data:
        return "-"
    return data.strftime("%d/%m/%Y")


def formatar_frota(valor):
    try:
        return str(int(float(valor)))
    except:
        return str(valor or "SEM FROTA")


def texto(valor):
    return (valor or "").upper().strip()


def eh_corretiva(registro):
    return texto(registro.tipo_servico) == "CORRETIVA"


def eh_preventiva(registro):
    return texto(registro.tipo_servico) == "PREVENTIVA"


def obter_nome_usuario():
    nomes_sessao = [
        "user_nome",
        "user_name",
        "nome",
        "usuario_nome",
        "username"
    ]

    for chave in nomes_sessao:
        valor = session.get(chave)
        if valor:
            return valor

    user_id = session.get("user_id")

    if user_id:
        try:
            usuario = Usuario.query.get(user_id)
            if usuario and usuario.nome:
                return usuario.nome
        except Exception as e:
            print("Erro ao buscar usuário para o Sidinho:", e)

    return "usuário"


# ==========================================
# 🤖 SIDINHO / IDENTIDADE
# ==========================================
def resposta_quem_e_sidinho():
    nome_usuario = obter_nome_usuario()

    return f"""
Olá, {nome_usuario}! Eu sou o Sidinho, seu assistente inteligente do sistema de manutenção de frota.

Eu posso te ajudar a consultar e analisar informações como:

• Quantidade de frotas cadastradas
• Total de manutenções
• OS em andamento
• Frotas com mais corretivas
• Frotas com maior TMA
• Principais causas de manutenção
• Últimas finalizações
• Histórico de uma frota específica
• Preventivas e corretivas
• Clientes mais atendidos
• Atendimentos internos e externos
• Manutenções sem data de saída

Por enquanto, eu sou um assistente consultivo: eu analiso os dados do sistema e respondo perguntas, mas não altero, excluo nem cadastro informações.
""".strip()


# ==========================================
# 🔎 CONSULTAS CONTROLADAS
# ==========================================
def buscar_resumo_geral():
    registros = Manutencao.query.all()

    total = len(registros)

    corretivas = sum(1 for r in registros if eh_corretiva(r))
    preventivas = sum(1 for r in registros if eh_preventiva(r))

    andamento = sum(
        1 for r in registros
        if "ANDAMENTO" in texto(r.status)
    )

    finalizadas = sum(
        1 for r in registros
        if "FINALIZADO" in texto(r.status)
    )

    registros_com_tma = [
        r.dtm for r in registros
        if r.dtm is not None
    ]

    tma_medio = round(
        sum(registros_com_tma) / len(registros_com_tma),
        1
    ) if registros_com_tma else 0

    causas = Counter(
        texto(r.causa) if texto(r.causa) else "SEM CAUSA"
        for r in registros
    )

    principal_causa = causas.most_common(1)[0] if causas else ("SEM CAUSA", 0)

    return {
        "total": total,
        "corretivas": corretivas,
        "preventivas": preventivas,
        "andamento": andamento,
        "finalizadas": finalizadas,
        "tma_medio": tma_medio,
        "principal_causa": principal_causa,
    }


def buscar_total_frotas():
    registros = Manutencao.query.with_entities(Manutencao.numero_frota).all()

    frotas = set()

    for r in registros:
        frota = formatar_frota(r.numero_frota)
        if frota and frota != "SEM FROTA":
            frotas.add(frota)

    frotas_ordenadas = sorted(
        frotas,
        key=lambda x: int(x) if str(x).isdigit() else 0
    )

    return len(frotas_ordenadas), frotas_ordenadas


def buscar_os_em_andamento():
    return Manutencao.query.filter(
        Manutencao.status.ilike("%ANDAMENTO%")
    ).order_by(
        Manutencao.data.desc().nullslast()
    ).limit(10).all()


def buscar_finalizadas():
    return Manutencao.query.filter(
        Manutencao.status.ilike("%FINALIZADO%")
    ).order_by(
        Manutencao.data_saida.desc().nullslast(),
        Manutencao.id.desc()
    ).limit(15).all()


def buscar_sem_data_saida():
    return Manutencao.query.filter(
        Manutencao.data_saida.is_(None)
    ).order_by(
        Manutencao.data.desc().nullslast()
    ).limit(15).all()


def buscar_maiores_tma():
    return Manutencao.query.filter(
        Manutencao.dtm.isnot(None)
    ).order_by(
        Manutencao.dtm.desc()
    ).limit(10).all()


def buscar_principais_causas():
    registros = Manutencao.query.all()

    causas = Counter(
        texto(r.causa) if texto(r.causa) else "SEM CAUSA"
        for r in registros
    )

    return causas.most_common(10)


def buscar_ultimas_finalizacoes():
    return Manutencao.query.filter(
        Manutencao.status.ilike("%FINALIZADO%"),
        Manutencao.data_saida.isnot(None)
    ).order_by(
        Manutencao.data_saida.desc(),
        Manutencao.id.desc()
    ).limit(10).all()


def buscar_historico_frota(pergunta):
    palavras = pergunta.replace(",", " ").replace(".", " ").split()

    frota_busca = None

    for p in palavras:
        if p.isdigit():
            frota_busca = p
            break

    if not frota_busca:
        return None, []

    registros = [
        r for r in Manutencao.query.all()
        if formatar_frota(r.numero_frota) == frota_busca
    ]

    registros = sorted(
        registros,
        key=lambda r: r.data or datetime.min.date(),
        reverse=True
    )[:10]

    return frota_busca, registros


def buscar_frotas_por_tipo_servico(tipo_servico):
    registros = Manutencao.query.all()
    contador = Counter()

    for r in registros:
        if texto(r.tipo_servico) == tipo_servico:
            frota = formatar_frota(r.numero_frota)
            contador[frota] += 1

    return contador.most_common(10)


def buscar_frotas_mais_atendidas():
    registros = Manutencao.query.all()
    contador = Counter()

    for r in registros:
        frota = formatar_frota(r.numero_frota)
        contador[frota] += 1

    return contador.most_common(10)


def buscar_frotas_maior_tma():
    registros = Manutencao.query.filter(
        Manutencao.dtm.isnot(None)
    ).all()

    soma_tma = {}
    qtd = {}

    for r in registros:
        frota = formatar_frota(r.numero_frota)

        soma_tma[frota] = soma_tma.get(frota, 0) + r.dtm
        qtd[frota] = qtd.get(frota, 0) + 1

    ranking = []

    for frota, total_tma in soma_tma.items():
        media = round(total_tma / qtd[frota], 1)
        ranking.append((frota, media, qtd[frota]))

    return sorted(
        ranking,
        key=lambda x: x[1],
        reverse=True
    )[:10]


def buscar_clientes_mais_atendidos():
    registros = Manutencao.query.all()
    contador = Counter()

    for r in registros:
        cliente = texto(r.cliente) if texto(r.cliente) else "SEM CLIENTE"
        contador[cliente] += 1

    return contador.most_common(10)


def buscar_tipo_atendimento():
    registros = Manutencao.query.all()
    contador = Counter()

    for r in registros:
        atendimento = texto(r.tipo_atendimento) if texto(r.tipo_atendimento) else "SEM INFO"
        contador[atendimento] += 1

    return contador.most_common(10)


# ==========================================
# 🧠 RESPOSTAS
# ==========================================
def resposta_total_frotas():
    total, frotas = buscar_total_frotas()

    if total == 0:
        return "Ainda não encontrei frotas cadastradas no sistema."

    lista = ", ".join(frotas[:30])

    if total > 30:
        lista += f"... e mais {total - 30} frota(s)."

    return f"""
Temos {total} frota(s) cadastrada(s) no sistema.

Frotas identificadas:
{lista}
""".strip()


def resposta_total_manutencoes():
    total = Manutencao.query.count()

    return f"Temos {total} manutenção(ões) registrada(s) no sistema."


def resposta_total_clientes():
    try:
        from models.cliente import Cliente
        total = Cliente.query.count()
        return f"Temos {total} cliente(s) cadastrado(s) no sistema."
    except Exception:
        registros = Manutencao.query.with_entities(Manutencao.cliente).all()

        clientes = set()

        for r in registros:
            cliente = texto(r.cliente)
            if cliente and cliente != "SEM CLIENTE":
                clientes.add(cliente)

        return f"Temos {len(clientes)} cliente(s) identificado(s) nas manutenções."


def resposta_resumo_geral():
    resumo = buscar_resumo_geral()

    total_frotas, _ = buscar_total_frotas()

    return f"""
Resumo geral do sistema:

• Total de frotas: {total_frotas}
• Total de manutenções: {resumo['total']}
• Preventivas: {resumo['preventivas']}
• Corretivas: {resumo['corretivas']}
• Em andamento: {resumo['andamento']}
• Finalizadas: {resumo['finalizadas']}
• TMA médio: {resumo['tma_medio']} dias
• Principal causa: {resumo['principal_causa'][0]} ({resumo['principal_causa'][1]} ocorrência(s))

Esse resumo considera todos os registros cadastrados no sistema.
""".strip()


def resposta_os_em_andamento():
    registros = buscar_os_em_andamento()

    if not registros:
        return "Não encontrei nenhuma OS em andamento no momento."

    linhas = ["OS em andamento encontradas:\n"]

    for r in registros:
        linhas.append(
            f"• OS {r.os or '-'} — Frota {formatar_frota(r.numero_frota)} — "
            f"Entrada {formatar_data(r.data)} — Serviço {r.tipo_servico or '-'} — "
            f"Causa {r.causa or '-'}"
        )

    return "\n".join(linhas)


def resposta_finalizadas():
    registros = buscar_finalizadas()

    if not registros:
        return "Não encontrei manutenções finalizadas cadastradas."

    linhas = ["Manutenções finalizadas:\n"]

    for r in registros:
        linhas.append(
            f"• OS {r.os or '-'} — Frota {formatar_frota(r.numero_frota)} — "
            f"Saída {formatar_data(r.data_saida)} — "
            f"TMA {r.dtm if r.dtm is not None else '-'} dia(s)"
        )

    return "\n".join(linhas)


def resposta_sem_data_saida():
    registros = buscar_sem_data_saida()

    if not registros:
        return "Não encontrei manutenções sem data de saída."

    linhas = ["Manutenções sem data de saída:\n"]

    for r in registros:
        linhas.append(
            f"• OS {r.os or '-'} — Frota {formatar_frota(r.numero_frota)} — "
            f"Entrada {formatar_data(r.data)} — Status {r.status or '-'} — "
            f"Serviço {r.tipo_servico or '-'}"
        )

    return "\n".join(linhas)


def resposta_maiores_tma():
    registros = buscar_maiores_tma()

    if not registros:
        return "Não encontrei registros com TMA preenchido."

    linhas = ["Manutenções com maior TMA:\n"]

    for i, r in enumerate(registros, start=1):
        linhas.append(
            f"{i}º Frota {formatar_frota(r.numero_frota)} — "
            f"OS {r.os or '-'} — TMA {r.dtm} dia(s) — "
            f"Entrada {formatar_data(r.data)} — Saída {formatar_data(r.data_saida)}"
        )

    return "\n".join(linhas)


def resposta_frotas_maior_tma():
    ranking = buscar_frotas_maior_tma()

    if not ranking:
        return "Não encontrei dados suficientes para calcular o TMA por frota."

    linhas = ["Frotas com maior TMA médio:\n"]

    for i, (frota, media, qtd) in enumerate(ranking, start=1):
        linhas.append(
            f"{i}º Frota {frota} — TMA médio {media} dia(s) — "
            f"{qtd} manutenção(ões)"
        )

    return "\n".join(linhas)


def resposta_principais_causas():
    causas = buscar_principais_causas()

    if not causas:
        return "Não encontrei causas cadastradas."

    linhas = ["Principais causas de manutenção:\n"]

    for i, (causa, qtd) in enumerate(causas, start=1):
        linhas.append(
            f"{i}º {causa} — {qtd} ocorrência(s)"
        )

    return "\n".join(linhas)


def resposta_ultimas_finalizacoes():
    registros = buscar_ultimas_finalizacoes()

    if not registros:
        return "Não encontrei manutenções finalizadas com data de saída."

    linhas = ["Últimas finalizações:\n"]

    for r in registros:
        linhas.append(
            f"• OS {r.os or '-'} — Frota {formatar_frota(r.numero_frota)} — "
            f"Finalizado em {formatar_data(r.data_saida)} — "
            f"TMA {r.dtm if r.dtm is not None else '-'} dia(s)"
        )

    return "\n".join(linhas)


def resposta_historico_frota(pergunta):
    frota, registros = buscar_historico_frota(pergunta)

    if not frota:
        return "Me informe o número da frota. Exemplo: histórico da frota 398."

    if not registros:
        return f"Não encontrei manutenções para a frota {frota}."

    linhas = [f"Histórico recente da frota {frota}:\n"]

    for r in registros:
        linhas.append(
            f"• OS {r.os or '-'} — "
            f"Entrada {formatar_data(r.data)} — "
            f"Saída {formatar_data(r.data_saida)} — "
            f"Status {r.status or '-'} — "
            f"Serviço {r.tipo_servico or '-'} — "
            f"Causa {r.causa or '-'} — "
            f"TMA {r.dtm if r.dtm is not None else '-'}"
        )

    return "\n".join(linhas)


def resposta_frota_mais_corretiva():
    ranking = buscar_frotas_por_tipo_servico("CORRETIVA")

    if not ranking:
        return "Não encontrei manutenções corretivas cadastradas."

    linhas = ["Frotas com mais manutenções corretivas:\n"]

    for i, (frota, qtd) in enumerate(ranking, start=1):
        linhas.append(
            f"{i}º Frota {frota} — {qtd} corretiva(s)"
        )

    primeira_frota, primeira_qtd = ranking[0]

    linhas.append(
        f"\nA frota com mais corretivas é a frota {primeira_frota}, "
        f"com {primeira_qtd} ocorrência(s)."
    )

    return "\n".join(linhas)


def resposta_frota_mais_preventiva():
    ranking = buscar_frotas_por_tipo_servico("PREVENTIVA")

    if not ranking:
        return "Não encontrei manutenções preventivas cadastradas."

    linhas = ["Frotas com mais manutenções preventivas:\n"]

    for i, (frota, qtd) in enumerate(ranking, start=1):
        linhas.append(
            f"{i}º Frota {frota} — {qtd} preventiva(s)"
        )

    primeira_frota, primeira_qtd = ranking[0]

    linhas.append(
        f"\nA frota com mais preventivas é a frota {primeira_frota}, "
        f"com {primeira_qtd} ocorrência(s)."
    )

    return "\n".join(linhas)


def resposta_frotas_mais_atendidas():
    ranking = buscar_frotas_mais_atendidas()

    if not ranking:
        return "Não encontrei manutenções cadastradas por frota."

    linhas = ["Frotas mais atendidas:\n"]

    for i, (frota, qtd) in enumerate(ranking, start=1):
        linhas.append(
            f"{i}º Frota {frota} — {qtd} atendimento(s)"
        )

    primeira_frota, primeira_qtd = ranking[0]

    linhas.append(
        f"\nA frota mais atendida é a frota {primeira_frota}, "
        f"com {primeira_qtd} atendimento(s)."
    )

    return "\n".join(linhas)


def resposta_preventiva_corretiva():
    resumo = buscar_resumo_geral()

    total_servicos = resumo["preventivas"] + resumo["corretivas"]

    if total_servicos == 0:
        return "Não encontrei manutenções preventivas ou corretivas cadastradas."

    perc_preventiva = round((resumo["preventivas"] / total_servicos) * 100, 1)
    perc_corretiva = round((resumo["corretivas"] / total_servicos) * 100, 1)

    return f"""
Comparativo entre preventivas e corretivas:

• Preventivas: {resumo['preventivas']} ({perc_preventiva}%)
• Corretivas: {resumo['corretivas']} ({perc_corretiva}%)

Total considerado: {total_servicos} manutenção(ões).
""".strip()


def resposta_clientes_mais_atendidos():
    ranking = buscar_clientes_mais_atendidos()

    if not ranking:
        return "Não encontrei clientes cadastrados nas manutenções."

    linhas = ["Clientes mais atendidos:\n"]

    for i, (cliente, qtd) in enumerate(ranking, start=1):
        linhas.append(
            f"{i}º {cliente} — {qtd} atendimento(s)"
        )

    return "\n".join(linhas)


def resposta_tipo_atendimento():
    ranking = buscar_tipo_atendimento()

    if not ranking:
        return "Não encontrei tipos de atendimento cadastrados."

    total = sum(qtd for _, qtd in ranking) or 1

    linhas = ["Resumo por tipo de atendimento:\n"]

    for atendimento, qtd in ranking:
        percentual = round((qtd / total) * 100, 1)
        linhas.append(
            f"• {atendimento} — {qtd} atendimento(s) — {percentual}%"
        )

    return "\n".join(linhas)


def resposta_alertas_operacionais():
    resumo = buscar_resumo_geral()
    maior_tma = buscar_maiores_tma()
    causas = buscar_principais_causas()
    frotas_corretivas = buscar_frotas_por_tipo_servico("CORRETIVA")

    linhas = ["Alertas operacionais identificados:\n"]

    if resumo["andamento"] > 0:
        linhas.append(f"• Existem {resumo['andamento']} manutenção(ões) em andamento.")

    if maior_tma:
        r = maior_tma[0]
        linhas.append(
            f"• Maior TMA atual: Frota {formatar_frota(r.numero_frota)} — "
            f"OS {r.os or '-'} — {r.dtm} dia(s)."
        )

    if causas:
        causa, qtd = causas[0]
        linhas.append(f"• Principal causa registrada: {causa} com {qtd} ocorrência(s).")

    if frotas_corretivas:
        frota, qtd = frotas_corretivas[0]
        linhas.append(f"• Frota com mais corretivas: {frota} com {qtd} ocorrência(s).")

    if len(linhas) == 1:
        return "Não encontrei alertas operacionais relevantes no momento."

    return "\n".join(linhas)


def resposta_relatorio_cliente():
    resumo = buscar_resumo_geral()
    total_frotas, _ = buscar_total_frotas()

    return f"""
Resumo executivo para apresentação ao cliente:

No período analisado pelo sistema, foram identificadas {resumo['total']} manutenção(ões) registradas, envolvendo {total_frotas} frota(s).

Do total de manutenções, {resumo['preventivas']} foram preventivas e {resumo['corretivas']} foram corretivas. Atualmente, existem {resumo['andamento']} manutenção(ões) em andamento e {resumo['finalizadas']} finalizada(s).

O TMA médio registrado é de {resumo['tma_medio']} dia(s). A principal causa apontada nos registros foi: {resumo['principal_causa'][0]}, com {resumo['principal_causa'][1]} ocorrência(s).

Essas informações ajudam a acompanhar a operação, identificar reincidências e apoiar decisões sobre manutenção preventiva, corretiva e controle da frota.
""".strip()


# ==========================================
# 🧠 ROTEADOR POR INTENÇÃO
# ==========================================
def responder_sem_ia_inteligente(pergunta):
    intencao = detectar_intencao(pergunta)

    mapa_respostas = {
        "identidade_sidinho": resposta_quem_e_sidinho,
        "total_frotas": resposta_total_frotas,
        "total_manutencoes": resposta_total_manutencoes,
        "total_clientes": resposta_total_clientes,
        "resumo_geral": resposta_resumo_geral,
        "os_em_andamento": resposta_os_em_andamento,
        "maiores_tma": resposta_maiores_tma,
        "frotas_maior_tma": resposta_frotas_maior_tma,
        "principais_causas": resposta_principais_causas,
        "ultimas_finalizacoes": resposta_ultimas_finalizacoes,
        "historico_frota": lambda: resposta_historico_frota(pergunta),
        "frota_mais_corretiva": resposta_frota_mais_corretiva,
        "frota_mais_preventiva": resposta_frota_mais_preventiva,
        "frotas_mais_atendidas": resposta_frotas_mais_atendidas,
        "preventiva_corretiva": resposta_preventiva_corretiva,
        "finalizadas": resposta_finalizadas,
        "sem_data_saida": resposta_sem_data_saida,
        "clientes_mais_atendidos": resposta_clientes_mais_atendidos,
        "tipo_atendimento": resposta_tipo_atendimento,
        "alertas_operacionais": resposta_alertas_operacionais,
        "relatorio_cliente": resposta_relatorio_cliente,
    }

    funcao = mapa_respostas.get(intencao, resposta_resumo_geral)

    return funcao()


# ==========================================
# CONTEXTO PARA IA REAL
# ==========================================
def montar_contexto(pergunta):
    resposta_controlada = responder_sem_ia_inteligente(pergunta)

    contexto = f"""
RESPOSTA CONTROLADA GERADA PELO SISTEMA:
{resposta_controlada}

Observação:
Os dados acima foram consultados diretamente no banco do sistema.
Use esses dados como fonte principal.
"""

    return contexto.strip()


def chamar_ia(pergunta, contexto):
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return responder_sem_ia_inteligente(pergunta)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        prompt = f"""
Você é o Sidinho, assistente inteligente de um sistema de manutenção de frota.

Responda em português do Brasil, de forma clara, objetiva e profissional.

Nunca invente dados. Use somente as informações do CONTEXTO.
Se não houver informação suficiente, diga isso claramente.

PERGUNTA DO USUÁRIO:
{pergunta}

CONTEXTO DO SISTEMA:
{contexto}
"""

        resposta = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        return resposta.output_text

    except Exception as e:
        return (
            "Não consegui consultar a IA agora, mas consegui analisar os dados do sistema.\n\n"
            f"{responder_sem_ia_inteligente(pergunta)}\n\n"
            f"Detalhe técnico: {str(e)}"
        )


# ==========================================
# ROTAS
# ==========================================
@assistente_bp.route("/", methods=["GET"])
def tela_assistente():

    if not session.get("user_id"):
        return redirect("/login")

    return render_template("assistente.html")


@assistente_bp.route("/perguntar", methods=["POST"])
def perguntar():

    if not session.get("user_id"):
        return jsonify({
            "ok": False,
            "resposta": "Sessão expirada. Faça login novamente."
        }), 401

    dados = request.get_json() or {}
    pergunta = (dados.get("pergunta") or "").strip()

    if not pergunta:
        return jsonify({
            "ok": False,
            "resposta": "Digite uma pergunta para o Sidinho."
        }), 400

    contexto = montar_contexto(pergunta)
    resposta = chamar_ia(pergunta, contexto)

    return jsonify({
        "ok": True,
        "resposta": resposta
    })