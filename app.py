from flask import Flask, render_template, request
from db import get_connection

app = Flask(__name__)

@app.route("/", methods=["GET"])
def dashboard():
    conn = get_connection()
    cur = conn.cursor()

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    where_clause = ""
    params = []

    if data_inicio and data_fim:
        where_clause = "WHERE data BETWEEN %s AND %s"
        params = [data_inicio, data_fim]

    def add_condition(base, condition):
        return f"{base} AND {condition}" if base else f"WHERE {condition}"

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
    # EVOLUÇÃO CORRIGIDA
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
        pico_mes=pico_mes,      # 🔥 corrigido
        pior_mes=pior_mes       # 🔥 corrigido
    )

if __name__ == "__main__":
    app.run(debug=True)