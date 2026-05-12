function abrirFecharSidinho() {
  const painel = document.getElementById("sidinhoChatPanel");
  const bolinha = document.getElementById("sidinhoBubble");

  painel.classList.toggle("sidinho-open");
  bolinha.classList.toggle("sidinho-active");
}

function sidinhoAguardar(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function sidinhoAdicionarMensagem(tipo, texto) {
  const chat = document.getElementById("sidinhoMessages");

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
}

function sidinhoMostrarDigitando() {
  sidinhoRemoverDigitando();

  const chat = document.getElementById("sidinhoMessages");

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

  if (!pergunta) return;

  sidinhoAdicionarMensagem("user", pergunta);
  input.value = "";

  sidinhoLoading(true);
  sidinhoMostrarDigitando();

  const tempoMinimoDigitando = sidinhoAguardar(1200);

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
  input.value = pergunta;
  sidinhoEnviarPergunta();
}