import sqlite3
from pathlib import Path

db_path = Path("instance") / "dev.db"

print(f"Banco usado: {db_path.resolve()}")

con = sqlite3.connect(db_path)
cur = con.cursor()

def tabela_existe(nome):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nome,))
    return cur.fetchone() is not None

def coluna_existe(tabela, coluna):
    cur.execute(f"PRAGMA table_info({tabela})")
    return coluna in [row[1] for row in cur.fetchall()]

def adicionar_coluna(tabela, coluna, tipo):
    if not tabela_existe(tabela):
        print(f"ATENÇÃO: tabela não existe: {tabela}")
        return

    if coluna_existe(tabela, coluna):
        print(f"OK já existe: {tabela}.{coluna}")
        return

    sql = f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}"
    cur.execute(sql)
    print(f"Adicionado: {tabela}.{coluna}")

adicionar_coluna("evidencias_tabelas_controle", "ativo", "BOOLEAN DEFAULT 1")
adicionar_coluna("evidencias_tabelas_controle", "criado_em", "TIMESTAMP")
adicionar_coluna("evidencias_tabelas_controle", "atualizado_em", "TIMESTAMP")

adicionar_coluna("evidencias_tabelas_colunas", "largura", "INTEGER DEFAULT 140")
adicionar_coluna("evidencias_tabelas_colunas", "cor", "VARCHAR(40) DEFAULT 'padrao'")
adicionar_coluna("evidencias_tabelas_colunas", "alinhamento", "VARCHAR(20) DEFAULT 'center'")
adicionar_coluna("evidencias_tabelas_colunas", "grupo", "VARCHAR(180)")
adicionar_coluna("evidencias_tabelas_colunas", "ordem", "INTEGER DEFAULT 0")

adicionar_coluna("evidencias_tabelas_linhas", "ordem", "INTEGER DEFAULT 0")

adicionar_coluna("evidencias_tabelas_celulas", "cor", "VARCHAR(40)")
adicionar_coluna("evidencias_tabelas_celulas", "alinhamento", "VARCHAR(20) DEFAULT 'left'")

con.commit()
con.close()

print("Migração complementar concluída com sucesso.")
