import pandas as pd
from app import app, db
from models import Manutencao

df = pd.read_excel("dados.xlsx")

df.columns = df.columns.str.strip()
df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce")
df = df.where(pd.notnull(df), None)
df = df.dropna(how='all')

with app.app_context():

    # 🔥 limpa tabela
    db.session.query(Manutencao).delete()
    db.session.commit()

    total = 0

    for _, row in df.iterrows():

        # 🚨 IGNORA LINHAS SUJAS
        if pd.isna(row["DATA"]) or pd.isna(row["Nº FROTA"]):
            continue

        nova = Manutencao(
            data=row["DATA"],
            numero_frota=str(int(row["Nº FROTA"])),  # 🔥 remove .0
            bau=row["BAU"],
            tipo_veiculo=row["TIPO VEICULO"],
            tipo_servico=row["TIPO SERVIÇO"],
            tipo_atendimento=row["TIPO ATENDIMENTO"],
            tipo_manutencao=row["TIPO MANUTENÇÃO"],
            status=row["STATUS"],
            observacao=row["OBSERVAÇÃO"],
            cliente=str(row["CLIENTE"]).strip() if row["CLIENTE"] else None
        )

        db.session.add(nova)

        db.session.add(nova)
        total += 1

    db.session.commit()

print("🔥 TOTAL INSERIDO:", total)