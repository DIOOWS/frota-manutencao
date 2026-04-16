import pandas as pd
from db import get_connection

df = pd.read_excel("dados.xlsx")

conn = get_connection()
cur = conn.cursor()

# LIMPA TABELA
cur.execute("DELETE FROM manutencoes")

contador = 0

for _, row in df.iterrows():

    data = pd.to_datetime(row["DATA"], dayfirst=True, errors="coerce")

    if pd.isna(data):
        continue

    tipo_servico = str(row["TIPO SERVIÇO"]).strip()

    if tipo_servico == "" or tipo_servico.lower() == "nan":
        tipo_servico = "SEM TIPO"

    cur.execute("""
        INSERT INTO manutencoes (
            data, numero_frota, bau, tipo_veiculo,
            tipo_servico, tipo_atendimento,
            tipo_manutencao, status, observacao
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        data,  # deixa como datetime (melhor)
        str(row["Nº FROTA"]).strip(),
        str(row["BAU"]).strip(),
        str(row["TIPO VEICULO"]).strip(),
        tipo_servico,
        str(row["TIPO ATENDIMENTO"]).strip(),
        str(row["TIPO MANUTENÇÃO"]).strip(),
        str(row["STATUS"]).strip(),
        str(row["OBSERVAÇÃO"]).strip()
    ))

    contador += 1

conn.commit()
cur.close()
conn.close()

print("TOTAL INSERIDO:", contador)