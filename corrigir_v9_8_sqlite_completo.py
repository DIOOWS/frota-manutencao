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

def adicionar_coluna(tabela, coluna, tipo):
    if not tabela_existe(tabela):
        print(f"ATENÇÃO: tabela não existe: {tabela}")
        return

    if coluna_existe(tabela, coluna):
        print(f"OK já existe: {tabela}.{coluna}")
        return

    cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    print(f"Adicionado: {tabela}.{coluna}")

# Completa colunas da tabela de controle
adicionar_coluna("evidencias_tabelas_controle", "ativo", "BOOLEAN DEFAULT 1")
adicionar_coluna("evidencias_tabelas_controle", "criado_em", "TIMESTAMP")
adicionar_coluna("evidencias_tabelas_controle", "atualizado_em", "TIMESTAMP")

# Completa colunas
adicionar_coluna("evidencias_tabelas_colunas", "largura", "INTEGER DEFAULT 140")
adicionar_coluna("evidencias_tabelas_colunas", "cor", "VARCHAR(40) DEFAULT 'padrao'")
adicionar_coluna("evidencias_tabelas_colunas", "alinhamento", "VARCHAR(20) DEFAULT 'center'")
adicionar_coluna("evidencias_tabelas_colunas", "grupo", "VARCHAR(180)")
adicionar_coluna("evidencias_tabelas_colunas", "ordem", "INTEGER DEFAULT 0")

# Completa linhas
adicionar_coluna("evidencias_tabelas_linhas", "ordem", "INTEGER DEFAULT 0")

# Completa células
adicionar_coluna("evidencias_tabelas_celulas", "tabela_id", "INTEGER")
adicionar_coluna("evidencias_tabelas_celulas", "cor", "VARCHAR(40)")
adicionar_coluna("evidencias_tabelas_celulas", "alinhamento", "VARCHAR(20) DEFAULT 'left'")
adicionar_coluna("evidencias_tabelas_celulas", "atualizado_em", "TIMESTAMP")

# Preenche tabela_id nas células antigas usando a linha
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

# Preenche datas vazias
agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if tabela_existe("evidencias_tabelas_controle"):
    if coluna_existe("evidencias_tabelas_controle", "criado_em"):
        cur.execute("UPDATE evidencias_tabelas_controle SET criado_em = COALESCE(criado_em, ?)", (agora,))
    if coluna_existe("evidencias_tabelas_controle", "atualizado_em"):
        cur.execute("UPDATE evidencias_tabelas_controle SET atualizado_em = COALESCE(atualizado_em, ?)", (agora,))

if tabela_existe("evidencias_tabelas_celulas") and coluna_existe("evidencias_tabelas_celulas", "atualizado_em"):
    cur.execute("UPDATE evidencias_tabelas_celulas SET atualizado_em = COALESCE(atualizado_em, ?)", (agora,))

con.commit()
con.close()

print("Migração complementar V9.8 concluída com sucesso.")
