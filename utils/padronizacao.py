# utils/padronizacao.py

def tipo_padronizado(tipo):
    tipo = (tipo or "").upper()

    if "REFRIG" in tipo:
        return "Refrigeração"
    return "Estrutura"


def motivo_padronizado(texto):
    texto = (texto or "").lower()

    if "compressor" in texto:
        return "Compressor condenado"
    if "não liga" in texto or "nao liga" in texto:
        return "Sistema não liga"
    if "temperatura" in texto:
        return "Baixa temperatura"
    if "vazamento" in texto:
        return "Vazamento de gás"

    return "Outros"