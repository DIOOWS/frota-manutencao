from flask import Blueprint, render_template, request, redirect, session
from models.manutencao import Manutencao
from collections import defaultdict, Counter
from datetime import datetime

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
def dashboard():

    if not session.get("user_id"):
        return redirect("/login")

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = Manutencao.query

    if data_inicio and data_fim:
        try:
            inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            fim = datetime.strptime(data_fim, "%Y-%m-%d")
            query = query.filter(Manutencao.data.between(inicio, fim))
        except Exception as e:
            print("Erro filtro data:", e)

    registros = query.order_by(Manutencao.id.desc()).all()

    def formatar_frota(valor):
        try:
            return str(int(float(valor)))
        except:
            return "Sem frota"

    total = len(registros)

    por_mes = defaultdict(int)
    tipos_counter = Counter()
    frotas_counter = Counter()
    atendimento_counter = Counter()
    dados_frotas = {}
    dados_tipos_detalhe = {}

    corretivas = preventivas = andamento = concluidas = 0

    for r in registros:

        mes = None
        if r.data:
            mes = r.data.strftime("%Y-%m")
            por_mes[mes] += 1

        tipo = (r.tipo_manutencao or "Sem tipo").strip().upper()
        tipo_servico = (r.tipo_servico or "").strip().lower()
        status = (r.status or "").strip().lower()
        atendimento = (r.tipo_atendimento or "Sem info").strip().lower()
        frota = formatar_frota(r.numero_frota)

        tipos_counter[tipo] += 1
        frotas_counter[frota] += 1
        atendimento_counter[atendimento] += 1

        if tipo_servico == "corretiva":
            corretivas += 1
        elif tipo_servico == "preventiva":
            preventivas += 1

        if "andamento" in status:
            andamento += 1
        elif "finalizado" in status:
            concluidas += 1

        if frota and mes:
            if frota not in dados_frotas:
                dados_frotas[frota] = defaultdict(int)
            dados_frotas[frota][mes] += 1

        if tipo not in dados_tipos_detalhe:
            dados_tipos_detalhe[tipo] = []

        dados_tipos_detalhe[tipo].append({
            "frota": frota,
            "data": r.data.strftime("%d/%m") if r.data else "Sem data"
        })

    # 🔥 Frotas inteligentes
    dados_frota = defaultdict(list)
    for r in registros:
        frota = formatar_frota(r.numero_frota)
        if frota:
            dados_frota[frota].append(r)

    frotas_inteligente = []
    for frota, itens in dados_frota.items():
        total_frota = len(itens)
        tipos = Counter([i.tipo_manutencao for i in itens if i.tipo_manutencao])
        tipo_principal = tipos.most_common(1)[0][0] if tipos else "N/A"
        tipo_principal = tipo_principal.capitalize()

        ordenados = sorted([i for i in itens if i.data], key=lambda x: x.data)
        crescimento = 0

        if len(ordenados) >= 2:
            meio = len(ordenados)//2
            antes = len(ordenados[:meio])
            depois = len(ordenados[meio:])
            if antes > 0:
                crescimento = round(((depois - antes)/antes)*100, 1)

        if total_frota >= 10:
            nivel = "critica"
        elif total_frota >= 5:
            nivel = "atencao"
        else:
            nivel = "normal"

        frotas_inteligente.append({
            "frota": frota,
            "total": total_frota,
            "tipo": tipo_principal,
            "crescimento": crescimento,
            "nivel": nivel
        })

    frotas_inteligente = sorted(frotas_inteligente, key=lambda x: x["total"], reverse=True)[:5]

    # 🔥 Gráfico mensal
    labels = sorted(por_mes.keys())
    valores = [por_mes[m] for m in labels]

    labels_formatados = [
        datetime.strptime(m, "%Y-%m").strftime("%b/%y").capitalize()
        for m in labels
    ]

    crescimento = []
    for i in range(len(valores)):
        if i == 0:
            crescimento.append(0)
        else:
            ant = valores[i-1]
            atual = valores[i]
            crescimento.append(round(((atual-ant)/ant)*100,1) if ant else 0)

    # 🔥 Tipos
    tipos_ordenados = tipos_counter.most_common()
    labels_tipo = [t[0] for t in tipos_ordenados]
    valores_tipo = [t[1] for t in tipos_ordenados]

    # 🔥 Pareto
    total_manutencoes = sum(frotas_counter.values()) or 1
    frotas_ordenadas = sorted(frotas_counter.items(), key=lambda x: x[1], reverse=True)

    top = frotas_ordenadas[:10]
    outros = frotas_ordenadas[10:]
    soma_outros = sum(v for _, v in outros)

    labels_frota = [f[0] for f in top]
    valores_frota = [f[1] for f in top]

    pareto_percentual = []
    acumulado = 0

    for i, valor in enumerate(valores_frota):
        if labels_frota[i] == "Outros":
            pareto_percentual.append(pareto_percentual[-1] if pareto_percentual else 0)
            continue
        perc = (valor/total_manutencoes)*100
        acumulado += perc
        pareto_percentual.append(round(acumulado,2))

    # 🔥 Atendimento
    labels_atendimento = list(atendimento_counter.keys())
    valores_atendimento = list(atendimento_counter.values())

    # 🔥 Ranking
    dados_frota_mes = {}
    for frota, meses in dados_frotas.items():
        for mes, qtd in meses.items():
            if mes not in dados_frota_mes:
                dados_frota_mes[mes] = {}
            dados_frota_mes[mes][frota] = qtd

    # 🔥 proteção final
    labels_formatados = labels_formatados or []
    valores = valores or []
    crescimento = crescimento or []
    labels_tipo = labels_tipo or []
    valores_tipo = valores_tipo or []
    labels_frota = labels_frota or []
    valores_frota = valores_frota or []
    pareto_percentual = pareto_percentual or []
    labels_atendimento = labels_atendimento or []
    valores_atendimento = valores_atendimento or []
    dados_frota_mes = dados_frota_mes or {}
    frotas_inteligente = frotas_inteligente or []

    return render_template(
        "dashboard.html",
        total=total,
        corretivas=corretivas,
        preventivas=preventivas,
        andamento=andamento,
        concluidas=concluidas,
        labels=labels_formatados,
        valores=valores,
        crescimento=crescimento,
        labels_tipo=labels_tipo,
        valores_tipo=valores_tipo,
        labels_frota=labels_frota,
        valores_frota=valores_frota,
        pareto_percentual=pareto_percentual,
        labels_atendimento=labels_atendimento,
        valores_atendimento=valores_atendimento,
        frotas_inteligente=frotas_inteligente,
        dados_frota_mes=dados_frota_mes
    )