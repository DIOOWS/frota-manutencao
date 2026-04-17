from flask import Flask, render_template, request
from db import get_connection
import calendar
from datetime import datetime

app = Flask(__name__)

@app.route("/", methods=["GET"])
def dashboard():

    conn = get_connection()
    cur = conn.cursor()

    # ======================
    # FILTROS
    # ======================
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    cliente = request.args.get("cliente")
    frota = request.args.get("frota")

    where_clause = ""
    params = []

    def add_condition(base, condition):
        return f"{base} AND {condition}" if base else f"WHERE {condition}"

    # DATA
    if data_inicio and data_fim:
        where_clause = add_condition(where_clause, "data BETWEEN %s AND %s")
        params.extend([data_inicio, data_fim])

    # CLIENTE
    if cliente:
        where_clause = add_condition(where_clause, "cliente = %s")
        params.append(cliente)

    # FROTA
    if frota:
        where_clause = add_condition(where_clause, "numero_frota = %s")
        params.append(frota)

    # ======================
    # TOTAL
    # ======================
    cur.execute(f"SELECT COUNT(*) FROM manutencoes {where_clause}", params)
    total = cur.fetchone()[0]

    # ======================
    # TIPOS
    # ======================
    cur.execute(f"""
        SELECT COALESCE(tipo_servico, 'SEM TIPO'), COUNT(*)
        FROM manutencoes
        {where_clause}
        GROUP BY tipo_servico
    """, params)
    tipos = cur.fetchall()

    tipos_dict = {t[0]: t[1] for t in tipos}

    corretiva = tipos_dict.get("CORRETIVA", 0)
    preventiva = tipos_dict.get("PREVENTIVA", 0)

    perc_corretiva = round((corretiva / total) * 100, 1) if total else 0
    perc_preventiva = round((preventiva / total) * 100, 1) if total else 0

    confiabilidade = round(100 - perc_corretiva, 1)

    # ======================
    # ANDAMENTO
    # ======================
    cur.execute(f"""
        SELECT COUNT(*) FROM manutencoes
        {add_condition(where_clause, "status = 'ANDAMENTO'")}
    """, params)
    andamento = cur.fetchone()[0]

    # ======================
    # TOP FROTA
    # ======================
    cur.execute(f"""
        SELECT numero_frota, COUNT(*)
        FROM manutencoes
        {where_clause}
        GROUP BY numero_frota
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """, params)
    top_frota = cur.fetchone() or ("-", 0)

    # ======================
    # TOP 8 FROTAS
    # ======================
    cur.execute(f"""
        SELECT numero_frota, COUNT(*)
        FROM manutencoes
        {where_clause}
        GROUP BY numero_frota
        ORDER BY COUNT(*) DESC
        LIMIT 8
    """, params)
    top8_frotas = cur.fetchall()

    # ======================
    # TOP 8 TIPOS
    # ======================
    cur.execute(f"""
        SELECT COALESCE(tipo_manutencao, 'SEM TIPO'), COUNT(*)
        FROM manutencoes
        {where_clause}
        GROUP BY tipo_manutencao
        ORDER BY COUNT(*) DESC
        LIMIT 8
    """, params)
    top8_tipos = cur.fetchall()

    # ======================
    # EVOLUÇÃO
    # ======================
    cur.execute(f"""
        SELECT 
            DATE_TRUNC('month', data) as mes,
            TO_CHAR(DATE_TRUNC('month', data), 'MM/YYYY'),
            COUNT(*)
        FROM manutencoes
        {where_clause}
        GROUP BY mes
        ORDER BY mes
    """, params)

    evolucao_raw = cur.fetchall()
    evolucao = [(row[1], row[2]) for row in evolucao_raw]

    # ======================
    # DADOS DO MODAL (TOP 5)
    # ======================
    detalhe_frotas = []
    detalhe_tipos = []

    # 🔥 CORREÇÃO AQUI
    if evolucao:
        ultimo_mes = evolucao[-1][0]
        mes, ano = ultimo_mes.split("/")
    else:
        hoje = datetime.now()
        mes = f"{hoje.month:02d}"
        ano = str(hoje.year)

    data_inicio_modal = f"{ano}-{mes}-01"
    ultimo_dia = calendar.monthrange(int(ano), int(mes))[1]
    data_fim_modal = f"{ano}-{mes}-{ultimo_dia}"

    cur.execute("""
        SELECT numero_frota, COUNT(*)
        FROM manutencoes
        WHERE data BETWEEN %s AND %s
        GROUP BY numero_frota
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """, (data_inicio_modal, data_fim_modal))
    detalhe_frotas = cur.fetchall() or []

    cur.execute("""
        SELECT COALESCE(tipo_manutencao,'SEM TIPO'), COUNT(*)
        FROM manutencoes
        WHERE data BETWEEN %s AND %s
        GROUP BY tipo_manutencao
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """, (data_inicio_modal, data_fim_modal))
    detalhe_tipos = cur.fetchall() or []

    # ======================
    # PICO E PIOR
    # ======================
    pico_mes = max(evolucao, key=lambda x: x[1]) if evolucao else ("-", 0)
    pior_mes = min(evolucao, key=lambda x: x[1]) if evolucao else ("-", 0)

    # ======================
    # TENDÊNCIA
    # ======================
    tendencia = 0
    if len(evolucao) >= 2:
        atual = evolucao[-1][1]
        anterior = evolucao[-2][1]

        if anterior > 0:
            tendencia = round(((atual - anterior) / anterior) * 100, 1)

    # ======================
    # LISTAS PARA FILTRO
    # ======================
    cur.execute("SELECT DISTINCT cliente FROM manutencoes ORDER BY cliente")
    clientes = [c[0] for c in cur.fetchall() if c[0]]

    cur.execute("SELECT DISTINCT numero_frota FROM manutencoes ORDER BY numero_frota")
    frotas = [f[0] for f in cur.fetchall() if f[0]]

    conn.close()

    return render_template(
        "dashboard.html",
        total=total,
        tipos=tipos,
        corretiva=corretiva,
        preventiva=preventiva,
        perc_corretiva=perc_corretiva,
        perc_preventiva=perc_preventiva,
        confiabilidade=confiabilidade,
        andamento=andamento,
        top_frota=top_frota,
        top8_frotas=top8_frotas,
        top8_tipos=top8_tipos,
        evolucao=evolucao,
        tendencia=tendencia,
        pico_mes=pico_mes,
        pior_mes=pior_mes,

        clientes=clientes,
        frotas=frotas,
        cliente_selecionado=cliente,
        frota_selecionada=frota,

        detalhe_frotas=detalhe_frotas,
        detalhe_tipos=detalhe_tipos
    )

if __name__ == "__main__":
    app.run(debug=True)