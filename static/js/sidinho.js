const SIDINHO_STORAGE_KEY = "sidinho_chat_historico_v1";

function abrirFecharSidinho() {
  const painel = document.getElementById("sidinhoChatPanel");
  const bolinha = document.getElementById("sidinhoBubble");

  painel.classList.toggle("sidinho-open");
  bolinha.classList.toggle("sidinho-active");
}

function sidinhoAguardar(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function sidinhoObterHistorico() {
  try {
    const bruto = localStorage.getItem(SIDINHO_STORAGE_KEY);

    if (!bruto) {
      return [];
    }

    return JSON.parse(bruto) || [];
  } catch (error) {
    return [];
  }
}

function sidinhoSalvarHistorico(historico) {
  try {
    const ultimas = historico.slice(-40);
    localStorage.setItem(SIDINHO_STORAGE_KEY, JSON.stringify(ultimas));
  } catch (error) {
    console.warn("Não foi possível salvar histórico do Sidinho:", error);
  }
}

function sidinhoRegistrarHistorico(tipo, texto) {
  const historico = sidinhoObterHistorico();

  historico.push({
    tipo,
    texto,
    data: new Date().toISOString()
  });

  sidinhoSalvarHistorico(historico);
}

function sidinhoLimparHistorico() {
  localStorage.removeItem(SIDINHO_STORAGE_KEY);

  const chat = document.getElementById("sidinhoMessages");

  if (!chat) {
    return;
  }

  chat.innerHTML = "";

  sidinhoAdicionarMensagem(
    "bot",
    "Histórico limpo. Como posso te ajudar agora?",
    true
  );
}

function sidinhoAdicionarMensagem(tipo, texto, salvar = true) {
  const chat = document.getElementById("sidinhoMessages");

  if (!chat) {
    return;
  }

  const linha = document.createElement("div");
  linha.className = tipo === "user"
    ? "sidinho-message sidinho-user"
    : "sidinho-message sidinho-bot";

  const balao = document.createElement("div");
  balao.className = "sidinho-balloon";
  balao.textContent = texto;

  linha.appendChild(balao);
  chat.appendChild(linha);

  chat.scrollTop = chat.scrollHeight;

  if (salvar) {
    sidinhoRegistrarHistorico(tipo, texto);
  }
}

function sidinhoCarregarHistorico() {
  const chat = document.getElementById("sidinhoMessages");

  if (!chat) {
    return;
  }

  const historico = sidinhoObterHistorico();

  if (!historico.length) {
    return;
  }

  chat.innerHTML = "";

  historico.forEach(item => {
    sidinhoAdicionarMensagem(item.tipo, item.texto, false);
  });

  chat.scrollTop = chat.scrollHeight;
}

function sidinhoMostrarDigitando() {
  sidinhoRemoverDigitando();

  const chat = document.getElementById("sidinhoMessages");

  if (!chat) {
    return;
  }

  const linha = document.createElement("div");
  linha.className = "sidinho-message sidinho-bot";
  linha.id = "sidinhoTyping";

  const balao = document.createElement("div");
  balao.className = "sidinho-balloon sidinho-typing-balloon";

  balao.innerHTML = `
    <span class="sidinho-typing-text">Sidinho está analisando</span>
    <span class="sidinho-typing-dots">
      <span></span>
      <span></span>
      <span></span>
    </span>
  `;

  linha.appendChild(balao);
  chat.appendChild(linha);

  chat.scrollTop = chat.scrollHeight;
}

function sidinhoRemoverDigitando() {
  const typing = document.getElementById("sidinhoTyping");

  if (typing) {
    typing.remove();
  }
}

function sidinhoLoading(ativo) {
  const btn = document.getElementById("sidinhoSendBtn");
  const input = document.getElementById("sidinhoInput");

  if (!btn || !input) {
    return;
  }

  if (ativo) {
    btn.disabled = true;
    input.disabled = true;
    btn.innerText = "...";
  } else {
    btn.disabled = false;
    input.disabled = false;
    btn.innerText = "➤";
    input.focus();
  }
}

async function sidinhoEnviarPergunta() {
  const input = document.getElementById("sidinhoInput");
  const pergunta = input.value.trim();

  if (!pergunta) {
    return;
  }

  sidinhoAdicionarMensagem("user", pergunta);
  input.value = "";

  sidinhoLoading(true);
  sidinhoMostrarDigitando();

  const tempoMinimoDigitando = sidinhoAguardar(1300);

  try {
    const requisicao = fetch("/assistente/perguntar", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ pergunta })
    });

    const resposta = await requisicao;
    const dados = await resposta.json();

    await tempoMinimoDigitando;

    sidinhoRemoverDigitando();

    sidinhoAdicionarMensagem(
      "bot",
      dados.resposta || "Não consegui responder agora."
    );

  } catch (error) {
    await tempoMinimoDigitando;

    sidinhoRemoverDigitando();

    sidinhoAdicionarMensagem(
      "bot",
      "Tive um problema para consultar os dados agora. Tente novamente."
    );
  }

  sidinhoLoading(false);
}

function sidinhoEnter(event) {
  if (event.key === "Enter") {
    sidinhoEnviarPergunta();
  }
}

function sidinhoPerguntaRapida(pergunta) {
  const input = document.getElementById("sidinhoInput");

  if (!input) {
    return;
  }

  input.value = pergunta;
  sidinhoEnviarPergunta();
}

document.addEventListener("DOMContentLoaded", function () {
  sidinhoCarregarHistorico();
});