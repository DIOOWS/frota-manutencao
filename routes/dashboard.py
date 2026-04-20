from flask import Blueprint, render_template, request
from models.manutencao import Manutencao
from collections import defaultdict, Counter

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def dashboard():

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = Manutencao.query

    if data_inicio and data_fim:
        query = query.filter(
            Manutencao.data.between(data_inicio, data_fim)
        )

    registros = query.all()

    # 🔥 função para padronizar frota
    def formatar_frota(valor):
        try:
            return str(int(float(valor)))
        except:
            return "Sem frota"

    total = len(registros)

    # 🔥 gráfico por mês
    por_mes = defaultdict(int)

    # 🔥 estruturas auxiliares
    tipos_counter = Counter()
    frotas_counter = Counter()
    atendimento_counter = Counter()
    dados_frotas = {}
    dados_tipos_detalhe = {}

    corretivas = 0
    preventivas = 0
    andamento = 0
    concluidas = 0

    # 🔥 LOOP ÚNICO (OTIMIZADO)
    for r in registros:

        # DATA / MÊS
        if r.data:
            mes = r.data.strftime("%Y-%m")
            por_mes[mes] += 1

        # PADRONIZAÇÕES
        tipo = (r.tipo_manutencao or "Sem tipo").strip().upper()
        tipo_servico = (r.tipo_servico or "").strip().lower()
        status = (r.status or "").strip().lower()
        atendimento = (r.tipo_atendimento or "Sem info").strip().lower()
        frota = formatar_frota(r.numero_frota)

        # CONTADORES
        tipos_counter[tipo] += 1
        frotas_counter[frota] += 1
        atendimento_counter[atendimento] += 1

        # SERVIÇOS
        if tipo_servico == "corretiva":
            corretivas += 1
        elif tipo_servico == "preventiva":
            preventivas += 1

        # STATUS
        if status == "andamento":
            andamento += 1
        elif status == "finalizado":
            concluidas += 1

        # HISTÓRICO POR FROTA
        if r.numero_frota and r.data:
            if frota not in dados_frotas:
                dados_frotas[frota] = defaultdict(int)

            dados_frotas[frota][mes] += 1

        # MODAL DINÂMICO POR TIPO
        if tipo not in dados_tipos_detalhe:
            dados_tipos_detalhe[tipo] = []

        dados_tipos_detalhe[tipo].append({
            "frota": frota,
            "data": r.data.strftime("%d/%m") if r.data else "Sem data",
            "data_ordem": r.data
        })

    # 🔥 GRÁFICO POR MÊS
    labels = sorted(por_mes.keys())
    valores = [por_mes[m] for m in labels]

    # 🔥 TIPOS (ORDENADO)
    tipos_ordenados = tipos_counter.most_common()
    labels_tipo = [t[0] for t in tipos_ordenados]
    valores_tipo = [t[1] for t in tipos_ordenados]

    # 🔥 TOP FROTAS
    top_frotas = frotas_counter.most_common(5)
    labels_frota = [f[0] for f in top_frotas]
    valores_frota = [f[1] for f in top_frotas]

    # 🔥 INTERNO vs EXTERNO
    labels_atendimento = list(atendimento_counter.keys())
    valores_atendimento = list(atendimento_counter.values())

    # 🔥 ORGANIZA HISTÓRICO POR FROTA
    dados_frotas = {
        frota: dict(sorted(meses.items()))
        for frota, meses in dados_frotas.items()
    }

    # 🔥 ORDENA MODAL (DATA DESC)
    for tipo in dados_tipos_detalhe:
        dados_tipos_detalhe[tipo] = sorted(
            dados_tipos_detalhe[tipo],
            key=lambda x: x["data_ordem"] or 0,
            reverse=True
        )

        # remove campo auxiliar
        for item in dados_tipos_detalhe[tipo]:
            item.pop("data_ordem", None)

    # 🔥 FROTAS CRÍTICAS
    limite = 3

    frotas_criticas = [
        (frota, qtd)
        for frota, qtd in frotas_counter.items()
        if qtd >= limite
    ]

    frotas_criticas = sorted(
        frotas_criticas,
        key=lambda x: x[1],
        reverse=True
    )[:5]

    return render_template(
        "dashboard.html",
        total=total,
        corretivas=corretivas,
        preventivas=preventivas,
        andamento=andamento,
        concluidas=concluidas,
        labels=labels,
        valores=valores,
        labels_tipo=labels_tipo,
        valores_tipo=valores_tipo,
        labels_frota=labels_frota,
        valores_frota=valores_frota,
        labels_atendimento=labels_atendimento,
        valores_atendimento=valores_atendimento,
        dados_frotas=dados_frotas,
        frotas_criticas=frotas_criticas,
        dados_tipos_detalhe=dados_tipos_detalhe,
    )