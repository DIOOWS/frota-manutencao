from pathlib import Path
import sqlite3
import shutil
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
BANCO = BASE_DIR / "instance" / "dev.db"

TIPOS_PADRAO = [
    "Antes",
    "Depois",
    "Durante",
    "Finalizado",
    "Avaria",
    "Instalado",
    "Removido",
    "Etiqueta",
    "Comprovante",
    "Outro",
]


def coluna_existe(cursor, tabela, coluna):
    cursor.execute(f"PRAGMA table_info({tabela})")
    return any(row[1] == coluna for row in cursor.fetchall())


def tabela_existe(cursor, tabela):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (tabela,),
    )
    return cursor.fetchone() is not None


def adicionar_coluna_se_nao_existir(cursor, tabela, coluna, definicao):
    if not coluna_existe(cursor, tabela, coluna):
        print(f"Adicionando coluna: {tabela}.{coluna}")
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
    else:
        print(f"Coluna já existe: {tabela}.{coluna}")


def migrar():
    print(f"Usando banco: {BANCO}")

    if not BANCO.exists():
        raise RuntimeError(f"Banco não encontrado: {BANCO}")

    backup = BANCO.with_name(
        f"dev_backup_antes_v7_auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    shutil.copy2(BANCO, backup)
    print(f"Backup criado em: {backup}")

    con = sqlite3.connect(BANCO)
    cur = con.cursor()

    if not tabela_existe(cur, "evidencias_imagens"):
        con.close()
        raise RuntimeError("Tabela evidencias_imagens não existe nesse banco.")

    if not tabela_existe(cur, "evidencias_campos_filho"):
        con.close()
        raise RuntimeError("Tabela evidencias_campos_filho não existe nesse banco.")

    if not tabela_existe(cur, "evidencias_campos_pai"):
        con.close()
        raise RuntimeError("Tabela evidencias_campos_pai não existe nesse banco.")

    adicionar_coluna_se_nao_existir(
        cur,
        "evidencias_imagens",
        "campo_pai_id",
        "INTEGER",
    )

    adicionar_coluna_se_nao_existir(
        cur,
        "evidencias_imagens",
        "tipo_foto",
        "VARCHAR(80)",
    )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS evidencias_tipos_foto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome VARCHAR(80) NOT NULL UNIQUE,
            ativo BOOLEAN DEFAULT 1,
            ordem INTEGER DEFAULT 0,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for ordem, nome in enumerate(TIPOS_PADRAO, start=1):
        cur.execute("""
            INSERT OR IGNORE INTO evidencias_tipos_foto (nome, ativo, ordem)
            VALUES (?, 1, ?)
        """, (nome, ordem))

    print("Migrando imagens antigas do filho para o pai...")

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
        SET tipo_foto = (
            SELECT evidencias_campos_filho.nome
            FROM evidencias_campos_filho
            WHERE evidencias_campos_filho.id = evidencias_imagens.campo_filho_id
        )
        WHERE (tipo_foto IS NULL OR TRIM(tipo_foto) = '')
          AND campo_filho_id IS NOT NULL
    """)

    cur.execute("""
        UPDATE evidencias_imagens
        SET tipo_foto = 'Outro'
        WHERE tipo_foto IS NULL OR TRIM(tipo_foto) = ''
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_evidencias_imagens_campo_pai_id
        ON evidencias_imagens (campo_pai_id)
    """)

    cur.execute("SELECT COUNT(*) FROM evidencias_imagens")
    total_imagens = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM evidencias_imagens WHERE campo_pai_id IS NOT NULL")
    imagens_migradas = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM evidencias_tipos_foto")
    total_tipos = cur.fetchone()[0]

    con.commit()
    con.close()

    print("Migração concluída com sucesso.")
    print(f"Imagens totais: {total_imagens}")
    print(f"Imagens com campo_pai_id: {imagens_migradas}")
    print(f"Tipos de foto cadastrados: {total_tipos}")


if __name__ == "__main__":
    migrar()