import pandas as pd
from db import get_connection
from psycopg2.extras import execute_batch

df = pd.read_excel("dados.xlsx")

df.columns = df.columns.str.strip()
df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce")
df = df.where(pd.notnull(df), None)
df = df.dropna(how='all')

conn = get_connection()
cur = conn.cursor()

cur.execute("DELETE FROM manutencoes")

dados = []

for _, row in df.iterrows():

    if pd.isna(row["DATA"]) or pd.isna(row["Nº FROTA"]):
        continue

    data = row["DATA"]

    cliente = row["CLIENTE"]
    if cliente:
        cliente = str(cliente).strip()

    dados.append((
        data,
        row["Nº FROTA"],
        row["BAU"],
        row["TIPO VEICULO"],
        row["TIPO SERVIÇO"],
        row["TIPO ATENDIMENTO"],
        row["TIPO MANUTENÇÃO"],
        row["STATUS"],
        row["OBSERVAÇÃO"],
        cliente
    ))

execute_batch(cur, """
    INSERT INTO manutencoes (
        data, numero_frota, bau, tipo_veiculo,
        tipo_servico, tipo_atendimento,
        tipo_manutencao, status, observacao,
        cliente
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", dados)

conn.commit()
cur.close()
conn.close()

print("TOTAL INSERIDO:", len(dados))