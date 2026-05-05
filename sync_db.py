from app import app
from database import db
from models.manutencao import Manutencao

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 🔥 BANCO PRODUÇÃO
DATABASE_URL = "postgresql://postgres.vhrkitmevkgtoudilbmo:94BmzfxfN9hxxoTP@aws-1-us-west-2.pooler.supabase.com:6543/postgres"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
prod_session = Session()

with app.app_context():

    print("🔥 Limpando banco local...")
    Manutencao.query.delete()
    db.session.commit()

    print("🔥 Buscando dados da produção...")

    dados = prod_session.query(Manutencao).all()

    print(f"🔥 Total encontrado: {len(dados)}")

    for m in dados:
        novo = Manutencao(
            data=m.data,
            numero_frota=m.numero_frota,
            bau=m.bau,
            tipo_veiculo=m.tipo_veiculo,
            tipo_servico=m.tipo_servico,
            tipo_atendimento=m.tipo_atendimento,
            tipo_manutencao=m.tipo_manutencao,
            status=m.status,
            observacao=m.observacao,
            cliente=m.cliente,
            os=m.os,
        )

        db.session.add(novo)

    db.session.commit()

    print("🔥 SINCRONIZAÇÃO FINALIZADA")