from sqlalchemy import inspect, text

from app import app
from database import db


COLUNAS_V2 = {
    "chave_conta": "VARCHAR(64)",
    "descricao_snapshot": "VARCHAR(255)",
    "fornecedor_snapshot": "VARCHAR(255)",
    "valor_snapshot": "NUMERIC(14, 2)",
    "vencimento_snapshot": "DATE",
    "observacao_snapshot": "TEXT",
    "updated_at": "DATETIME",
}


def executar_migracao():
    with app.app_context():
        inspector = inspect(db.engine)

        tabelas = inspector.get_table_names()

        if "planejamento_financeiro" not in tabelas:
            raise RuntimeError(
                "A tabela planejamento_financeiro não existe no banco local."
            )

        colunas_existentes = {
            coluna["name"]
            for coluna in inspector.get_columns("planejamento_financeiro")
        }

        with db.engine.begin() as conexao:
            for nome_coluna, tipo_coluna in COLUNAS_V2.items():
                if nome_coluna in colunas_existentes:
                    print(f"[OK] Coluna já existe: {nome_coluna}")
                    continue

                conexao.execute(
                    text(
                        f"""
                        ALTER TABLE planejamento_financeiro
                        ADD COLUMN {nome_coluna} {tipo_coluna}
                        """
                    )
                )

                print(f"[CRIADA] {nome_coluna}")

            conexao.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_planejamento_chave_competencia
                    ON planejamento_financeiro (
                        chave_conta,
                        origem,
                        mes,
                        ano
                    )
                    """
                )
            )

            conexao.execute(
                text(
                    """
                    UPDATE planejamento_financeiro
                    SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)
                    WHERE updated_at IS NULL
                    """
                )
            )

        print("\nMigração local da V2 concluída com sucesso.")


if __name__ == "__main__":
    executar_migracao()