from app import app
from database import db
from sqlalchemy import text

with app.app_context():
    print("BANCO USADO:", db.engine.url)

    with db.engine.begin() as conn:
        colunas = conn.execute(
            text("PRAGMA table_info(faturamento_comercial)")
        ).fetchall()

        nomes = [coluna[1] for coluna in colunas]

        print("COLUNAS ANTES:")
        print(nomes)

        if "chave_conciliacao" not in nomes:
            conn.execute(text(
                "ALTER TABLE faturamento_comercial ADD COLUMN chave_conciliacao TEXT"
            ))
            print("Coluna chave_conciliacao criada.")

        if "origem_registro" not in nomes:
            conn.execute(text(
                "ALTER TABLE faturamento_comercial ADD COLUMN origem_registro TEXT DEFAULT 'MANUAL'"
            ))
            print("Coluna origem_registro criada.")

        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_faturamento_comercial_chave_conciliacao "
            "ON faturamento_comercial(chave_conciliacao)"
        ))

        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_faturamento_comercial_origem_registro "
            "ON faturamento_comercial(origem_registro)"
        ))

        colunas = conn.execute(
            text("PRAGMA table_info(faturamento_comercial)")
        ).fetchall()

        nomes = [coluna[1] for coluna in colunas]

        print("COLUNAS DEPOIS:")
        print(nomes)

print("Banco corrigido com sucesso.")