import sqlite3

conn = sqlite3.connect("instance/dev.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS planejamento_financeiro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_id INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    ano INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PLANEJADA',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_planejamento_financeiro_conta_mes_ano
ON planejamento_financeiro (conta_id, mes, ano)
""")

conn.commit()
conn.close()

print("Tabela criada com sucesso!")