import calendar
import hmac
import secrets

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from sqlalchemy import func, or_

from database import db

from models.painel_tv import PainelTVConfig
from models.faturamento_comercial import FaturamentoComercial
from models.conta_pagar_importada import ContaPagarImportada
from models.conta_receber_importada import ContaReceberImportada
from models.manutencao import Manutencao


painel_tv_bp = Blueprint(
    "painel_tv",
    __name__,
    url_prefix="/gestao/painel-tv",
)

QUITADOS = (
    "PAGO",
    "RECEBIDO",
    "NOTAS PAGAS",
    "OK",
    "QUITADO",
    "BAIXADO",
)

CANCELADOS = (
    "CANCELADO",
    "CANCELADA",
    "TRANSPORTADO",
)

MESES = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)


# =========================================================
# ACESSO E DATAS
# =========================================================

def hoje_brasil():
    return datetime.now(
        timezone(timedelta(hours=-3))
    ).date()


def acesso_tv(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.endswith("/dados"):
                return jsonify(
                    erro="Sessão encerrada. Faça login novamente."
                ), 401

            return redirect(url_for("auth.login"))

        # Mesma política de acesso do Financeiro.
        if session.get("user_role") not in ("gestao", "gestor"):
            abort(403)

        return funcao(*args, **kwargs)

    return wrapper


@painel_tv_bp.after_request
def sem_cache(response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response


def periodo(valor=None):
    hoje = hoje_brasil()

    if not valor:
        return hoje.replace(day=1)

    try:
        data = datetime.strptime(valor, "%Y-%m").date()

        if len(valor) != 7 or not 2000 <= data.year <= 2100:
            raise ValueError()

        return data

    except (ValueError, TypeError):
        abort(
            400,
            "Competência inválida. Use AAAA-MM.",
        )


# =========================================================
# HELPERS DOS INDICADORES
# =========================================================

def normalizado(coluna):
    return func.upper(
        func.trim(
            func.coalesce(coluna, "")
        )
    )


def aberto(model):
    return db.and_(
        or_(
            model.pago.is_(False),
            model.pago.is_(None),
        ),
        normalizado(model.status).notin_(
            QUITADOS + CANCELADOS
        ),
    )


def numero(valor):
    return float(valor or 0)


def valor_receber():
    # Usa total com juros quando preenchido; senão, valor.
    return func.coalesce(
        func.nullif(ContaReceberImportada.total, 0),
        ContaReceberImportada.valor,
        0,
    )


def resumo(query, coluna_valor):
    total, quantidade = query.with_entities(
        func.coalesce(func.sum(coluna_valor), 0),
        func.count(),
    ).one()

    return {
        "total": numero(total),
        "quantidade": quantidade,
    }


# =========================================================
# DADOS AUTOMÁTICOS DO PAINEL
# =========================================================

def montar_dados(inicio):
    fim = date(
        inicio.year,
        inicio.month,
        calendar.monthrange(
            inicio.year,
            inicio.month,
        )[1],
    )

    inicio_dt = datetime.combine(
        inicio,
        datetime.min.time(),
    )

    fim_dt = datetime.combine(
        fim,
        datetime.max.time(),
    )

    hoje = hoje_brasil()

    hoje_inicio = datetime.combine(
        hoje,
        datetime.min.time(),
    )

    hoje_fim = datetime.combine(
        hoje,
        datetime.max.time(),
    )

    competencia = inicio.strftime("%Y-%m")

    config = PainelTVConfig.query.filter_by(
        competencia=competencia
    ).first()

    # -----------------------------------------------------
    # FATURAMENTO COMERCIAL
    # -----------------------------------------------------

    faturamento_query = FaturamentoComercial.query.filter(
        FaturamentoComercial.mes == inicio.month,
        FaturamentoComercial.ano == inicio.year,
        normalizado(
            FaturamentoComercial.status
        ).notin_(CANCELADOS),
    )

    faturamento = resumo(
        faturamento_query,
        FaturamentoComercial.valor,
    )

    # -----------------------------------------------------
    # CONTAS A PAGAR E A RECEBER
    # -----------------------------------------------------

    # Não soma registros PAGAMENTO novamente:
    # eles podem representar obrigações já existentes
    # em DESPESA_COMPLETA.
    pagar = ContaPagarImportada.query.filter(
        ContaPagarImportada.origem_importacao
        == "DESPESA_COMPLETA",
        aberto(ContaPagarImportada),
    )

    receber = ContaReceberImportada.query.filter(
        ContaReceberImportada.origem_importacao
        == "RECEBIMENTO",
        aberto(ContaReceberImportada),
    )

    pagar_mes = pagar.filter(
        ContaPagarImportada.data_vencimento.between(
            inicio_dt,
            fim_dt,
        )
    )

    receber_mes = receber.filter(
        ContaReceberImportada.data_vencimento.between(
            inicio_dt,
            fim_dt,
        )
    )

    vencem_hoje = pagar.filter(
        ContaPagarImportada.data_vencimento.between(
            hoje_inicio,
            hoje_fim,
        )
    )

    atrasadas = pagar.filter(
        ContaPagarImportada.data_vencimento
        < hoje_inicio
    )

    entradas_hoje = receber.filter(
        ContaReceberImportada.data_vencimento.between(
            hoje_inicio,
            hoje_fim,
        )
    )

    # -----------------------------------------------------
    # LISTA DE VENCIMENTOS PARA EXIBIÇÃO
    # -----------------------------------------------------

    contas = []

    fontes = (
        (
            pagar,
            ContaPagarImportada,
            "pagar",
        ),
        (
            receber,
            ContaReceberImportada,
            "receber",
        ),
    )

    for query, model, tipo in fontes:
        registros = query.filter(
            or_(
                model.data_vencimento <= fim_dt,
                model.data_vencimento.is_(None),
            )
        ).order_by(
            model.data_vencimento.asc().nullslast(),
            model.id.asc(),
        ).limit(24).all()

        for conta in registros:
            if tipo == "pagar":
                nome = conta.fornecedor_funcionario
                valor = conta.valor
            else:
                nome = conta.cliente
                valor = conta.total or conta.valor

            vencimento = None

            if conta.data_vencimento:
                vencimento = (
                    conta.data_vencimento
                    .date()
                    .isoformat()
                )

            contas.append({
                "id": f"{tipo}-{conta.id}",
                "tipo": tipo,
                "nome": nome or "Sem descrição",
                "vencimento": vencimento,
                "valor": numero(valor),
            })

    contas.sort(
        key=lambda item: (
            item["vencimento"] or "9999-12-31",
            item["id"],
        )
    )

    # -----------------------------------------------------
    # MANUTENÇÕES / OPERAÇÃO
    # -----------------------------------------------------

    status_manutencao = normalizado(
        Manutencao.status
    )

    finalizadas = Manutencao.query.filter(
        status_manutencao.like("%FINALIZADO%"),
        Manutencao.data_saida.between(
            inicio,
            fim,
        ),
    )

    servicos = finalizadas.count()

    entradas = Manutencao.query.filter(
        Manutencao.data.between(
            inicio,
            fim,
        )
    ).count()

    andamento = Manutencao.query.filter(
        status_manutencao.like("%ANDAMENTO%")
    ).count()

    ultimas = finalizadas.order_by(
        Manutencao.data_saida.desc(),
        Manutencao.id.desc(),
    ).limit(8).all()

    media_tma = finalizadas.with_entities(
        func.avg(
            func.coalesce(Manutencao.dtm, 0)
        )
    ).filter(
        Manutencao.dtm > 0
    ).scalar()

    sem_vencimento = (
        pagar.filter(
            ContaPagarImportada.data_vencimento.is_(None)
        ).count()
        +
        receber.filter(
            ContaReceberImportada.data_vencimento.is_(None)
        ).count()
    )

    avisos_texto = config.avisos if config else ""

    avisos = [
        linha.strip()
        for linha in avisos_texto.splitlines()
        if linha.strip()
    ]

    # -----------------------------------------------------
    # RESPOSTA PARA A TELA
    # -----------------------------------------------------

    return {
        "competencia": competencia,

        "periodo": (
            f"{MESES[inicio.month - 1]} "
            f"{inicio.year}"
        ),

        "hoje": hoje.isoformat(),

        "atualizado_em": datetime.now(
            timezone.utc
        ).isoformat(),

        "empresa": (
            config.empresa
            if config
            else "EASY ASSISTÊNCIA"
        ),

        "meta_faturamento": (
            numero(config.meta_faturamento)
            if config
            else 0
        ),

        "meta_servicos": (
            config.meta_servicos
            if config
            else 0
        ),

        "segundos_tela": (
            config.segundos_tela
            if config
            else 15
        ),

        "avisos": avisos,

        "faturamento": faturamento,

        "pagar_mes": resumo(
            pagar_mes,
            ContaPagarImportada.valor,
        ),

        "receber_mes": resumo(
            receber_mes,
            valor_receber(),
        ),

        "vence_hoje": resumo(
            vencem_hoje,
            ContaPagarImportada.valor,
        ),

        "atrasadas": resumo(
            atrasadas,
            ContaPagarImportada.valor,
        ),

        "recebimentos_hoje": resumo(
            entradas_hoje,
            valor_receber(),
        ),

        "sem_vencimento": sem_vencimento,

        "contas": contas,

        "operacao": {
            "finalizadas": servicos,
            "entradas": entradas,
            "andamento": andamento,

            "tma": (
                round(float(media_tma), 1)
                if media_tma is not None
                else None
            ),

            "ultimas": [
                {
                    "frota": (
                        manutencao.numero_frota
                        or "Sem frota"
                    ),
                    "cliente": (
                        manutencao.cliente
                        or "-"
                    ),
                    "data": (
                        manutencao.data_saida.isoformat()
                    ),
                }
                for manutencao in ultimas
            ],
        },

        "fontes": {
            "faturamento": (
                "Faturamento Comercial • competência do mês"
            ),
            "pagar": (
                "Radar • Despesas Completo"
            ),
            "receber": (
                "Contas a Receber • origem RECEBIMENTO"
            ),
            "servicos": (
                "Manutenções • FINALIZADO com saída no mês"
            ),
        },
    }


# =========================================================
# TELA DO PAINEL
# =========================================================

@painel_tv_bp.route("/")
@acesso_tv
def index():
    return render_template(
        "gestao/painel_tv.html"
    )


# =========================================================
# API DE ATUALIZAÇÃO AUTOMÁTICA
# =========================================================

@painel_tv_bp.route("/dados")
@acesso_tv
def dados():
    inicio = periodo(
        request.args.get("competencia")
    )

    try:
        return jsonify(
            montar_dados(inicio)
        )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Erro ao atualizar o painel TV"
        )

        return jsonify(
            erro=(
                "Não foi possível consultar os dados. "
                "Tentando novamente."
            )
        ), 503


# =========================================================
# CONFIGURAÇÕES DAS METAS E AVISOS
# =========================================================

@painel_tv_bp.route(
    "/configuracoes",
    methods=["GET", "POST"],
)
@acesso_tv
def configuracoes():
    if request.method == "POST":
        competencia_informada = request.form.get(
            "competencia"
        )
    else:
        competencia_informada = request.args.get(
            "competencia"
        )

    inicio = periodo(
        competencia_informada
    )

    competencia = inicio.strftime("%Y-%m")

    config = PainelTVConfig.query.filter_by(
        competencia=competencia
    ).first()

    token = session.setdefault(
        "painel_tv_csrf",
        secrets.token_urlsafe(32),
    )

    if request.method == "POST":
        token_recebido = request.form.get(
            "csrf_token",
            "",
        )

        if not hmac.compare_digest(
            token,
            token_recebido,
        ):
            abort(
                400,
                "Formulário expirado. Atualize a página.",
            )

        try:
            empresa = request.form.get(
                "empresa",
                "",
            ).strip()

            meta = Decimal(
                request.form.get(
                    "meta_faturamento",
                    "0",
                ).replace(",", ".")
            )

            servicos = int(
                request.form.get(
                    "meta_servicos",
                    "0",
                )
            )

            segundos = int(
                request.form.get(
                    "segundos_tela",
                    "15",
                )
            )

            avisos = [
                linha.strip()
                for linha in request.form.get(
                    "avisos",
                    "",
                ).splitlines()
                if linha.strip()
            ]

            if not empresa or len(empresa) > 100:
                raise ValueError()

            if not meta.is_finite():
                raise ValueError()

            if not (
                Decimal("0")
                <= meta
                <= Decimal("999999999999.99")
            ):
                raise ValueError()

            if not 0 <= servicos <= 10000000:
                raise ValueError()

            if not 5 <= segundos <= 120:
                raise ValueError()

            if len(avisos) > 30:
                raise ValueError()

            if any(
                len(aviso) > 250
                for aviso in avisos
            ):
                raise ValueError()

        except (ValueError, InvalidOperation):
            flash(
                "Verifique os valores: metas positivas, "
                "tempo de 5 a 120 segundos e até 30 avisos "
                "de 250 caracteres.",
                "error",
            )

            return render_template(
                "gestao/painel_tv_config.html",
                config=config,
                competencia=competencia,
                csrf_token=token,
                valores=request.form,
            ), 400

        if config is None:
            config = PainelTVConfig(
                competencia=competencia
            )

            db.session.add(config)

        config.empresa = empresa

        config.meta_faturamento = meta.quantize(
            Decimal("0.01")
        )

        config.meta_servicos = servicos
        config.segundos_tela = segundos
        config.avisos = "\n".join(avisos)

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

            current_app.logger.exception(
                "Erro ao salvar configuração do painel TV"
            )

            flash(
                "Não foi possível salvar. "
                "Atualize a página e tente novamente.",
                "error",
            )

            return render_template(
                "gestao/painel_tv_config.html",
                config=config,
                competencia=competencia,
                csrf_token=token,
                valores=request.form,
            ), 503

        flash(
            "Painel atualizado. A tela recebe "
            "as alterações em até 10 segundos.",
            "success",
        )

        return redirect(
            url_for(
                "painel_tv.configuracoes",
                competencia=competencia,
            )
        )

    return render_template(
        "gestao/painel_tv_config.html",
        config=config,
        competencia=competencia,
        csrf_token=token,
        valores={},
    )