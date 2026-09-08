import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("instance") / "dev.db"

print(f"Banco usado: {DB_PATH.resolve()}")
con = sqlite3.connect(DB_PATH)
cur = con.cursor()

def tabela_existe(nome):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nome,))
    return cur.fetchone() is not None

def coluna_existe(tabela, coluna):
    if not tabela_existe(tabela):
        return False
    cur.execute(f"PRAGMA table_info({tabela})")
    return coluna in [row[1] for row in cur.fetchall()]

def add_col(tabela, coluna, tipo):
    if not tabela_existe(tabela):
        print(f"ATENÇÃO: tabela não existe: {tabela}")
        return
    if coluna_existe(tabela, coluna):
        print(f"OK já existe: {tabela}.{coluna}")
        return
    cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    print(f"Adicionado: {tabela}.{coluna}")

def exec_safe(sql, msg):
    try:
        cur.execute(sql)
        print(msg)
    except Exception as e:
        print(f"AVISO: {msg}: {e}")

# Imagens por campo pai
add_col("evidencias_imagens", "campo_pai_id", "INTEGER")
add_col("evidencias_imagens", "tipo_foto", "VARCHAR(80)")

# Tipos de foto
cur.execute("""
CREATE TABLE IF NOT EXISTS evidencias_tipos_foto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(80) NOT NULL UNIQUE,
    ativo BOOLEAN DEFAULT 1,
    ordem INTEGER DEFAULT 0,
    criado_em TIMESTAMP
)
""")

# Tabelas principais
cur.execute("""
CREATE TABLE IF NOT EXISTS evidencias_tabelas_controle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campo_pai_id INTEGER NOT NULL UNIQUE,
    titulo VARCHAR(180),
    ativo BOOLEAN DEFAULT 1,
    criado_em TIMESTAMP,
    atualizado_em TIMESTAMP
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS evidencias_tabelas_colunas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabela_id INTEGER NOT NULL,
    nome VARCHAR(120),
    grupo VARCHAR(180),
    tipo VARCHAR(40) DEFAULT 'texto',
    cor VARCHAR(40) DEFAULT 'padrao',
    largura INTEGER DEFAULT 140,
    ordem INTEGER DEFAULT 0,
    criado_em TIMESTAMP
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS evidencias_tabelas_linhas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabela_id INTEGER NOT NULL,
    rotulo VARCHAR(120),
    ordem INTEGER DEFAULT 0,
    criado_em TIMESTAMP
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS evidencias_tabelas_celulas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabela_id INTEGER,
    linha_id INTEGER NOT NULL,
    coluna_id INTEGER NOT NULL,
    valor TEXT,
    cor VARCHAR(40),
    alinhamento VARCHAR(20) DEFAULT 'center',
    atualizado_em TIMESTAMP
)
""")

# Completa bancos antigos que já tinham as tabelas incompletas
add_col("evidencias_tabelas_controle", "ativo", "BOOLEAN DEFAULT 1")
add_col("evidencias_tabelas_controle", "criado_em", "TIMESTAMP")
add_col("evidencias_tabelas_controle", "atualizado_em", "TIMESTAMP")

add_col("evidencias_tabelas_colunas", "grupo", "VARCHAR(180)")
add_col("evidencias_tabelas_colunas", "tipo", "VARCHAR(40) DEFAULT 'texto'")
add_col("evidencias_tabelas_colunas", "cor", "VARCHAR(40) DEFAULT 'padrao'")
add_col("evidencias_tabelas_colunas", "largura", "INTEGER DEFAULT 140")
add_col("evidencias_tabelas_colunas", "ordem", "INTEGER DEFAULT 0")
add_col("evidencias_tabelas_colunas", "criado_em", "TIMESTAMP")

add_col("evidencias_tabelas_linhas", "rotulo", "VARCHAR(120)")
add_col("evidencias_tabelas_linhas", "ordem", "INTEGER DEFAULT 0")
add_col("evidencias_tabelas_linhas", "criado_em", "TIMESTAMP")

add_col("evidencias_tabelas_celulas", "tabela_id", "INTEGER")
add_col("evidencias_tabelas_celulas", "cor", "VARCHAR(40)")
add_col("evidencias_tabelas_celulas", "alinhamento", "VARCHAR(20) DEFAULT 'center'")
add_col("evidencias_tabelas_celulas", "atualizado_em", "TIMESTAMP")

# Corrige registros antigos
agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if tabela_existe("evidencias_imagens") and coluna_existe("evidencias_imagens", "campo_pai_id") and tabela_existe("evidencias_campos_filho"):
    cur.execute("""
        UPDATE evidencias_imagens
        SET campo_pai_id = (
            SELECT evidencias_campos_filho.campo_pai_id
            FROM evidencias_campos_filho
            WHERE evidencias_campos_filho.id = evidencias_imagens.campo_filho_id
        )
        WHERE campo_pai_id IS NULL
          AND campo_filho_id IS NOT NULL
    """)
    cur.execute("""
        UPDATE evidencias_imagens
        SET tipo_foto = COALESCE(tipo_foto, (
            SELECT evidencias_campos_filho.nome
            FROM evidencias_campos_filho
            WHERE evidencias_campos_filho.id = evidencias_imagens.campo_filho_id
        ))
        WHERE tipo_foto IS NULL
          AND campo_filho_id IS NOT NULL
    """)
    print("Imagens antigas vinculadas ao campo pai.")

if tabela_existe("evidencias_tabelas_celulas") and coluna_existe("evidencias_tabelas_celulas", "tabela_id") and tabela_existe("evidencias_tabelas_linhas"):
    cur.execute("""
        UPDATE evidencias_tabelas_celulas
        SET tabela_id = (
            SELECT evidencias_tabelas_linhas.tabela_id
            FROM evidencias_tabelas_linhas
            WHERE evidencias_tabelas_linhas.id = evidencias_tabelas_celulas.linha_id
        )
        WHERE tabela_id IS NULL
          AND linha_id IS NOT NULL
    """)
    print("Células antigas vinculadas com tabela_id.")

for tabela in ["evidencias_tabelas_controle", "evidencias_tabelas_colunas", "evidencias_tabelas_linhas", "evidencias_tabelas_celulas"]:
    if tabela_existe(tabela):
        if coluna_existe(tabela, "criado_em"):
            cur.execute(f"UPDATE {tabela} SET criado_em = COALESCE(criado_em, ?)", (agora,))
        if coluna_existe(tabela, "atualizado_em"):
            cur.execute(f"UPDATE {tabela} SET atualizado_em = COALESCE(atualizado_em, ?)", (agora,))

con.commit()
con.close()
print("Migração V9.13 completa concluída com sucesso.")
