from pathlib import Path
import sqlite3
import shutil
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
BANCO = BASE_DIR / "instance" / "dev.db"
SQL = """
CREATE TABLE IF NOT EXISTS evidencias_tabelas_controle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campo_pai_id INTEGER NOT NULL,
    titulo VARCHAR(180) NOT NULL,
    ativa BOOLEAN DEFAULT 1,
    ordem INTEGER DEFAULT 0,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campo_pai_id) REFERENCES evidencias_campos_pai(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidencias_tabelas_controle_campo_pai_id
ON evidencias_tabelas_controle (campo_pai_id);
CREATE TABLE IF NOT EXISTS evidencias_tabelas_colunas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabela_id INTEGER NOT NULL,
    grupo VARCHAR(120),
    nome VARCHAR(120) NOT NULL,
    tipo VARCHAR(40) DEFAULT 'texto',
    cor VARCHAR(30) DEFAULT 'padrao',
    largura INTEGER DEFAULT 16,
    ordem INTEGER DEFAULT 0,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tabela_id) REFERENCES evidencias_tabelas_controle(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidencias_tabelas_colunas_tabela_id
ON evidencias_tabelas_colunas (tabela_id);
CREATE TABLE IF NOT EXISTS evidencias_tabelas_linhas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabela_id INTEGER NOT NULL,
    rotulo VARCHAR(120) NOT NULL,
    ordem INTEGER DEFAULT 0,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tabela_id) REFERENCES evidencias_tabelas_controle(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidencias_tabelas_linhas_tabela_id
ON evidencias_tabelas_linhas (tabela_id);
CREATE TABLE IF NOT EXISTS evidencias_tabelas_celulas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    linha_id INTEGER NOT NULL,
    coluna_id INTEGER NOT NULL,
    valor TEXT,
    atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (linha_id) REFERENCES evidencias_tabelas_linhas(id) ON DELETE CASCADE,
    FOREIGN KEY (coluna_id) REFERENCES evidencias_tabelas_colunas(id) ON DELETE CASCADE,
    CONSTRAINT uq_evidencia_celula_linha_coluna UNIQUE (linha_id, coluna_id)
);
CREATE INDEX IF NOT EXISTS idx_evidencias_tabelas_celulas_linha_id
ON evidencias_tabelas_celulas (linha_id);
CREATE INDEX IF NOT EXISTS idx_evidencias_tabelas_celulas_coluna_id
ON evidencias_tabelas_celulas (coluna_id);
"""

def tabela_existe(cur, nome):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nome,))
    return cur.fetchone() is not None

def migrar():
    print(f"Usando banco: {BANCO}")
    if not BANCO.exists():
        raise RuntimeError(f"Banco não encontrado: {BANCO}")
    backup = BANCO.with_name(f"dev_backup_antes_v8_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(BANCO, backup)
    print(f"Backup criado: {backup}")
    con = sqlite3.connect(BANCO)
    cur = con.cursor()
    if not tabela_existe(cur, "evidencias_campos_pai"):
        con.close()
        raise RuntimeError("Tabela evidencias_campos_pai não existe nesse banco.")
    cur.executescript(SQL)
    con.commit()
    for tabela in [
        "evidencias_tabelas_controle",
        "evidencias_tabelas_colunas",
        "evidencias_tabelas_linhas",
        "evidencias_tabelas_celulas",
    ]:
        cur.execute(f"SELECT COUNT(*) FROM {tabela}")
        print(f"{tabela}: {cur.fetchone()[0]} registro(s)")
    con.close()
    print("Migração V8 concluída com sucesso.")

if __name__ == "__main__":
    migrar()
