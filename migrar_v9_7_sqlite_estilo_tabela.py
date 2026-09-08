import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CANDIDATOS = [
    os.path.join(BASE_DIR, "instance", "dev.db"),
    os.path.join(BASE_DIR, "dev.db"),
    os.path.join(BASE_DIR, "frota.db"),
]

def escolher_banco():
    for caminho in CANDIDATOS:
        if os.path.exists(caminho):
            return caminho
    raise FileNotFoundError("Não encontrei instance/dev.db, dev.db ou frota.db")

def coluna_existe(cur, tabela, coluna):
    cur.execute(f"PRAGMA table_info({tabela})")
    return coluna in [row[1] for row in cur.fetchall()]

banco = escolher_banco()
backup = banco.replace('.db', f'_backup_antes_v9_7_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
with open(banco, 'rb') as src, open(backup, 'wb') as dst:
    dst.write(src.read())

conn = sqlite3.connect(banco)
cur = conn.cursor()

# Estilo das células
if not coluna_existe(cur, 'evidencias_tabelas_celulas', 'cor'):
    cur.execute("ALTER TABLE evidencias_tabelas_celulas ADD COLUMN cor VARCHAR(40)")
if not coluna_existe(cur, 'evidencias_tabelas_celulas', 'alinhamento'):
    cur.execute("ALTER TABLE evidencias_tabelas_celulas ADD COLUMN alinhamento VARCHAR(20) DEFAULT 'center'")

# Largura das colunas, caso ainda não exista no seu banco local
if not coluna_existe(cur, 'evidencias_tabelas_colunas', 'largura'):
    cur.execute("ALTER TABLE evidencias_tabelas_colunas ADD COLUMN largura INTEGER DEFAULT 140")

conn.commit()
conn.close()
print('Banco usado:', banco)
print('Backup criado:', backup)
print('Migração V9.7 concluída.')
