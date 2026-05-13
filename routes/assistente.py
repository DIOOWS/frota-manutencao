from flask import Blueprint, render_template, request, redirect, session, jsonify
from models.manutencao import Manutencao
from models.usuario import Usuario
from collections import Counter
from datetime import datetime
import os

from utils.assistente_intencoes import detectar_intencao

try:
    from utils.assistente_intencoes import detectar_intencoes
except Exception:
    detectar_intencoes = None


assistente_bp = Blueprint("assistente", __name__, url_prefix="/assistente")


# ==========================================
# 🔧 HELPERS
# ==========================================
def limpar_pergunta(pergunta):
    p = (pergunta or "").lower().strip()

    correcoes = {
        "quants": "quantas",
        "qnts": "quantas",
        "qntas": "quantas",
        "qntos": "quantos",
        "qnt": "quantidade",
        "qtd": "quantidade",
        "qtde": "quantidade",
        "manutencao": "manutenção",
        "manutencoes": "manutenções",
        "veiculos": "veículos",
        "veiculo": "veículo",
        "caminhoes": "caminhões",
        "caminhao": "caminhão",
        "saida": "saída",
        "saidas": "saídas",
        "atm": "tma",
        "dtm": "tma",
        "vc": "você",
        "voce": "você",
        "ta": "está",
        "esta": "está",
        "estao": "estão",
        "inteligete": "inteligente",
        "intelegente": "inteligente",
        "critica": "crítica",
        "critico": "crítico",
        "atencao": "atenção",
        "relatorio": "relatório",
        "historico": "histórico",
        "ultima": "última",
        "ultimas": "últimas",
    }

    for errado, certo in correcoes.items():
        p = p.replace(errado, certo)

    return p


def formatar_data(data):
    if not data:
        return "-"
    return data.strftime("%d/%m/%Y")


def formatar_frota(valor):
    try:
        return str(int(float(valor)))
    except Exception:
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


def extrair_numero_frota(pergunta):
    """
    Extrai o primeiro número encontrado na pergunta.
    Exemplo: 'relatório da frota 398' -> '398'
    """
    p = pergunta or ""
    partes = p.replace(",", " ").replace(".", " ").replace("?", " ").split()

    for parte in partes:
        if parte.isdigit():
            return parte

    return None


def salvar_frota_contexto(frota):
    """
    Guarda a última frota citada na sessão.
    Isso permite perguntas como:
    'e quando foi a última manutenção dela?'
    """
    if frota:
        session["sidinho_ultima_frota"] = str(frota)
        session.modified = True


def obter_frota_contexto(pergunta=None):
    """
    Primeiro tenta extrair frota da pergunta.
    Se não encontrar, tenta usar a última frota salva na sessão.
    """
    frota = extrair_numero_frota(pergunta or "")

    if frota:
        salvar_frota_contexto(frota)
        return frota

    return session.get("sidinho_ultima_frota")


def ordenar_por_data_desc(registros):
    return sorted(
        registros,
        key=lambda r: r.data or datetime.min.date(),
        reverse=True
    )


# ==========================================
# 🔍 DETECTORES DIRETOS
# ==========================================
def pergunta_sobre_sidinho(pergunta):
    p = limpar_pergunta(pergunta)

    termos = [
        "qual seu nome",
        "qual é seu nome",
        "qual e seu nome",
        "qual o seu nome",
        "quem é você",
        "quem e você",
        "quem é o sidinho",
        "quem e o sidinho",
        "se apresente",
        "se apresenta",
        "quem está falando",
        "quem esta falando",
        "o que você faz",
        "você sabe meu nome",
        "qual meu nome",
        "quem sou eu",
        "você me conhece",
    ]

    return any(t in p for t in termos)


def pergunta_ajuda_sidinho(pergunta):
    p = limpar_pergunta(pergunta)

    termos = [
        "como falar com você",
        "como falar com voce",
        "como usar o sidinho",
        "como faço perguntas",
        "como faco perguntas",
        "me ensine como falar",
        "me ensina como falar",
        "me ensine a perguntar",
        "me ensina a perguntar",
        "quais perguntas posso fazer",
        "o que posso perguntar",
        "quais comandos você entende",
        "quais comandos voce entende",
        "me ajuda a usar",
        "me ajuda a perguntar",
        "como consigo uma resposta",
        "como fazer perguntas",
    ]

    return any(t in p for t in termos)


def pergunta_frota_critica(pergunta):
    p = limpar_pergunta(pergunta)

    termos = [
        "frota mais crítica",
        "frota mais critica",
        "qual frota mais crítica",
        "qual frota mais critica",
        "qual frota está pior",
        "qual frota esta pior",
        "qual frota preocupa",
        "qual frota merece atenção",
        "qual frota merece atencao",
        "qual frota devo acompanhar",
        "qual frota devo olhar",
        "qual frota está dando mais problema",
        "qual frota esta dando mais problema",
        "qual veículo mais crítico",
        "qual veiculo mais critico",
        "qual caminhão mais crítico",
        "qual caminhao mais critico",
    ]

    return any(t in p for t in termos)


def pergunta_relatorio_frota(pergunta):
    p = limpar_pergunta(pergunta)

    tem_numero = any(char.isdigit() for char in p)

    termos_relatorio = [
        "relatório",
        "relatorio",
        "análise",
        "analise",
        "resumo",
        "diagnóstico",
        "diagnostico",
        "situação",
        "situacao",
        "como está",
        "como esta",
    ]

    termos_frota = [
        "frota",
        "veículo",
        "veiculo",
        "caminhão",
        "caminhao",
        "baú",
        "bau",
    ]

    referencias_contexto = [
        "dela",
        "dele",
        "essa",
        "esse",
        "dessa",
        "desse",
    ]

    # Caso 1: relatório da frota 420
    if any(t in p for t in termos_relatorio) and any(t in p for t in termos_frota) and tem_numero:
        return True

    # Caso 2: relatório da 420 / resumo da 420 / análise da 420
    if any(t in p for t in termos_relatorio) and tem_numero:
        return True

    # Caso 3: relatório dela / resumo dela / como está essa
    if any(t in p for t in termos_relatorio) and any(t in p for t in referencias_contexto):
        return True

    return False


def pergunta_ultima_manutencao_frota(pergunta):
    p = limpar_pergunta(pergunta)

    termos_ultima = [
        "última vez",
        "ultima vez",
        "última manutenção",
        "ultima manutenção",
        "última manutencao",
        "ultima manutencao",
        "última os",
        "ultima os",
        "último atendimento",
        "ultimo atendimento",
        "quando foi",
        "quando fez",
        "quando veio",
        "quando realizou",
    ]

    tem_referencia_frota = (
        "frota" in p
        or "veículo" in p
        or "veiculo" in p
        or "caminhão" in p
        or "caminhao" in p
        or "dela" in p
        or "dele" in p
        or "essa" in p
        or "esse" in p
        or any(char.isdigit() for char in p)
    )

    return tem_referencia_frota and any(t in p for t in termos_ultima)


def pergunta_corretivas_frota(pergunta):
    p = limpar_pergunta(pergunta)

    tem_corretiva = "corretiva" in p or "corretivas" in p

    referencia_frota = (
        "frota" in p
        or "veículo" in p
        or "veiculo" in p
        or "caminhão" in p
        or "caminhao" in p
        or "ela" in p
        or "ele" in p
        or "dela" in p
        or "dele" in p
        or "essa" in p
        or "esse" in p
        or any(char.isdigit() for char in p)
    )

    termos_quantidade = (
        "quantas" in p
        or "quantos" in p
        or "quantidade" in p
        or "total" in p
        or "tem" in p
        or "teve" in p
    )

    return tem_corretiva and referencia_frota and termos_quantidade


def pergunta_preventivas_frota(pergunta):
    p = limpar_pergunta(pergunta)

    tem_preventiva = "preventiva" in p or "preventivas" in p

    referencia_frota = (
        "frota" in p
        or "veículo" in p
        or "veiculo" in p
        or "caminhão" in p
        or "caminhao" in p
        or "ela" in p
        or "ele" in p
        or "dela" in p
        or "dele" in p
        or "essa" in p
        or "esse" in p
        or any(char.isdigit() for char in p)
    )

    termos_quantidade = (
        "quantas" in p
        or "quantos" in p
        or "quantidade" in p
        or "total" in p
        or "tem" in p
        or "teve" in p
    )

    return tem_preventiva and referencia_frota and termos_quantidade


# ==========================================
# 🤖 SIDINHO / IDENTIDADE
# ==========================================
def resposta_quem_e_sidinho():
    nome_usuario = obter_nome_usuario()

    return f"""
Olá, {nome_usuario}! Eu sou o Sidinho, seu assistente inteligente do sistema de manutenção de frota.

Eu fui criado para te ajudar a consultar e analisar os dados do sistema de forma rápida.

Eu posso responder perguntas como:

• Quantas frotas temos?
• Quantas manutenções estão cadastradas?
• Quais OS estão em andamento?
• Qual frota tem mais corretivas?
• Quantas corretivas ela tem?
• Quantas preventivas ela tem?
• Qual frota teve maior TMA?
• Qual frota mais crítica?
• Me dá o relatório da frota 398
• Quando foi a última manutenção da frota 398?
• Quais são as principais causas?
• Quais foram as últimas finalizações?
• Qual cliente teve mais atendimentos?
• Tem alguma manutenção sem data de saída?
• O que merece atenção na operação?

Por enquanto eu sou consultivo: eu analiso e respondo, mas não altero, excluo nem cadastro informações.
""".strip()


def resposta_ajuda_sidinho():
    nome_usuario = obter_nome_usuario()

    return f"""
Claro, {nome_usuario}! Você pode falar comigo de forma simples, como se estivesse perguntando para uma pessoa da operação.

Aqui vão exemplos de perguntas que eu consigo responder:

Resumo:
• Me dá um resumo geral
• Como está o sistema?
• O que merece atenção?
• Gera um resumo para o cliente

Frotas:
• Quantas frotas temos?
• Qual frota tem mais corretiva?
• Qual frota teve maior TMA?
• Qual frota mais crítica?
• Me mostra o histórico da frota 398
• Me dá o relatório da frota 398
• Quando foi a última manutenção da frota 398?
• Quantas corretivas ela tem?
• Quantas preventivas ela tem?

Manutenções:
• Quantas manutenções temos?
• Quais OS estão em andamento?
• Quais manutenções estão sem data de saída?
• Quais foram as últimas finalizações?

Análises:
• Quais são as principais causas?
• Tem mais preventiva ou corretiva?
• Quais clientes mais atendidos?
• Quantos atendimentos internos e externos?

Você também pode juntar perguntas:
• Me dá um resumo e mostra as OS em andamento
• Qual frota tem mais corretiva e quais são as principais causas?
• Mostra as frotas com maior TMA e os alertas operacionais

Dica:
Quando quiser consultar uma frota específica, coloque o número dela na pergunta.

Exemplo:
relatório da frota 398

Depois disso, você pode continuar o papo:
• E quando foi a última manutenção dela?
• Ela teve corretiva?
• Quantas corretivas ela tem?
• Quantas preventivas ela tem?
• Como está essa frota?
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


def buscar_registros_frota(frota):
    if not frota:
        return []

    registros = [
        r for r in Manutencao.query.all()
        if formatar_frota(r.numero_frota) == str(frota)
    ]

    return ordenar_por_data_desc(registros)


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
    frota_busca = obter_frota_contexto(pergunta)

    if not frota_busca:
        return None, []

    registros = buscar_registros_frota(frota_busca)

    return frota_busca, registros[:10]


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
Hoje temos {total} frota(s) identificada(s) no sistema.

Frotas encontradas:
{lista}

Esse total é calculado com base nos números de frota presentes nos registros de manutenção.
""".strip()


def resposta_total_manutencoes():
    total = Manutencao.query.count()

    return f"""
Temos {total} manutenção(ões) registrada(s) no sistema.

Esse número considera todos os registros cadastrados na base de manutenções.
""".strip()


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

Leitura rápida:
O sistema possui {total_frotas} frota(s) acompanhada(s) e {resumo['total']} manutenção(ões) registrada(s). A principal causa registrada até agora é {resumo['principal_causa'][0]}.
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

    linhas.append("\nEssas OS merecem acompanhamento porque ainda não foram finalizadas.")

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

    linhas.append("\nEsses registros podem precisar de revisão, porque ainda não possuem data de saída.")

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

    linhas.append("\nAs maiores posições desse ranking indicam manutenções que ficaram mais tempo em atendimento.")

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

    linhas.append("\nAs primeiras frotas da lista merecem atenção por apresentarem maior tempo médio de atendimento.")

    return "\n".join(linhas)


def resposta_principais_causas():
    causas = buscar_principais_causas()

    if not causas:
        return "Não encontrei causas cadastradas."

    linhas = ["Principais causas de manutenção:\n"]

    for i, (causa, qtd) in enumerate(causas, start=1):
        linhas.append(f"{i}º {causa} — {qtd} ocorrência(s)")

    causa_top, qtd_top = causas[0]
    linhas.append(f"\nA causa que mais aparece é {causa_top}, com {qtd_top} ocorrência(s).")

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

    salvar_frota_contexto(frota)

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


def resposta_relatorio_frota(pergunta):
    frota = obter_frota_contexto(pergunta)

    if not frota:
        return "Me informe o número da frota para gerar o relatório. Exemplo: relatório da frota 398."

    salvar_frota_contexto(frota)

    registros = buscar_registros_frota(frota)

    if not registros:
        return f"Não encontrei manutenções para a frota {frota}."

    total = len(registros)
    preventivas = sum(1 for r in registros if eh_preventiva(r))
    corretivas = sum(1 for r in registros if eh_corretiva(r))
    andamento = sum(1 for r in registros if "ANDAMENTO" in texto(r.status))
    finalizadas = sum(1 for r in registros if "FINALIZADO" in texto(r.status))

    tmas = [r.dtm for r in registros if r.dtm is not None]
    tma_medio = round(sum(tmas) / len(tmas), 1) if tmas else 0

    causas = Counter(
        texto(r.causa) if texto(r.causa) else "SEM CAUSA"
        for r in registros
    )

    principal_causa = causas.most_common(1)[0] if causas else ("SEM CAUSA", 0)

    ultima = registros[0]

    linhas = [
        f"Relatório da Frota {frota}\n",
        "Resumo:",
        f"• Total de manutenções: {total}",
        f"• Preventivas: {preventivas}",
        f"• Corretivas: {corretivas}",
        f"• Em andamento: {andamento}",
        f"• Finalizadas: {finalizadas}",
        f"• TMA médio: {tma_medio} dia(s)",
        f"• Principal causa: {principal_causa[0]} ({principal_causa[1]} ocorrência(s))",
        "",
        "Última manutenção encontrada:",
        f"• OS: {ultima.os or '-'}",
        f"• Entrada: {formatar_data(ultima.data)}",
        f"• Saída: {formatar_data(ultima.data_saida)}",
        f"• Serviço: {ultima.tipo_servico or '-'}",
        f"• Status: {ultima.status or '-'}",
        f"• Causa: {ultima.causa or '-'}",
        f"• TMA: {ultima.dtm if ultima.dtm is not None else '-'} dia(s)",
        "",
        "Últimas OS:",
    ]

    for r in registros[:5]:
        linhas.append(
            f"• OS {r.os or '-'} — Entrada {formatar_data(r.data)} — "
            f"Saída {formatar_data(r.data_saida)} — "
            f"{r.tipo_servico or '-'} — TMA {r.dtm if r.dtm is not None else '-'}"
        )

    leitura = []

    if corretivas > preventivas:
        leitura.append("A frota possui mais corretivas do que preventivas, o que pode indicar necessidade de acompanhamento mais próximo.")

    if andamento > 0:
        leitura.append("Existe manutenção em andamento para essa frota.")

    if tma_medio >= 3:
        leitura.append("O TMA médio está acima de 3 dias, então vale acompanhar o tempo de atendimento.")

    if not leitura:
        leitura.append("A frota não apresenta um sinal crítico forte pelos dados atuais, mas vale manter o acompanhamento periódico.")

    linhas.append("")
    linhas.append("Leitura operacional:")
    for item in leitura:
        linhas.append(f"• {item}")

    return "\n".join(linhas)


def resposta_ultima_manutencao_frota(pergunta):
    frota = obter_frota_contexto(pergunta)

    if not frota:
        return "Me informe o número da frota. Exemplo: quando foi a última manutenção da frota 398?"

    salvar_frota_contexto(frota)

    registros = buscar_registros_frota(frota)

    if not registros:
        return f"Não encontrei manutenções para a frota {frota}."

    ultima = registros[0]

    data_referencia = ultima.data_saida or ultima.data

    return f"""
A última manutenção encontrada para a frota {frota} foi em {formatar_data(data_referencia)}.

Dados da última manutenção:
• OS: {ultima.os or '-'}
• Entrada: {formatar_data(ultima.data)}
• Saída: {formatar_data(ultima.data_saida)}
• Serviço: {ultima.tipo_servico or '-'}
• Atendimento: {ultima.tipo_atendimento or '-'}
• Status: {ultima.status or '-'}
• Causa: {ultima.causa or '-'}
• TMA: {ultima.dtm if ultima.dtm is not None else '-'} dia(s)

Leitura:
Essa foi a manutenção mais recente encontrada para essa frota no sistema.
""".strip()


def resposta_corretivas_frota(pergunta):
    frota = obter_frota_contexto(pergunta)

    if not frota:
        return "Me informe o número da frota. Exemplo: quantas corretivas a frota 420 tem?"

    salvar_frota_contexto(frota)

    registros = buscar_registros_frota(frota)

    if not registros:
        return f"Não encontrei manutenções para a frota {frota}."

    corretivas = [r for r in registros if eh_corretiva(r)]
    total_corretivas = len(corretivas)

    if total_corretivas == 0:
        return f"A frota {frota} não possui manutenções corretivas registradas no sistema."

    linhas = [
        f"A frota {frota} possui {total_corretivas} manutenção(ões) corretiva(s) registrada(s).\n",
        "Últimas corretivas encontradas:"
    ]

    for r in corretivas[:5]:
        linhas.append(
            f"• OS {r.os or '-'} — Entrada {formatar_data(r.data)} — "
            f"Saída {formatar_data(r.data_saida)} — "
            f"Status {r.status or '-'} — "
            f"Causa {r.causa or '-'} — "
            f"TMA {r.dtm if r.dtm is not None else '-'} dia(s)"
        )

    if total_corretivas >= 2:
        linhas.append(
            "\nLeitura: essa frota merece acompanhamento, porque possui mais de uma corretiva registrada."
        )

    return "\n".join(linhas)


def resposta_preventivas_frota(pergunta):
    frota = obter_frota_contexto(pergunta)

    if not frota:
        return "Me informe o número da frota. Exemplo: quantas preventivas a frota 420 tem?"

    salvar_frota_contexto(frota)

    registros = buscar_registros_frota(frota)

    if not registros:
        return f"Não encontrei manutenções para a frota {frota}."

    preventivas = [r for r in registros if eh_preventiva(r)]
    total_preventivas = len(preventivas)

    if total_preventivas == 0:
        return f"A frota {frota} não possui manutenções preventivas registradas no sistema."

    linhas = [
        f"A frota {frota} possui {total_preventivas} manutenção(ões) preventiva(s) registrada(s).\n",
        "Últimas preventivas encontradas:"
    ]

    for r in preventivas[:5]:
        linhas.append(
            f"• OS {r.os or '-'} — Entrada {formatar_data(r.data)} — "
            f"Saída {formatar_data(r.data_saida)} — "
            f"Status {r.status or '-'} — "
            f"Causa {r.causa or '-'} — "
            f"TMA {r.dtm if r.dtm is not None else '-'} dia(s)"
        )

    return "\n".join(linhas)


def resposta_frota_mais_corretiva():
    ranking = buscar_frotas_por_tipo_servico("CORRETIVA")

    if not ranking:
        return "Não encontrei manutenções corretivas cadastradas."

    linhas = ["Frotas com mais manutenções corretivas:\n"]

    for i, (frota, qtd) in enumerate(ranking, start=1):
        linhas.append(f"{i}º Frota {frota} — {qtd} corretiva(s)")

    primeira_frota, primeira_qtd = ranking[0]

    salvar_frota_contexto(primeira_frota)

    linhas.append(
        f"\nA frota com mais corretivas é a frota {primeira_frota}, "
        f"com {primeira_qtd} ocorrência(s)."
    )

    if primeira_qtd >= 2:
        linhas.append("Essa frota merece atenção, porque aparece mais de uma vez em manutenção corretiva.")

    return "\n".join(linhas)


def resposta_frota_mais_preventiva():
    ranking = buscar_frotas_por_tipo_servico("PREVENTIVA")

    if not ranking:
        return "Não encontrei manutenções preventivas cadastradas."

    linhas = ["Frotas com mais manutenções preventivas:\n"]

    for i, (frota, qtd) in enumerate(ranking, start=1):
        linhas.append(f"{i}º Frota {frota} — {qtd} preventiva(s)")

    primeira_frota, primeira_qtd = ranking[0]

    salvar_frota_contexto(primeira_frota)

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
        linhas.append(f"{i}º Frota {frota} — {qtd} atendimento(s)")

    primeira_frota, primeira_qtd = ranking[0]

    salvar_frota_contexto(primeira_frota)

    linhas.append(
        f"\nA frota mais atendida é a frota {primeira_frota}, "
        f"com {primeira_qtd} atendimento(s)."
    )

    return "\n".join(linhas)


def resposta_frota_critica():
    registros = Manutencao.query.all()

    if not registros:
        return "Ainda não encontrei dados suficientes para apontar uma frota crítica."

    dados = {}

    for r in registros:
        frota = formatar_frota(r.numero_frota)

        if not frota or frota == "SEM FROTA":
            continue

        if frota not in dados:
            dados[frota] = {
                "total": 0,
                "corretivas": 0,
                "andamento": 0,
                "tma_total": 0,
                "tma_qtd": 0,
                "causas": Counter()
            }

        dados[frota]["total"] += 1

        if eh_corretiva(r):
            dados[frota]["corretivas"] += 1

        if "ANDAMENTO" in texto(r.status):
            dados[frota]["andamento"] += 1

        if r.dtm is not None:
            dados[frota]["tma_total"] += r.dtm
            dados[frota]["tma_qtd"] += 1

        causa = texto(r.causa) if texto(r.causa) else "SEM CAUSA"
        dados[frota]["causas"][causa] += 1

    ranking = []

    for frota, info in dados.items():
        tma_medio = round(info["tma_total"] / info["tma_qtd"], 1) if info["tma_qtd"] else 0

        pontuacao = (
            info["corretivas"] * 3
            + info["andamento"] * 2
            + tma_medio
            + info["total"]
        )

        ranking.append({
            "frota": frota,
            "pontuacao": pontuacao,
            "total": info["total"],
            "corretivas": info["corretivas"],
            "andamento": info["andamento"],
            "tma_medio": tma_medio,
            "principal_causa": info["causas"].most_common(1)[0] if info["causas"] else ("SEM CAUSA", 0)
        })

    ranking = sorted(ranking, key=lambda x: x["pontuacao"], reverse=True)

    if not ranking:
        return "Ainda não encontrei dados suficientes para apontar uma frota crítica."

    critica = ranking[0]

    salvar_frota_contexto(critica["frota"])

    return f"""
A frota mais crítica no momento é a Frota {critica['frota']}.

Motivos:
• Total de atendimento(s): {critica['total']}
• Corretiva(s): {critica['corretivas']}
• Em andamento: {critica['andamento']}
• TMA médio: {critica['tma_medio']} dia(s)
• Principal causa: {critica['principal_causa'][0]} ({critica['principal_causa'][1]} ocorrência(s))

Minha leitura:
Essa frota merece atenção porque combina volume de atendimento, corretivas, tempo médio e possíveis pendências operacionais.
""".strip()


def resposta_preventiva_corretiva():
    resumo = buscar_resumo_geral()

    total_servicos = resumo["preventivas"] + resumo["corretivas"]

    if total_servicos == 0:
        return "Não encontrei manutenções preventivas ou corretivas cadastradas."

    perc_preventiva = round((resumo["preventivas"] / total_servicos) * 100, 1)
    perc_corretiva = round((resumo["corretivas"] / total_servicos) * 100, 1)

    if resumo["corretivas"] > resumo["preventivas"]:
        leitura = "A operação tem mais corretivas do que preventivas. Isso pode indicar maior atuação em problemas já ocorridos."
    elif resumo["preventivas"] > resumo["corretivas"]:
        leitura = "A operação tem mais preventivas do que corretivas. Isso é positivo para controle e prevenção."
    else:
        leitura = "A operação está equilibrada entre preventivas e corretivas."

    return f"""
Comparativo entre preventivas e corretivas:

• Preventivas: {resumo['preventivas']} ({perc_preventiva}%)
• Corretivas: {resumo['corretivas']} ({perc_corretiva}%)

Total considerado: {total_servicos} manutenção(ões).

Leitura:
{leitura}
""".strip()


def resposta_clientes_mais_atendidos():
    ranking = buscar_clientes_mais_atendidos()

    if not ranking:
        return "Não encontrei clientes cadastrados nas manutenções."

    linhas = ["Clientes mais atendidos:\n"]

    for i, (cliente, qtd) in enumerate(ranking, start=1):
        linhas.append(f"{i}º {cliente} — {qtd} atendimento(s)")

    return "\n".join(linhas)


def resposta_tipo_atendimento():
    ranking = buscar_tipo_atendimento()

    if not ranking:
        return "Não encontrei tipos de atendimento cadastrados."

    total = sum(qtd for _, qtd in ranking) or 1

    linhas = ["Resumo por tipo de atendimento:\n"]

    for atendimento, qtd in ranking:
        percentual = round((qtd / total) * 100, 1)
        linhas.append(f"• {atendimento} — {qtd} atendimento(s) — {percentual}%")

    return "\n".join(linhas)


def resposta_alertas_operacionais():
    resumo = buscar_resumo_geral()
    maior_tma = buscar_maiores_tma()
    causas = buscar_principais_causas()
    frotas_corretivas = buscar_frotas_por_tipo_servico("CORRETIVA")

    linhas = ["Pontos que merecem atenção:\n"]

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
        salvar_frota_contexto(frota)
        linhas.append(f"• Frota com mais corretivas: {frota} com {qtd} ocorrência(s).")

    if len(linhas) == 1:
        return "Não encontrei alertas operacionais relevantes no momento."

    linhas.append("\nEsses pontos podem ser usados como prioridade para análise operacional.")

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


def resposta_nao_entendi():
    nome_usuario = obter_nome_usuario()

    return f"""
{nome_usuario}, ainda não consegui entender totalmente sua pergunta.

Você pode tentar perguntar assim:

• Sidinho, me ensine como falar com você
• Qual seu nome?
• Quantas frotas temos?
• Quantas manutenções temos?
• Quais OS estão em andamento?
• Qual frota tem mais corretiva?
• Qual frota mais crítica?
• Me dá o relatório da frota 398
• Quando foi a última manutenção da frota 398?
• Quantas corretivas ela tem?
• Quantas preventivas ela tem?
• Quais são as principais causas?
• Quais frotas tiveram maior TMA?
• Me mostra o histórico da frota 398
• O que merece atenção?
• Gera um resumo para o cliente
""".strip()


# ==========================================
# 🧠 ROTEADOR POR INTENÇÃO
# ==========================================
def obter_intencoes(pergunta):
    pergunta_limpa = limpar_pergunta(pergunta)

    if pergunta_sobre_sidinho(pergunta_limpa):
        return ["identidade_sidinho"]

    if pergunta_ajuda_sidinho(pergunta_limpa):
        return ["ajuda_sidinho"]

    if pergunta_ultima_manutencao_frota(pergunta_limpa):
        return ["ultima_manutencao_frota"]

    if pergunta_relatorio_frota(pergunta_limpa):
        return ["relatorio_frota"]

    if pergunta_corretivas_frota(pergunta_limpa):
        return ["corretivas_frota"]

    if pergunta_preventivas_frota(pergunta_limpa):
        return ["preventivas_frota"]

    if pergunta_frota_critica(pergunta_limpa):
        return ["frota_critica"]

    if detectar_intencoes:
        intencoes = detectar_intencoes(pergunta_limpa, limite=3)
    else:
        intencoes = [detectar_intencao(pergunta_limpa)]

    if not intencoes:
        intencoes = [detectar_intencao(pergunta_limpa)]

    return intencoes


def executar_intencao(intencao, pergunta):
    mapa_respostas = {
        "identidade_sidinho": resposta_quem_e_sidinho,
        "ajuda_sidinho": resposta_ajuda_sidinho,
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
        "relatorio_frota": lambda: resposta_relatorio_frota(pergunta),
        "ultima_manutencao_frota": lambda: resposta_ultima_manutencao_frota(pergunta),
        "corretivas_frota": lambda: resposta_corretivas_frota(pergunta),
        "preventivas_frota": lambda: resposta_preventivas_frota(pergunta),
        "frota_mais_corretiva": resposta_frota_mais_corretiva,
        "frota_mais_preventiva": resposta_frota_mais_preventiva,
        "frotas_mais_atendidas": resposta_frotas_mais_atendidas,
        "frota_critica": resposta_frota_critica,
        "preventiva_corretiva": resposta_preventiva_corretiva,
        "finalizadas": resposta_finalizadas,
        "sem_data_saida": resposta_sem_data_saida,
        "clientes_mais_atendidos": resposta_clientes_mais_atendidos,
        "tipo_atendimento": resposta_tipo_atendimento,
        "alertas_operacionais": resposta_alertas_operacionais,
        "relatorio_cliente": resposta_relatorio_cliente,
    }

    funcao = mapa_respostas.get(intencao)

    if not funcao:
        return None

    return funcao()


def responder_sem_ia_inteligente(pergunta):
    intencoes = obter_intencoes(pergunta)
    respostas = []

    for intencao in intencoes:
        resposta = executar_intencao(intencao, pergunta)

        if resposta and resposta not in respostas:
            respostas.append(resposta)

    if not respostas:
        return resposta_nao_entendi()

    return "\n\n---\n\n".join(respostas)


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