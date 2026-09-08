import sqlite3
from pathlib import Path
from datetime import datetime

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

def add(tabela, coluna, tipo):
    if not tabela_existe(tabela):
        print(f"ATENÇÃO: tabela não existe: {tabela}")
        return
    if coluna_existe(tabela, coluna):
        print(f"OK já existe: {tabela}.{coluna}")
        return
    cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    print(f"Adicionado: {tabela}.{coluna}")

add("evidencias_tabelas_controle", "ativo", "BOOLEAN DEFAULT 1")
add("evidencias_tabelas_controle", "criado_em", "TIMESTAMP")
add("evidencias_tabelas_controle", "atualizado_em", "TIMESTAMP")
add("evidencias_tabelas_colunas", "largura", "INTEGER DEFAULT 140")
add("evidencias_tabelas_colunas", "cor", "VARCHAR(40) DEFAULT 'padrao'")
add("evidencias_tabelas_colunas", "alinhamento", "VARCHAR(20) DEFAULT 'center'")
add("evidencias_tabelas_colunas", "grupo", "VARCHAR(180)")
add("evidencias_tabelas_colunas", "ordem", "INTEGER DEFAULT 0")
add("evidencias_tabelas_colunas", "tipo", "VARCHAR(40) DEFAULT 'texto'")
add("evidencias_tabelas_linhas", "ordem", "INTEGER DEFAULT 0")
add("evidencias_tabelas_celulas", "tabela_id", "INTEGER")
add("evidencias_tabelas_celulas", "cor", "VARCHAR(40)")
add("evidencias_tabelas_celulas", "alinhamento", "VARCHAR(20) DEFAULT 'center'")
add("evidencias_tabelas_celulas", "atualizado_em", "TIMESTAMP")

if tabela_existe("evidencias_tabelas_celulas") and coluna_existe("evidencias_tabelas_celulas", "tabela_id"):
    cur.execute("""
        UPDATE evidencias_tabelas_celulas
        SET tabela_id = (
            SELECT evidencias_tabelas_linhas.tabela_id
            FROM evidencias_tabelas_linhas
            WHERE evidencias_tabelas_linhas.id = evidencias_tabelas_celulas.linha_id
        )
        WHERE tabela_id IS NULL
    """)
    print("Células antigas vinculadas com tabela_id.")

agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
for tabela in ["evidencias_tabelas_controle", "evidencias_tabelas_celulas"]:
    if tabela_existe(tabela) and coluna_existe(tabela, "atualizado_em"):
        cur.execute(f"UPDATE {tabela} SET atualizado_em = COALESCE(atualizado_em, ?)", (agora,))
    if tabela_existe(tabela) and coluna_existe(tabela, "criado_em"):
        cur.execute(f"UPDATE {tabela} SET criado_em = COALESCE(criado_em, ?)", (agora,))

con.commit()
con.close()
print("Migração complementar V9.9 concluída com sucesso.")
