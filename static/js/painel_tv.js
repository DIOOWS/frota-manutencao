(function () {
    "use strict";

    // =====================================================
    // CONFIGURAÇÃO E ESTADO
    // =====================================================

    const URL_DADOS = "/gestao/painel-tv/dados";
    const INTERVALO_ATUALIZACAO = 10000;

    let dados = null;
    let telaAtual = 0;
    let segundosDecorridos = 0;
    let pausado = false;
    let cicloAtual = 0;

    let consultando = false;
    let assinaturaAnterior = "";
    let textoFaixaAnterior = "";
    let ultimaLeitura = null;

    const elemento = (id) => document.getElementById(id);

    // =====================================================
    // FORMATAÇÃO
    // =====================================================

    function moeda(valor) {
        return Number(valor || 0).toLocaleString("pt-BR", {
            style: "currency",
            currency: "BRL",
            maximumFractionDigits: 0
        });
    }

    function escapar(valor) {
        const caracteres = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        };

        return String(valor == null ? "" : valor).replace(
            /[&<>"']/g,
            (caractere) => caracteres[caractere]
        );
    }

    function percentual(realizado, meta) {
        return Number(meta) > 0
            ? (Number(realizado) / Number(meta)) * 100
            : 0;
    }

    function percentualTexto(valor) {
        return Number(valor || 0).toLocaleString("pt-BR", {
            maximumFractionDigits: 1
        });
    }

    function limitarPercentual(valor) {
        return Math.max(0, Math.min(100, valor));
    }

    function dataTexto(valor) {
        if (!valor) {
            return "Sem data";
        }

        return valor.split("-").reverse().join("/");
    }

    function grupoAtual(itens, tamanho) {
        const quantidadeGrupos = Math.max(
            1,
            Math.ceil(itens.length / tamanho)
        );

        const inicio = (
            cicloAtual % quantidadeGrupos
        ) * tamanho;

        return itens.slice(inicio, inicio + tamanho);
    }

    // =====================================================
    // CONEXÃO E RELÓGIO
    // =====================================================

    function mostrarStatus(texto, erro = false) {
        const status = elemento("conexao");

        status.textContent = texto;

        status.className = erro
            ? "status-error"
            : "status-ok";
    }

    function atualizarRelogio() {
        const agora = new Date();

        elemento("relogio").textContent =
            agora.toLocaleTimeString("pt-BR", {
                timeZone: "America/Sao_Paulo",
                hour: "2-digit",
                minute: "2-digit"
            });

        elemento("data-hoje").textContent =
            agora.toLocaleDateString("pt-BR", {
                timeZone: "America/Sao_Paulo",
                day: "2-digit",
                month: "long",
                year: "numeric"
            });
    }

    // =====================================================
    // INDICADORES FIXOS
    // =====================================================

    function atualizarIndicadores() {
        elemento("empresa").textContent = dados.empresa;

        elemento("periodo").textContent =
            dados.periodo.toUpperCase();

        elemento("meta").textContent =
            dados.meta_faturamento > 0
                ? moeda(dados.meta_faturamento)
                : "Definir meta";

        elemento("faturamento").textContent =
            moeda(dados.faturamento.total);

        elemento("pagar").textContent =
            moeda(dados.pagar_mes.total);

        elemento("receber").textContent =
            moeda(dados.receber_mes.total);
    }

    // =====================================================
    // TELA 1 — METAS
    // =====================================================

    function montarTelaMetas() {
        const metaDefinida = dados.meta_faturamento > 0;

        const progresso = percentual(
            dados.faturamento.total,
            dados.meta_faturamento
        );

        const progressoServicos = percentual(
            dados.operacao.finalizadas,
            dados.meta_servicos
        );

        const faltante = Math.max(
            0,
            dados.meta_faturamento - dados.faturamento.total
        );

        let mensagem;

        if (!metaDefinida) {
            mensagem = `
                Configure a meta mensal para acompanhar
                o progresso.
            `;
        } else if (progresso >= 100) {
            mensagem = `
                Meta alcançada.
                Vamos continuar avançando!
            `;
        } else {
            mensagem = `
                Faltam <b>${moeda(faltante)}</b>
                para alcançar a meta.
            `;
        }

        const comprimentoGrafico =
            limitarPercentual(progresso) * 6.283;

        const valorCentral = metaDefinida
            ? `${percentualTexto(progresso)}<small>%</small>`
            : "A configurar";

        const classeValor = metaDefinida
            ? ""
            : "no-goal";

        return `
            <div class="goals">
                <div class="goal-copy">
                    <div class="eyebrow">
                        <span class="tiny-line"></span>
                        NOSSO OBJETIVO, TODOS OS DIAS
                    </div>

                    <h2>
                        Cada resultado<br>
                        nos leva <em>mais longe.</em>
                    </h2>

                    <p>${mensagem}</p>

                    <div class="service">
                        <span>
                            Serviços finalizados no mês

                            <b>
                                ${dados.operacao.finalizadas}

                                <span>
                                    /
                                    ${dados.meta_servicos || "sem meta"}
                                </span>
                            </b>
                        </span>

                        <div class="bar">
                            <i style="
                                width:
                                ${limitarPercentual(progressoServicos)}%;
                            "></i>
                        </div>
                    </div>

                    <div class="fin-caption">
                        Faturamento Comercial • competência do mês
                        <br>
                        Serviços • Manutenções finalizadas
                        por data de saída
                    </div>
                </div>

                <div class="gauge-wrap">
                    <svg
                        viewBox="0 0 240 240"
                        aria-hidden="true"
                    >
                        <circle
                            class="track"
                            cx="120"
                            cy="120"
                            r="100"
                        ></circle>

                        <circle
                            class="gauge"
                            cx="120"
                            cy="120"
                            r="100"
                            stroke-dasharray="
                                ${comprimentoGrafico} 628.3
                            "
                        ></circle>
                    </svg>

                    <div>
                        <span class="eyebrow">
                            ${
                                metaDefinida
                                    ? "META ATINGIDA"
                                    : "META DO MÊS"
                            }
                        </span>

                        <strong class="${classeValor}">
                            ${valorCentral}
                        </strong>

                        <span>
                            ${moeda(dados.faturamento.total)}
                            realizados
                        </span>
                    </div>
                </div>
            </div>
        `;
    }

    // =====================================================
    // TELA 2 — FINANCEIRO
    // =====================================================

    function montarLinhaConta(conta) {
        const entrada = conta.tipo === "receber";

        const atrasada = Boolean(
            conta.vencimento &&
            conta.vencimento < dados.hoje
        );

        const vencimento = (
            conta.vencimento === dados.hoje
        )
            ? "Hoje"
            : dataTexto(conta.vencimento);

        return `
            <div class="bill">
                <span>
                    <i class="${
                        entrada ? "credit" : "debit"
                    }"></i>

                    ${escapar(conta.nome)}
                </span>

                <span class="${
                    atrasada ? "danger" : ""
                }">
                    ${vencimento}
                </span>

                <b>
                    ${entrada ? "+" : "−"}
                    ${moeda(conta.valor)}
                </b>
            </div>
        `;
    }

    function montarTelaFinanceiro() {
        const contasVisiveis = grupoAtual(
            dados.contas,
            4
        );

        const linhas = contasVisiveis.length
            ? contasVisiveis.map(montarLinhaConta).join("")
            : `
                <p class="muted">
                    Nenhuma conta aberta encontrada
                    nestas fontes.
                </p>
            `;

        const avisoSemData = dados.sem_vencimento
            ? `
                <br>
                ${dados.sem_vencimento} contas sem vencimento
                ficam fora dos totais mensais.
            `
            : "";

        return `
            <div class="finance">
                <div class="section-title">
                    <div>
                        <span class="eyebrow">
                            FINANCEIRO EM MOVIMENTO
                        </span>

                        <h2>
                            Contas no radar<span>.</span>
                        </h2>
                    </div>

                    <div class="balance">
                        Recebimentos previstos hoje

                        <strong>
                            ${moeda(dados.recebimentos_hoje.total)}
                        </strong>
                    </div>
                </div>

                <div class="financial-body">
                    <div class="alerts">
                        <article>
                            <span>Vencem hoje</span>

                            <strong>
                                ${moeda(dados.vence_hoje.total)}
                            </strong>

                            <small>
                                ${dados.vence_hoje.quantidade}
                                ${
                                    dados.vence_hoje.quantidade === 1
                                        ? "conta aberta"
                                        : "contas abertas"
                                }
                            </small>
                        </article>

                        <article class="red">
                            <span>
                                Atrasadas • todos os meses
                            </span>

                            <strong>
                                ${moeda(dados.atrasadas.total)}
                            </strong>

                            <small>
                                ${dados.atrasadas.quantidade}
                                ${
                                    dados.atrasadas.quantidade === 1
                                        ? "conta aberta"
                                        : "contas abertas"
                                }
                            </small>
                        </article>
                    </div>

                    <div class="bills">
                        <div class="list-head">
                            <span>CONTA / DESCRIÇÃO</span>
                            <span>VENCIMENTO</span>
                            <span>VALOR</span>
                        </div>

                        ${linhas}

                        <div class="fin-caption">
                            Entradas em verde • Saídas em amarelo.
                            <br>
                            Lista até o fim do mês + atrasados.
                            <br>
                            Exibindo ${contasVisiveis.length}
                            de ${dados.contas.length}
                            itens selecionados
                            (até 24 por fonte).
                            ${avisoSemData}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // =====================================================
    // TELA 3 — OPERAÇÃO
    // =====================================================

    function montarTelaOperacao() {
        const operacao = dados.operacao;

        const ultimas = grupoAtual(
            operacao.ultimas,
            3
        );

        const linhas = ultimas.length
            ? ultimas.map((manutencao) => `
                <div class="bill">
                    <span>
                        ${escapar(manutencao.frota)}
                    </span>

                    <span>
                        ${escapar(manutencao.cliente)}
                    </span>

                    <b>
                        ${dataTexto(manutencao.data)}
                    </b>
                </div>
            `).join("")
            : `
                <p class="muted">
                    Nenhuma manutenção finalizada neste mês.
                </p>
            `;

        const tma = operacao.tma == null
            ? "—"
            : percentualTexto(operacao.tma);

        return `
            <div class="operation">
                <div class="section-title">
                    <div>
                        <span class="eyebrow">
                            MANUTENÇÕES DO SISTEMA
                        </span>

                        <h2>
                            Frotas em movimento<span>.</span>
                        </h2>
                    </div>
                </div>

                <div class="op-grid">
                    <article>
                        <span>Entradas no mês</span>

                        <strong>
                            ${operacao.entradas}
                        </strong>
                    </article>

                    <article>
                        <span>Finalizadas no mês</span>

                        <strong>
                            ${operacao.finalizadas}
                        </strong>
                    </article>

                    <article>
                        <span>
                            Em andamento • total atual
                        </span>

                        <strong>
                            ${operacao.andamento}
                        </strong>
                    </article>

                    <article>
                        <span>
                            TMA registrado • finalizadas no mês
                        </span>

                        <strong>
                            ${tma}
                            <small>dias</small>
                        </strong>
                    </article>
                </div>

                <div class="list-head">
                    <span>FROTA</span>
                    <span>CLIENTE</span>
                    <span>FINALIZAÇÃO</span>
                </div>

                ${linhas}

                <div class="fin-caption">
                    Últimas finalizações do mês.
                    <br>
                    TMA usa os valores DTM positivos
                    registrados nas manutenções.
                </div>
            </div>
        `;
    }

    // =====================================================
    // TELA 4 — AVISOS
    // =====================================================

    function montarTelaAvisos() {
        const avisosVisiveis = grupoAtual(
            dados.avisos,
            4
        );

        const quantidadeGrupos = Math.max(
            1,
            Math.ceil(dados.avisos.length / 4)
        );

        const inicio = (
            cicloAtual % quantidadeGrupos
        ) * 4;

        const avisosHTML = avisosVisiveis.length
            ? avisosVisiveis.map((aviso, indice) => `
                <article>
                    <span>
                        ${
                            String(inicio + indice + 1)
                                .padStart(2, "0")
                        }
                    </span>

                    <h3>
                        ${escapar(aviso)}
                    </h3>

                    <span aria-hidden="true">›</span>
                </article>
            `).join("")
            : `
                <p class="muted">
                    Cadastre os avisos nas configurações
                    do Modo TV.
                </p>
            `;

        return `
            <div class="notice-slide">
                <div>
                    <span class="eyebrow">
                        O QUE MERECE NOSSA ATENÇÃO
                    </span>

                    <h2>
                        Equipe alinhada.<br>
                        <em>Prioridades claras.</em>
                    </h2>

                    <p>
                        Os próximos passos para manter
                        tudo em movimento.
                    </p>
                </div>

                <div class="notice-list">
                    ${avisosHTML}
                </div>
            </div>
        `;
    }

    // =====================================================
    // FAIXA DE ALERTAS
    // =====================================================

    function atualizarFaixa() {
        const mensagens = [
            `Vencem hoje: ${moeda(dados.vence_hoje.total)}`,
            `Atrasadas: ${moeda(dados.atrasadas.total)}`,
            ...dados.avisos
        ];

        const texto = mensagens.join("  ✦  ");

        // Evita reiniciar o movimento a cada consulta.
        if (texto === textoFaixaAnterior) {
            return;
        }

        textoFaixaAnterior = texto;

        const conteudo = escapar(texto);

        elemento("ticker").innerHTML = `
            <span>${conteudo}　 ✦　</span>
            <span aria-hidden="true">${conteudo}　 ✦　</span>
        `;
    }

    // =====================================================
    // RENDERIZAÇÃO E NAVEGAÇÃO
    // =====================================================

    function renderizar() {
        if (!dados) {
            return;
        }

        atualizarIndicadores();

        const telas = [
            montarTelaMetas,
            montarTelaFinanceiro,
            montarTelaOperacao,
            montarTelaAvisos
        ];

        elemento("stage").innerHTML =
            telas[telaAtual]();

        atualizarFaixa();
    }

    function atualizarContador() {
        const tempo = dados
            ? dados.segundos_tela
            : 15;

        if (!dados) {
            elemento("contador").textContent =
                "Aguardando dados";

            elemento("timer").style.width = "0%";

            return;
        }

        elemento("contador").textContent = pausado
            ? "Rotação pausada"
            : (
                "Próxima tela em " +
                Math.max(0, tempo - segundosDecorridos) +
                "s"
            );

        elemento("timer").style.width = (
            limitarPercentual(
                (segundosDecorridos / tempo) * 100
            ) + "%"
        );
    }

    function escolherTela(indice) {
        telaAtual = indice;
        segundosDecorridos = 0;

        document.querySelectorAll(
            "nav [data-slide]"
        ).forEach((botao) => {
            botao.classList.toggle(
                "active",
                Number(botao.dataset.slide) === telaAtual
            );
        });

        document.querySelectorAll(
            ".dots [data-slide]"
        ).forEach((botao) => {
            botao.classList.toggle(
                "selected",
                Number(botao.dataset.slide) === telaAtual
            );
        });

        elemento("pagina").textContent = (
            String(telaAtual + 1).padStart(2, "0") +
            " / 04"
        );

        renderizar();
        atualizarContador();
    }

    function alternarPausa() {
        pausado = !pausado;

        const botao = elemento("pausar");

        botao.textContent = pausado ? "▶" : "Ⅱ";

        botao.setAttribute(
            "aria-label",
            pausado
                ? "Retomar rotação"
                : "Pausar rotação"
        );

        atualizarContador();
    }

    // =====================================================
    // SESSÃO ENCERRADA
    // =====================================================

    function limparPainelSemAcesso() {
        dados = null;
        assinaturaAnterior = "";
        textoFaixaAnterior = "";

        elemento("stage").classList.remove("stale");

        elemento("stage").innerHTML = `
            <div class="loading-state">
                Sessão encerrada ou acesso indisponível.
                <br>
                Faça login com Gestão/Gestor.
            </div>
        `;

        [
            "meta",
            "faturamento",
            "pagar",
            "receber"
        ].forEach((id) => {
            elemento(id).textContent = "—";
        });

        elemento("empresa").textContent =
            "EASY ASSISTÊNCIA";

        elemento("periodo").textContent =
            "ACESSO INDISPONÍVEL";

        elemento("ticker").textContent =
            "Faça login novamente para visualizar os dados.";

        mostrarStatus(
            "Acesso indisponível • entre novamente no sistema",
            true
        );

        atualizarContador();
    }

    // =====================================================
    // CONSULTA AUTOMÁTICA AO FLASK
    // =====================================================

    async function consultarDados() {
        if (consultando) {
            return;
        }

        consultando = true;

        const controlador = new AbortController();

        const limite = setTimeout(() => {
            controlador.abort();
        }, 8000);

        try {
            const resposta = await fetch(URL_DADOS, {
                cache: "no-store",
                credentials: "same-origin",
                signal: controlador.signal
            });

            if (
                resposta.status === 401 ||
                resposta.status === 403 ||
                resposta.redirected
            ) {
                limparPainelSemAcesso();
                return;
            }

            if (!resposta.ok) {
                throw new Error(
                    "Não foi possível consultar o painel."
                );
            }

            const resultado = await resposta.json();

            // Verifica a estrutura mínima antes de exibir.
            if (
                !resultado ||
                !resultado.faturamento ||
                !resultado.pagar_mes ||
                !resultado.receber_mes ||
                !resultado.operacao ||
                !Array.isArray(resultado.contas) ||
                !Array.isArray(resultado.avisos)
            ) {
                throw new Error(
                    "Resposta do painel inválida."
                );
            }

            dados = resultado;
            ultimaLeitura = new Date();

            elemento("stage").classList.remove("stale");

            const horario = new Date(
                resultado.atualizado_em
            ).toLocaleTimeString("pt-BR", {
                timeZone: "America/Sao_Paulo",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit"
            });

            mostrarStatus(
                `● Conectado • Atualizado ${horario}`
            );

            // O horário muda em toda consulta.
            // Os gráficos só são refeitos se os dados mudarem.
            const assinatura = JSON.stringify({
                ...resultado,
                atualizado_em: ""
            });

            if (assinatura !== assinaturaAnterior) {
                assinaturaAnterior = assinatura;
                renderizar();
            }

            atualizarContador();

        } catch (erro) {
            elemento("stage").classList.add("stale");

            if (ultimaLeitura) {
                mostrarStatus(
                    "Sem atualização • exibindo a última leitura. " +
                    "Tentando novamente…",
                    true
                );
            } else {
                mostrarStatus(
                    "Não foi possível consultar os dados. " +
                    "Tentando novamente…",
                    true
                );
            }

        } finally {
            clearTimeout(limite);
            consultando = false;
        }
    }

    // =====================================================
    // TELA CHEIA
    // =====================================================

    async function alternarTelaCheia() {
        try {
            if (document.fullscreenElement) {
                await document.exitFullscreen();
            } else {
                await document.documentElement.requestFullscreen();
            }

        } catch (erro) {
            mostrarStatus(
                "Use F11 para ativar a tela cheia.",
                true
            );
        }
    }

    // =====================================================
    // EVENTOS
    // =====================================================

    document.querySelectorAll(
        "[data-slide]"
    ).forEach((botao) => {
        botao.addEventListener("click", () => {
            escolherTela(
                Number(botao.dataset.slide)
            );
        });
    });

    elemento("pausar").addEventListener(
        "click",
        alternarPausa
    );

    elemento("tela-cheia").addEventListener(
        "click",
        alternarTelaCheia
    );

    document.addEventListener("keydown", (evento) => {
        const tag = document.activeElement
            ? document.activeElement.tagName
            : "";

        if (
            [
                "INPUT",
                "TEXTAREA",
                "SELECT",
                "BUTTON",
                "A"
            ].includes(tag)
        ) {
            return;
        }

        if (evento.code === "Space") {
            evento.preventDefault();
            alternarPausa();
        }

        if (evento.key === "ArrowRight") {
            evento.preventDefault();

            escolherTela(
                (telaAtual + 1) % 4
            );
        }

        if (evento.key === "ArrowLeft") {
            evento.preventDefault();

            escolherTela(
                (telaAtual + 3) % 4
            );
        }
    });

    // =====================================================
    // ROTAÇÃO AUTOMÁTICA
    // =====================================================

    setInterval(() => {
        atualizarRelogio();

        if (!pausado && dados) {
            segundosDecorridos += 1;

            if (
                segundosDecorridos >= dados.segundos_tela
            ) {
                // Ao completar as quatro telas, avança
                // o grupo das listas e dos avisos.
                if (telaAtual === 3) {
                    cicloAtual += 1;
                }

                escolherTela(
                    (telaAtual + 1) % 4
                );
            }
        }

        atualizarContador();

    }, 1000);

    // =====================================================
    // INICIALIZAÇÃO
    // =====================================================

    atualizarRelogio();
    consultarDados();

    setInterval(
        consultarDados,
        INTERVALO_ATUALIZACAO
    );

})();