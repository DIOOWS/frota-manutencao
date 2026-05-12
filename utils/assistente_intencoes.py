from difflib import SequenceMatcher


INTENCOES = {
    # =========================
    # IDENTIDADE DO SIDINHO
    # =========================
    "identidade_sidinho": [
        "qual seu nome",
        "qual é seu nome",
        "qual e seu nome",
        "quem é você",
        "quem e voce",
        "quem é vc",
        "quem e vc",
        "quem é o sidinho",
        "quem e o sidinho",
        "se apresente",
        "se apresenta",
        "o que você faz",
        "o que voce faz",
        "você é quem",
        "voce e quem",
        "quem está falando",
        "quem esta falando",
        "me diga quem você é",
        "me diga quem voce e",
        "sidinho quem é você",
        "sidinho quem e voce",
        "você sabe meu nome",
        "voce sabe meu nome",
        "qual meu nome",
        "quem sou eu",
        "você me conhece",
        "voce me conhece",
    ],

    # =========================
    # TOTALIZADORES SIMPLES
    # =========================
    "total_frotas": [
        "quantas frotas temos",
        "quantas frotas existem",
        "quantas frotas cadastradas",
        "quantas frotas tem",
        "total de frotas",
        "quantidade de frotas",
        "qtd de frotas",
        "qtde de frotas",
        "quantos veículos temos",
        "quantos veiculos temos",
        "quantos caminhões temos",
        "quantos caminhoes temos",
        "total de veículos",
        "total de veiculos",
        "quantidade de veículos",
        "quantidade de veiculos",
        "me diga o total de frotas",
        "me mostra o total de frotas",
        "número de frotas",
        "numero de frotas",
    ],

    "total_manutencoes": [
        "quantas manutenções temos",
        "quantas manutencoes temos",
        "total de manutenções",
        "total de manutencoes",
        "quantidade de manutenções",
        "quantidade de manutencoes",
        "qtd de manutenções",
        "qtd de manutencoes",
        "quantos registros de manutenção",
        "quantos registros de manutencao",
        "quantas ordens temos",
        "quantas os temos",
        "total de os",
        "quantidade de os",
        "quantos atendimentos temos",
        "total de atendimentos",
    ],

    "total_clientes": [
        "quantos clientes temos",
        "quantos clientes existem",
        "quantos clientes cadastrados",
        "total de clientes",
        "quantidade de clientes",
        "qtd de clientes",
        "me mostra total de clientes",
        "me diga quantos clientes temos",
    ],

    # =========================
    # RESUMO / VISÃO GERAL
    # =========================
    "resumo_geral": [
        "me dá um resumo geral",
        "me da um resumo geral",
        "resumo geral",
        "resumo do sistema",
        "resumo operacional",
        "resumo das manutenções",
        "resumo das manutencoes",
        "resumo da frota",
        "resumo do mês",
        "resumo do mes",
        "resumo do período",
        "resumo do periodo",
        "como está o sistema",
        "como esta o sistema",
        "como estão as manutenções",
        "como estao as manutencoes",
        "como anda o sistema",
        "como anda a operação",
        "como anda a operacao",
        "como está a operação",
        "como esta a operacao",
        "visão geral",
        "visao geral",
        "diagnóstico geral",
        "diagnostico geral",
        "me mostra um resumo",
        "me fala a situação geral",
        "me fala a situacao geral",
        "qual a situação geral",
        "qual a situacao geral",
        "painel geral",
        "dados gerais",
        "indicadores gerais",
        "me dê os indicadores",
        "me de os indicadores",
        "o que temos no sistema",
        "analise geral",
        "análise geral",
        "faça uma análise geral",
        "faca uma analise geral",
        "me dá uma visão geral",
        "me da uma visao geral",
        "quero uma visão geral",
        "quero uma visao geral",
        "o sistema está bem",
        "o sistema esta bem",
        "como está o controle",
        "como esta o controle",
        "me mostra os números gerais",
        "me mostra os numeros gerais",
        "quais são os números gerais",
        "quais sao os numeros gerais",
        "qual o panorama geral",
        "me dá o panorama",
        "me da o panorama",
        "panorama do sistema",
        "panorama operacional",
        "me explica o cenário",
        "me explica o cenario",
        "qual o cenário atual",
        "qual o cenario atual",
        "como estamos hoje",
        "quero entender o geral",
        "resumo executivo",
    ],

    # =========================
    # OS EM ANDAMENTO / ABERTAS
    # =========================
    "os_em_andamento": [
        "quais os estão em andamento",
        "quais os estao em andamento",
        "quais ordens estão em andamento",
        "quais ordens estao em andamento",
        "manutenções em andamento",
        "manutencoes em andamento",
        "serviços em andamento",
        "servicos em andamento",
        "o que está em aberto",
        "o que esta em aberto",
        "os em aberto",
        "ordens em aberto",
        "serviços pendentes",
        "servicos pendentes",
        "manutenções pendentes",
        "manutencoes pendentes",
        "o que falta finalizar",
        "quais ainda não finalizaram",
        "quais ainda nao finalizaram",
        "quais estão abertas",
        "quais estao abertas",
        "listar os em andamento",
        "listar manutenções abertas",
        "listar manutencoes abertas",
        "tem alguma manutenção aberta",
        "tem alguma manutencao aberta",
        "tem os aberta",
        "tem ordem aberta",
        "quais carros estão parados",
        "quais carros estao parados",
        "quais frotas estão paradas",
        "quais frotas estao paradas",
        "o que ainda está parado",
        "o que ainda esta parado",
        "o que ainda não saiu",
        "o que ainda nao saiu",
        "quais veículos ainda não saíram",
        "quais veiculos ainda nao sairam",
        "quais veículos estão no pátio",
        "quais veiculos estao no patio",
        "quais serviços ainda não concluíram",
        "quais servicos ainda nao concluiram",
        "quais manutenções não finalizaram",
        "quais manutencoes nao finalizaram",
        "o que está aguardando finalização",
        "o que esta aguardando finalizacao",
        "me mostra o que está pendente",
        "me mostra o que esta pendente",
        "pendências",
        "pendencias",
        "lista de pendências",
        "lista de pendencias",
        "o que precisa finalizar",
    ],

    # =========================
    # MAIOR TMA / ATM POR MANUTENÇÃO
    # =========================
    "maiores_tma": [
        "quais maiores tma",
        "quais maiores atm",
        "maiores tma",
        "maiores atm",
        "qual manutenção demorou mais",
        "qual manutencao demorou mais",
        "quais demoraram mais",
        "quais serviços demoraram mais",
        "quais servicos demoraram mais",
        "tempo médio mais alto",
        "tempo medio mais alto",
        "maior tempo de atendimento",
        "maior tempo médio de atendimento",
        "maior tempo medio de atendimento",
        "qual os ficou mais tempo",
        "qual os demorou mais",
        "manutenções com maior tempo",
        "manutencoes com maior tempo",
        "listar maiores tempos",
        "qual foi o maior tma",
        "qual foi o maior atm",
        "quais atendimentos mais demorados",
        "quais manutenções mais demoradas",
        "quais manutencoes mais demoradas",
        "top tma",
        "top atm",
        "ranking de tma",
        "ranking de atm",
        "quais os tiveram maior tma",
        "quais os tiveram maior atm",
        "quais foram as mais demoradas",
        "quais ficaram mais dias",
        "quais serviços ficaram mais dias",
        "quais servicos ficaram mais dias",
        "qual serviço passou mais tempo",
        "qual servico passou mais tempo",
        "qual manutenção ficou mais dias parada",
        "qual manutencao ficou mais dias parada",
        "me mostra os maiores tempos",
        "me mostra os maiores tma",
        "me mostra os maiores atm",
    ],

    # =========================
    # FROTAS COM MAIOR TMA
    # =========================
    "frotas_maior_tma": [
        "qual frota tem maior tma",
        "qual frota tem maior atm",
        "frotas com maior tma",
        "frotas com maior atm",
        "quais frotas demoraram mais",
        "quais frotas têm maior tempo",
        "quais frotas tem maior tempo",
        "frota com maior tempo de atendimento",
        "frota com maior tempo médio",
        "frota com maior tempo medio",
        "ranking de tma por frota",
        "ranking de atm por frota",
        "quais veículos ficaram mais tempo parados",
        "quais veiculos ficaram mais tempo parados",
        "qual caminhão ficou mais tempo parado",
        "qual caminhao ficou mais tempo parado",
        "frotas mais demoradas",
        "veículos com maior tma",
        "veiculos com maior tma",
        "qual frota está demorando mais",
        "qual frota esta demorando mais",
        "qual veículo está demorando mais",
        "qual veiculo esta demorando mais",
        "qual frota teve maior tempo médio",
        "qual frota teve maior tempo medio",
        "me mostra as frotas com maior tempo",
        "quais frotas ficam mais paradas",
        "qual frota ficou mais dias parada",
        "frota com atendimento mais demorado",
        "frotas com atendimento mais demorado",
    ],

    # =========================
    # PRINCIPAIS CAUSAS
    # =========================
    "principais_causas": [
        "quais principais causas",
        "principais causas",
        "qual a principal causa",
        "causas mais comuns",
        "causas mais recorrentes",
        "motivos mais recorrentes",
        "motivos mais comuns",
        "ranking de causas",
        "top causas",
        "top 5 causas",
        "top 10 causas",
        "o que mais causa manutenção",
        "o que mais causa manutencao",
        "qual motivo aparece mais",
        "qual causa aparece mais",
        "causa que mais se repete",
        "motivo que mais se repete",
        "quais problemas mais acontecem",
        "quais defeitos mais acontecem",
        "quais ocorrências mais aparecem",
        "quais ocorrencias mais aparecem",
        "quais são os maiores problemas",
        "quais sao os maiores problemas",
        "qual problema mais comum",
        "qual defeito mais comum",
        "o que mais dá problema",
        "o que mais da problema",
        "por que os veículos estão indo para manutenção",
        "por que os veiculos estao indo para manutencao",
        "qual o motivo das manutenções",
        "qual o motivo das manutencoes",
        "quais causas devo acompanhar",
        "causas críticas",
        "causas criticas",
        "problemas críticos",
        "problemas criticos",
        "quais problemas merecem atenção",
        "quais problemas merecem atencao",
        "quais causas merecem atenção",
        "quais causas merecem atencao",
    ],

    # =========================
    # ÚLTIMAS FINALIZAÇÕES
    # =========================
    "ultimas_finalizacoes": [
        "últimas finalizações",
        "ultimas finalizacoes",
        "quais foram as últimas finalizações",
        "quais foram as ultimas finalizacoes",
        "últimas manutenções finalizadas",
        "ultimas manutencoes finalizadas",
        "últimos serviços finalizados",
        "ultimos servicos finalizados",
        "o que foi finalizado por último",
        "o que foi finalizado por ultimo",
        "últimas os finalizadas",
        "ultimas os finalizadas",
        "listar finalizações recentes",
        "listar finalizacoes recentes",
        "serviços concluídos recentemente",
        "servicos concluidos recentemente",
        "manutenções concluídas",
        "manutencoes concluidas",
        "últimas conclusões",
        "ultimas conclusoes",
        "o que acabou de finalizar",
        "o que foi concluído recentemente",
        "o que foi concluido recentemente",
        "quais serviços saíram",
        "quais servicos sairam",
        "quais veículos saíram por último",
        "quais veiculos sairam por ultimo",
        "últimos veículos liberados",
        "ultimos veiculos liberados",
        "últimas saídas",
        "ultimas saidas",
    ],

    # =========================
    # HISTÓRICO DE FROTA
    # =========================
    "historico_frota": [
        "histórico da frota",
        "historico da frota",
        "me mostra a frota",
        "me mostra o histórico da frota",
        "me mostra o historico da frota",
        "ver histórico da frota",
        "ver historico da frota",
        "consultar frota",
        "dados da frota",
        "manutenções da frota",
        "manutencoes da frota",
        "o que aconteceu com a frota",
        "como está a frota",
        "como esta a frota",
        "detalhes da frota",
        "informações da frota",
        "informacoes da frota",
        "histórico do veículo",
        "historico do veiculo",
        "histórico do caminhão",
        "historico do caminhao",
        "me fala da frota",
        "quero ver a frota",
        "abrir histórico da frota",
        "abrir historico da frota",
        "consulta da frota",
        "mostrar manutenção da frota",
        "mostrar manutencao da frota",
        "quais serviços essa frota teve",
        "quais servicos essa frota teve",
        "quais os dessa frota",
        "qual histórico desse veículo",
        "qual historico desse veiculo",
        "esse veículo teve problema",
        "esse veiculo teve problema",
        "essa frota teve problema",
        "me mostra tudo da frota",
    ],

    # =========================
    # FROTA COM MAIS CORRETIVA
    # =========================
    "frota_mais_corretiva": [
        "qual frota tem mais corretiva",
        "qual frota tem mais corretivas",
        "frota com mais corretiva",
        "frota com mais corretivas",
        "ranking de corretivas por frota",
        "quais frotas têm mais corretivas",
        "quais frotas tem mais corretivas",
        "veículos com mais corretivas",
        "veiculos com mais corretivas",
        "caminhões com mais corretivas",
        "caminhoes com mais corretivas",
        "qual veículo deu mais corretiva",
        "qual veiculo deu mais corretiva",
        "qual caminhão deu mais corretiva",
        "qual caminhao deu mais corretiva",
        "qual frota deu mais problema corretivo",
        "frota que mais deu manutenção corretiva",
        "frota que mais deu manutencao corretiva",
        "top corretivas por frota",
        "qual frota mais quebra",
        "qual veículo mais quebra",
        "qual veiculo mais quebra",
        "frota mais problemática em corretiva",
        "frota mais problematica em corretiva",
        "veículo mais problemático em corretiva",
        "veiculo mais problematico em corretiva",
        "qual frota teve mais problema corretivo",
        "quem teve mais corretiva",
        "quem mais teve corretiva",
    ],

    # =========================
    # FROTA COM MAIS PREVENTIVA
    # =========================
    "frota_mais_preventiva": [
        "qual frota tem mais preventiva",
        "qual frota tem mais preventivas",
        "frota com mais preventiva",
        "frota com mais preventivas",
        "ranking de preventivas por frota",
        "quais frotas têm mais preventivas",
        "quais frotas tem mais preventivas",
        "veículos com mais preventivas",
        "veiculos com mais preventivas",
        "caminhões com mais preventivas",
        "caminhoes com mais preventivas",
        "qual veículo teve mais preventiva",
        "qual veiculo teve mais preventiva",
        "qual caminhão teve mais preventiva",
        "qual caminhao teve mais preventiva",
        "top preventivas por frota",
        "qual frota faz mais preventiva",
        "qual frota teve mais manutenção preventiva",
        "qual frota teve mais manutencao preventiva",
        "quem teve mais preventiva",
        "quem mais teve preventiva",
    ],

    # =========================
    # FROTAS MAIS ATENDIDAS
    # =========================
    "frotas_mais_atendidas": [
        "qual frota teve mais manutenção",
        "qual frota teve mais manutencao",
        "qual frota teve mais atendimento",
        "frotas mais atendidas",
        "frota mais atendida",
        "ranking de frotas",
        "ranking de atendimento por frota",
        "veículos mais atendidos",
        "veiculos mais atendidos",
        "caminhões mais atendidos",
        "caminhoes mais atendidos",
        "qual veículo aparece mais",
        "qual veiculo aparece mais",
        "qual frota aparece mais",
        "qual frota mais aparece",
        "top frotas",
        "top veículos",
        "top veiculos",
        "top caminhões",
        "top caminhoes",
        "qual frota mais passou por manutenção",
        "qual frota mais passou por manutencao",
        "frota com mais registros",
        "veículo com mais registros",
        "veiculo com mais registros",
        "qual frota tem mais os",
        "ranking geral das frotas",
    ],

    # =========================
    # COMPARATIVO PREVENTIVA X CORRETIVA
    # =========================
    "preventiva_corretiva": [
        "comparar preventiva e corretiva",
        "comparativo preventiva corretiva",
        "preventiva vs corretiva",
        "preventivas vs corretivas",
        "quantas preventivas e corretivas",
        "quantidade de preventiva e corretiva",
        "quantidade de preventivas e corretivas",
        "me mostra preventiva e corretiva",
        "me mostra preventivas e corretivas",
        "qual diferença entre preventiva e corretiva",
        "qual diferenca entre preventiva e corretiva",
        "percentual de preventiva e corretiva",
        "porcentagem de preventiva e corretiva",
        "como está preventiva e corretiva",
        "como esta preventiva e corretiva",
        "tem mais preventiva ou corretiva",
        "tem mais corretiva ou preventiva",
        "qual tipo tem mais",
        "qual serviço tem mais",
        "qual servico tem mais",
        "comparar tipos de serviço",
        "comparar tipos de servico",
    ],

    # =========================
    # FINALIZADAS
    # =========================
    "finalizadas": [
        "quantas finalizadas",
        "quantas manutenções finalizadas",
        "quantas manutencoes finalizadas",
        "manutenções finalizadas",
        "manutencoes finalizadas",
        "serviços finalizados",
        "servicos finalizados",
        "os finalizadas",
        "listar finalizadas",
        "o que já foi finalizado",
        "o que ja foi finalizado",
        "quantas concluídas",
        "quantas concluidas",
        "quantos serviços concluídos",
        "quantos servicos concluidos",
        "total de finalizadas",
        "total finalizado",
        "lista de finalizadas",
        "me mostra as finalizadas",
        "quais estão finalizadas",
        "quais estao finalizadas",
    ],

    # =========================
    # SEM DATA DE SAÍDA
    # =========================
    "sem_data_saida": [
        "quais os sem data de saída",
        "quais os sem data de saida",
        "manutenções sem data de saída",
        "manutencoes sem data de saida",
        "serviços sem data de saída",
        "servicos sem data de saida",
        "quais ainda não tem saída",
        "quais ainda nao tem saida",
        "quais não têm data de saída",
        "quais nao tem data de saida",
        "os sem saída",
        "os sem saida",
        "registros sem saída",
        "registros sem saida",
        "quem não tem data de saída",
        "quem nao tem data de saida",
        "dados incompletos de saída",
        "dados incompletos de saida",
        "manutenção sem encerramento",
        "manutencao sem encerramento",
    ],

    # =========================
    # CLIENTES
    # =========================
    "clientes_mais_atendidos": [
        "cliente com mais manutenção",
        "cliente com mais manutencao",
        "clientes com mais manutenção",
        "clientes com mais manutencao",
        "ranking de clientes",
        "clientes mais atendidos",
        "cliente mais atendido",
        "qual cliente aparece mais",
        "qual cliente teve mais serviço",
        "qual cliente teve mais servico",
        "top clientes",
        "qual cliente teve mais os",
        "qual cliente teve mais ordem",
        "cliente com mais atendimento",
        "clientes com mais atendimento",
        "quem é o cliente mais atendido",
        "quem e o cliente mais atendido",
        "quais clientes mais usam o serviço",
        "quais clientes mais usam o servico",
        "ranking de atendimento por cliente",
    ],

    # =========================
    # TIPO DE ATENDIMENTO
    # =========================
    "tipo_atendimento": [
        "tipo de atendimento",
        "interno e externo",
        "quantos internos e externos",
        "quantidade de interno e externo",
        "atendimento interno externo",
        "comparar interno e externo",
        "interno vs externo",
        "externo vs interno",
        "quais atendimentos externos",
        "quais atendimentos internos",
        "tem mais interno ou externo",
        "tem mais externo ou interno",
        "quantos atendimentos internos",
        "quantos atendimentos externos",
        "resumo por tipo de atendimento",
        "ranking de tipo de atendimento",
        "tipo atendimento mais comum",
        "qual atendimento aparece mais",
        "qual tipo de atendimento aparece mais",
    ],

    # =========================
    # ALERTAS / PONTOS CRÍTICOS
    # =========================
    "alertas_operacionais": [
        "o que merece atenção",
        "o que merece atencao",
        "quais pontos merecem atenção",
        "quais pontos merecem atencao",
        "tem algo preocupante",
        "tem alguma coisa preocupante",
        "qual frota preocupa",
        "qual veículo preocupa",
        "qual veiculo preocupa",
        "qual caminhão preocupa",
        "qual caminhao preocupa",
        "onde devo focar",
        "o que eu deveria acompanhar",
        "o que acompanhar de perto",
        "quais riscos existem",
        "quais alertas operacionais",
        "me mostra os alertas",
        "alertas do sistema",
        "pontos críticos",
        "pontos criticos",
        "situação crítica",
        "situacao critica",
        "qual o maior problema agora",
        "o que está ruim",
        "o que esta ruim",
        "tem algum padrão ruim",
        "tem algum padrao ruim",
    ],

    # =========================
    # RELATÓRIO / TEXTO CLIENTE
    # =========================
    "relatorio_cliente": [
        "gera um relatório para cliente",
        "gera um relatorio para cliente",
        "faça um texto para cliente",
        "faca um texto para cliente",
        "me dá um texto para apresentar",
        "me da um texto para apresentar",
        "texto para reunião",
        "texto para reuniao",
        "resumo para reunião",
        "resumo para reuniao",
        "o que falar para o cliente",
        "como apresentar isso",
        "me ajuda a apresentar",
        "escreve um resumo executivo",
        "monta uma análise para o cliente",
        "monta uma analise para o cliente",
        "resumo para gestor",
        "texto para gestor",
        "explicação para cliente",
        "explicacao para cliente",
        "preparar apresentação",
        "preparar apresentacao",
        "me dá os destaques",
        "me da os destaques",
        "quais dados destacar",
    ],
}


SINONIMOS = {
    "manutencao": "manutenção",
    "manutencoes": "manutenções",
    "manut": "manutenção",
    "saida": "saída",
    "saidas": "saídas",
    "veiculo": "veículo",
    "veiculos": "veículos",
    "carro": "veículo",
    "carros": "veículos",
    "caminhao": "caminhão",
    "caminhoes": "caminhões",
    "bau": "baú",
    "baus": "baús",
    "esta": "está",
    "estao": "estão",
    "ta": "está",
    "tá": "está",
    "to": "estou",
    "tou": "estou",
    "ultimas": "últimas",
    "ultimos": "últimos",
    "finalizacoes": "finalizações",
    "conclusoes": "conclusões",
    "diagnostico": "diagnóstico",
    "analise": "análise",
    "situacao": "situação",
    "operacao": "operação",
    "atencao": "atenção",
    "critico": "crítico",
    "criticos": "críticos",
    "corretivo": "corretiva",
    "corretivos": "corretivas",
    "preventivo": "preventiva",
    "preventivos": "preventivas",
    "atm": "tma",
    "dtm": "tma",
    "ordem": "os",
    "ordens": "os",
    "servico": "serviço",
    "servicos": "serviços",
    "qtd": "quantidade",
    "qtde": "quantidade",
    "qnt": "quantidade",
    "problema": "causa",
    "problemas": "causas",
    "defeito": "causa",
    "defeitos": "causas",
    "motivo": "causa",
    "motivos": "causas",
}


def normalizar_texto(texto):
    texto = (texto or "").lower().strip()

    trocas = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }

    for velho, novo in trocas.items():
        texto = texto.replace(velho, novo)

    for sinal in ["?", ",", ".", "!", ";", ":", "(", ")", "[", "]", "{", "}", "-", "_", "/", "\\"]:
        texto = texto.replace(sinal, " ")

    palavras = texto.split()

    palavras_normalizadas = [
        SINONIMOS.get(p, p)
        for p in palavras
    ]

    return " ".join(palavras_normalizadas)


def similaridade(a, b):
    return SequenceMatcher(
        None,
        normalizar_texto(a),
        normalizar_texto(b)
    ).ratio()


def detectar_intencao(pergunta):
    pergunta_norm = normalizar_texto(pergunta)

    # =========================
    # REGRAS FORTES
    # =========================

    if (
        "quem" in pergunta_norm
        and (
            "voce" in pergunta_norm
            or "vc" in pergunta_norm
            or "sidinho" in pergunta_norm
            or "sou" in pergunta_norm
        )
    ):
        return "identidade_sidinho"

    if "qual seu nome" in pergunta_norm or "seu nome" in pergunta_norm:
        return "identidade_sidinho"

    if "meu nome" in pergunta_norm or "quem sou eu" in pergunta_norm:
        return "identidade_sidinho"

    if (
        ("quantas" in pergunta_norm or "quantos" in pergunta_norm or "total" in pergunta_norm or "quantidade" in pergunta_norm)
        and ("frota" in pergunta_norm or "veículo" in pergunta_norm or "veiculo" in pergunta_norm or "caminhão" in pergunta_norm or "caminhao" in pergunta_norm)
    ):
        return "total_frotas"

    if (
        ("quantas" in pergunta_norm or "quantos" in pergunta_norm or "total" in pergunta_norm or "quantidade" in pergunta_norm)
        and ("manutenção" in pergunta_norm or "manutencao" in pergunta_norm or "os" in pergunta_norm or "atendimento" in pergunta_norm)
    ):
        return "total_manutencoes"

    if (
        ("quantos" in pergunta_norm or "quantas" in pergunta_norm or "total" in pergunta_norm or "quantidade" in pergunta_norm)
        and "cliente" in pergunta_norm
    ):
        return "total_clientes"

    if "preventiva" in pergunta_norm and "corretiva" in pergunta_norm:
        return "preventiva_corretiva"

    if "corretiva" in pergunta_norm and "frota" in pergunta_norm:
        return "frota_mais_corretiva"

    if "preventiva" in pergunta_norm and "frota" in pergunta_norm:
        return "frota_mais_preventiva"

    if "andamento" in pergunta_norm or "aberto" in pergunta_norm or "pendente" in pergunta_norm:
        return "os_em_andamento"

    if "sem data" in pergunta_norm and "saida" in pergunta_norm:
        return "sem_data_saida"

    if "cliente" in pergunta_norm and ("mais" in pergunta_norm or "ranking" in pergunta_norm):
        return "clientes_mais_atendidos"

    if "interno" in pergunta_norm or "externo" in pergunta_norm:
        return "tipo_atendimento"

    if "causa" in pergunta_norm:
        return "principais_causas"

    if "finalizacao" in pergunta_norm or "finalizada" in pergunta_norm or "finalizado" in pergunta_norm:
        return "ultimas_finalizacoes"

    if "frota" in pergunta_norm and any(char.isdigit() for char in pergunta_norm):
        return "historico_frota"

    if "tma" in pergunta_norm and "frota" in pergunta_norm:
        return "frotas_maior_tma"

    if "tma" in pergunta_norm:
        return "maiores_tma"

    if "alerta" in pergunta_norm or "preocupa" in pergunta_norm or "critico" in pergunta_norm:
        return "alertas_operacionais"

    if "relatorio" in pergunta_norm or ("cliente" in pergunta_norm and "texto" in pergunta_norm):
        return "relatorio_cliente"

    # =========================
    # SIMILARIDADE
    # =========================

    melhor_intencao = "resumo_geral"
    melhor_score = 0

    for intencao, exemplos in INTENCOES.items():
        for exemplo in exemplos:
            score = similaridade(pergunta_norm, exemplo)

            if score > melhor_score:
                melhor_score = score
                melhor_intencao = intencao

    if melhor_score < 0.43:
        return "resumo_geral"

    return melhor_intencao


def detectar_intencoes(pergunta, limite=3):
    pergunta_norm = normalizar_texto(pergunta)
    intencoes_detectadas = []

    regras = [
        ("identidade_sidinho", ["seu nome"]),
        ("identidade_sidinho", ["quem", "voce"]),
        ("total_frotas", ["frota", "quantas"]),
        ("total_frotas", ["frota", "total"]),
        ("total_manutencoes", ["manutenção", "total"]),
        ("total_manutencoes", ["manutenção", "quantas"]),
        ("total_clientes", ["cliente", "total"]),
        ("total_clientes", ["cliente", "quantos"]),
        ("frota_mais_corretiva", ["corretiva", "frota"]),
        ("frota_mais_preventiva", ["preventiva", "frota"]),
        ("os_em_andamento", ["andamento"]),
        ("os_em_andamento", ["aberto"]),
        ("os_em_andamento", ["pendente"]),
        ("sem_data_saida", ["sem data", "saida"]),
        ("principais_causas", ["causa"]),
        ("ultimas_finalizacoes", ["finalizacao"]),
        ("ultimas_finalizacoes", ["finalizada"]),
        ("ultimas_finalizacoes", ["finalizado"]),
        ("frotas_maior_tma", ["tma", "frota"]),
        ("maiores_tma", ["tma"]),
        ("preventiva_corretiva", ["preventiva", "corretiva"]),
        ("clientes_mais_atendidos", ["cliente", "mais"]),
        ("tipo_atendimento", ["interno"]),
        ("tipo_atendimento", ["externo"]),
        ("alertas_operacionais", ["alerta"]),
        ("alertas_operacionais", ["preocupa"]),
        ("alertas_operacionais", ["critico"]),
        ("relatorio_cliente", ["relatorio"]),
        ("resumo_geral", ["resumo"]),
        ("resumo_geral", ["geral"]),
    ]

    for intencao, palavras in regras:
        if all(p in pergunta_norm for p in palavras):
            if intencao not in intencoes_detectadas:
                intencoes_detectadas.append(intencao)

    if "frota" in pergunta_norm and any(char.isdigit() for char in pergunta_norm):
        if "historico_frota" not in intencoes_detectadas:
            intencoes_detectadas.append("historico_frota")

    if not intencoes_detectadas:
        intencoes_detectadas.append(detectar_intencao(pergunta))

    return intencoes_detectadas[:limite]