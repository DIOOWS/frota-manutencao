import os
import sqlite3
from pathlib import Path

POSSIVEIS_BANCOS = [
    "dev.db",
    "easy_control.db",
    "frota_manutencao.db",
    os.path.join("instance", "dev.db"),
    os.path.join("instance", "easy_control.db"),
]


def achar_banco():
    for caminho in POSSIVEIS_BANCOS:
        if os.path.exists(caminho):
            return caminho
    raise FileNotFoundError(
        "Nao encontrei o banco SQLite. Edite a variavel DB_PATH no final do arquivo com o caminho correto."
    )


def colunas(conn, tabela):
    return {row[1]: row for row in conn.execute(f"PRAGMA table_info({tabela})").fetchall()}


def tabela_existe(conn, tabela):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,)
    ).fetchone()
    return row is not None


def migrar(DB_PATH=None):
    db_path = DB_PATH or achar_banco()
    print(f"Usando banco: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")

        if not tabela_existe(conn, "evidencias_imagens"):
            raise RuntimeError("Tabela evidencias_imagens nao existe nesse banco.")

        # Tabela do dropdown de tipos de foto
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evidencias_tipos_foto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(80) NOT NULL UNIQUE,
                ativo BOOLEAN DEFAULT 1,
                ordem INTEGER DEFAULT 0,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        tipos_padrao = [
            "Antes",
            "Depois",
            "Durante",
            "Finalizado",
            "Avaria",
            "Componente removido",
            "Componente instalado",
            "Etiqueta",
            "Comprovante",
            "Outro",
        ]
        for ordem, nome in enumerate(tipos_padrao, start=1):
            conn.execute(
                """
                INSERT OR IGNORE INTO evidencias_tipos_foto (nome, ativo, ordem)
                VALUES (?, 1, ?)
                """,
                (nome, ordem),
            )

        cols = colunas(conn, "evidencias_imagens")
        precisa_recriar = False

        if "campo_pai_id" not in cols or "tipo_foto" not in cols:
            precisa_recriar = True

        # No SQLite, notnull=1 significa NOT NULL. Para upload direto no pai,
        # campo_filho_id precisa aceitar NULL.
        if "campo_filho_id" in cols and cols["campo_filho_id"][3] == 1:
            precisa_recriar = True

        if precisa_recriar:
            print("Recriando evidencias_imagens com estrutura V7...")

            conn.execute("DROP TABLE IF EXISTS evidencias_imagens_old_v7")
            conn.execute("ALTER TABLE evidencias_imagens RENAME TO evidencias_imagens_old_v7")

            conn.execute(
                """
                CREATE TABLE evidencias_imagens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campo_filho_id INTEGER NULL,
                    campo_pai_id INTEGER NULL,
                    tipo_foto VARCHAR(80) NULL,
                    imagem_url TEXT NOT NULL,
                    public_id VARCHAR(255) NULL,
                    caminho_local VARCHAR(500) NULL,
                    nome_original VARCHAR(255) NULL,
                    legenda VARCHAR(255) NULL,
                    ordem INTEGER DEFAULT 0,
                    enviado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(campo_filho_id) REFERENCES evidencias_campos_filho(id) ON DELETE SET NULL,
                    FOREIGN KEY(campo_pai_id) REFERENCES evidencias_campos_pai(id) ON DELETE CASCADE
                )
                """
            )

            old_cols = colunas(conn, "evidencias_imagens_old_v7")
            campo_pai_expr = "(SELECT f.campo_pai_id FROM evidencias_campos_filho f WHERE f.id = old.campo_filho_id)"
            if "campo_pai_id" in old_cols:
                campo_pai_expr = f"COALESCE(old.campo_pai_id, {campo_pai_expr})"

            tipo_expr = "COALESCE((SELECT f.nome FROM evidencias_campos_filho f WHERE f.id = old.campo_filho_id), 'Outro')"
            if "tipo_foto" in old_cols:
                tipo_expr = f"COALESCE(NULLIF(old.tipo_foto, ''), {tipo_expr})"

            conn.execute(
                f"""
                INSERT INTO evidencias_imagens (
                    id,
                    campo_filho_id,
                    campo_pai_id,
                    tipo_foto,
                    imagem_url,
                    public_id,
                    caminho_local,
                    nome_original,
                    legenda,
                    ordem,
                    enviado_em
                )
                SELECT
                    old.id,
                    old.campo_filho_id,
                    {campo_pai_expr} AS campo_pai_id,
                    {tipo_expr} AS tipo_foto,
                    old.imagem_url,
                    old.public_id,
                    old.caminho_local,
                    old.nome_original,
                    old.legenda,
                    old.ordem,
                    old.enviado_em
                FROM evidencias_imagens_old_v7 old
                """
            )

            conn.execute("DROP TABLE evidencias_imagens_old_v7")
        else:
            print("Estrutura ja possui campo_pai_id/tipo_foto. Atualizando dados antigos...")
            conn.execute(
                """
                UPDATE evidencias_imagens
                SET campo_pai_id = (
                    SELECT f.campo_pai_id
                    FROM evidencias_campos_filho f
                    WHERE f.id = evidencias_imagens.campo_filho_id
                )
                WHERE campo_pai_id IS NULL
                  AND campo_filho_id IS NOT NULL
                """
            )
            conn.execute(
                """
                UPDATE evidencias_imagens
                SET tipo_foto = COALESCE((
                    SELECT f.nome
                    FROM evidencias_campos_filho f
                    WHERE f.id = evidencias_imagens.campo_filho_id
                ), 'Outro')
                WHERE (tipo_foto IS NULL OR tipo_foto = '')
                  AND campo_filho_id IS NOT NULL
                """
            )

        conn.execute("CREATE INDEX IF NOT EXISTS ix_evidencias_imagens_campo_pai_id ON evidencias_imagens(campo_pai_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_evidencias_imagens_campo_filho_id ON evidencias_imagens(campo_filho_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_evidencias_imagens_tipo_foto ON evidencias_imagens(tipo_foto)")

        conn.commit()
        print("Migracao V7 concluida com sucesso. Suas fotos antigas foram preservadas.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # Se o script nao encontrar o banco automaticamente, coloque o caminho aqui.
    # Exemplo: migrar(r"C:\\Users\\EASY\\Desktop\\frota-manutencao\\dev.db")
    migrar()
