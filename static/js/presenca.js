(function () {
  "use strict";

  const HEARTBEAT_INTERVALO = 30000;
  const LISTA_INTERVALO = 30000;

  const wrapper = document.getElementById("easyOnlineWrapper");
  const botao = document.getElementById("easyOnlineButton");
  const popover = document.getElementById("easyOnlinePopover");
  const contador = document.getElementById("easyOnlineCount");
  const totalCabecalho = document.getElementById("easyOnlineHeaderTotal");
  const lista = document.getElementById("easyOnlineList");
  const atualizado = document.getElementById("easyOnlineUpdated");

  function requisicao(url, opcoes) {
    return fetch(url, {
      credentials: "same-origin",
      cache: "no-store",
      ...opcoes
    });
  }

  async function registrarPresenca() {
    try {
      await requisicao("/api/presenca", {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        }
      });
    } catch (erro) {
      // Falhas temporárias de rede não devem interromper a navegação.
      console.debug("Presença não atualizada:", erro);
    }
  }

  function criarItemUsuario(nome) {
    const item = document.createElement("div");
    item.className = "easy-online-item";

    const ponto = document.createElement("span");
    ponto.className = "easy-online-dot";
    ponto.setAttribute("aria-hidden", "true");

    const texto = document.createElement("span");
    texto.textContent = nome;

    item.appendChild(ponto);
    item.appendChild(texto);

    return item;
  }

  function mostrarEstado(mensagem) {
    if (!lista) return;

    lista.innerHTML = "";
    const estado = document.createElement("div");
    estado.className = "easy-online-state";
    estado.textContent = mensagem;
    lista.appendChild(estado);
  }

  async function carregarUsuariosOnline() {
    if (!wrapper || !contador || !lista) return;

    try {
      const resposta = await requisicao("/api/usuarios-online", { method: "GET" });

      if (!resposta.ok) {
        if (resposta.status === 401 || resposta.status === 403) {
          wrapper.hidden = true;
          return;
        }
        throw new Error("Falha ao consultar usuários online");
      }

      const dados = await resposta.json();
      const usuarios = Array.isArray(dados.usuarios) ? dados.usuarios : [];
      const total = Number.isFinite(dados.total) ? dados.total : usuarios.length;

      contador.textContent = String(total);

      if (totalCabecalho) {
        totalCabecalho.textContent = total === 1 ? "1 usuário" : `${total} usuários`;
      }

      lista.innerHTML = "";

      if (!usuarios.length) {
        mostrarEstado("Nenhum usuário online no momento.");
      } else {
        usuarios.forEach(usuario => {
          lista.appendChild(criarItemUsuario(usuario.nome || "Usuário"));
        });
      }

      if (atualizado) {
        atualizado.textContent = "Atualizado agora";
      }
    } catch (erro) {
      mostrarEstado("Não foi possível atualizar a lista.");
      if (atualizado) atualizado.textContent = "Falha na atualização";
      console.debug("Lista online não atualizada:", erro);
    }
  }

  function fecharPopover() {
    if (!popover || !botao) return;
    popover.classList.remove("is-open");
    popover.setAttribute("aria-hidden", "true");
    botao.setAttribute("aria-expanded", "false");
  }

  function abrirPopover() {
    if (!popover || !botao) return;
    popover.classList.add("is-open");
    popover.setAttribute("aria-hidden", "false");
    botao.setAttribute("aria-expanded", "true");
    carregarUsuariosOnline();
  }

  if (botao && popover) {
    botao.addEventListener("click", function (evento) {
      evento.stopPropagation();
      const aberto = popover.classList.contains("is-open");
      aberto ? fecharPopover() : abrirPopover();
    });

    popover.addEventListener("click", function (evento) {
      evento.stopPropagation();
    });

    document.addEventListener("click", fecharPopover);

    document.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape") fecharPopover();
    });
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") {
      registrarPresenca();
      carregarUsuariosOnline();
    }
  });

  registrarPresenca();
  carregarUsuariosOnline();

  window.setInterval(registrarPresenca, HEARTBEAT_INTERVALO);
  window.setInterval(carregarUsuariosOnline, LISTA_INTERVALO);
})();
