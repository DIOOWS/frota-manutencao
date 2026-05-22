import os
import json
import urllib.request
import urllib.error
from decimal import Decimal


def dinheiro_br(valor):
    try:
        numero = float(valor or 0)
    except Exception:
        numero = 0

    texto = f"{numero:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")

    return f"R$ {texto}"


def texto_seguro(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def montar_mensagem_contas_vencendo_hoje(contas, data_ref):
    data_formatada = data_ref.strftime("%d/%m/%Y")

    linhas = [
        "🔔 Radar Financeiro - Easy Control",
        "",
        f"Contas vencendo hoje ({data_formatada}):",
        ""
    ]

    total = Decimal("0.00")

    for idx, conta in enumerate(contas, start=1):
        descricao = texto_seguro(conta.descricao) or "Sem descrição"
        fornecedor = texto_seguro(conta.fornecedor) or "-"
        categoria = texto_seguro(conta.categoria) or "-"
        setor = texto_seguro(conta.setor) or "-"
        valor = conta.valor or Decimal("0.00")

        try:
            total += Decimal(str(valor or 0))
        except Exception:
            pass

        parcela = ""

        try:
            parcela = conta.nome_parcela()
        except Exception:
            parcela = ""

        linhas.append(
            f"{idx}. {descricao} — {dinheiro_br(valor)}"
        )

        linhas.append(
            f"   Fornecedor: {fornecedor} | Setor: {setor}"
        )

        if categoria:
            linhas.append(
                f"   Categoria: {categoria}"
            )

        if parcela:
            linhas.append(
                f"   Parcela: {parcela}"
            )

        linhas.append("")

    linhas.append(f"Total vencendo hoje: {dinheiro_br(total)}")
    linhas.append("")
    linhas.append("Acesse o sistema para pagar, editar ou acompanhar.")

    return "\n".join(linhas)


def enviar_mensagem_telegram(mensagem):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token:
        return False, "TELEGRAM_BOT_TOKEN não configurado no .env."

    if not chat_id:
        return False, "TELEGRAM_CHAT_ID não configurado no .env."

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    dados = json.dumps(payload).encode("utf-8")

    requisicao = urllib.request.Request(
        url=url,
        data=dados,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=20) as resposta:
            conteudo = resposta.read().decode("utf-8")

        retorno = json.loads(conteudo)

        if retorno.get("ok"):
            return True, "Mensagem enviada com sucesso para o Telegram."

        return False, f"Telegram retornou erro: {retorno}"

    except urllib.error.HTTPError as e:
        try:
            erro = e.read().decode("utf-8")
        except Exception:
            erro = str(e)

        return False, f"Erro HTTP ao enviar Telegram: {erro}"

    except Exception as e:
        return False, f"Erro ao enviar Telegram: {str(e)}"