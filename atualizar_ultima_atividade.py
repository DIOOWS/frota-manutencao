from pathlib import Path
import sqlite3


PASTA_PROJETO = Path(__file__).resolve().parent


def atualizar_banco(caminho_banco: Path) -> bool:
    conexao = None

    try:
        conexao = sqlite3.connect(str(caminho_banco))
        cursor = conexao.cursor()

        tabelas = {
            linha[0]
            for linha in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        if "usuarios" not in tabelas:
            return False

        colunas = {
            linha[1]
            for linha in cursor.execute(
                "PRAGMA table_info(usuarios)"
            ).fetchall()
        }

        if "ultima_atividade" not in colunas:
            cursor.execute(
                """
                ALTER TABLE usuarios
                ADD COLUMN ultima_atividade DATETIME
                """
            )
            print(f"[OK] Coluna criada em: {caminho_banco}")
        else:
            print(f"[OK] Coluna já existe em: {caminho_banco}")

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_usuarios_ultima_atividade
            ON usuarios (ultima_atividade)
            """
        )

        conexao.commit()
        print(f"[OK] Índice verificado em: {caminho_banco}")
        return True

    except sqlite3.Error as erro:
        print(f"[ERRO] {caminho_banco}: {erro}")
        return False

    finally:
        if conexao:
            conexao.close()


def main():
    bancos = list(PASTA_PROJETO.rglob("*.db"))

    if not bancos:
        print("Nenhum arquivo .db encontrado no projeto.")
        return

    encontrados = 0

    for banco in bancos:
        if atualizar_banco(banco):
            encontrados += 1

    if encontrados == 0:
        print("Nenhum banco com a tabela 'usuarios' foi encontrado.")
        return

    print()
    print("Atualização concluída com sucesso.")
    print(f"Bancos atualizados: {encontrados}")


if __name__ == "__main__":
    main()