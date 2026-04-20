console.log("JS CARREGOU 🚀");

document.addEventListener("DOMContentLoaded", function () {

  // 🔥 GRAFICO PIZZA (INTERNO VS EXTERNO)
  const elAtendimento = document.getElementById("dados-atendimento");

  if (elAtendimento) {
    const dados = JSON.parse(elAtendimento.textContent);
    const ctx = document.getElementById("graficoAtendimento");

    if (ctx) {
      new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: dados.labels,
          datasets: [{
            data: dados.valores,
            backgroundColor: [
              "#020024",
              "#090979",
              "#00d4ff"
            ]
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom'
            }
          }
        }
      });
    }
  }

  // 🔥 GRAFICO POR MÊS
  const elMes = document.getElementById("dados-mes");

  if (elMes) {
    const dadosMes = JSON.parse(elMes.textContent);
    const ctxMes = document.getElementById("graficoMes");

    if (ctxMes) {

      const gradientMes = ctxMes.getContext("2d").createLinearGradient(0, 0, 0, 300);
      gradientMes.addColorStop(0, "#020024");
      gradientMes.addColorStop(0.5, "#090979");
      gradientMes.addColorStop(1, "#00d4ff");

      new Chart(ctxMes, {
        type: 'bar',
        data: {
          labels: dadosMes.labels,
          datasets: [{
            label: 'Manutenções',
            data: dadosMes.valores,
            backgroundColor: gradientMes,
            borderColor: "#020024",
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false
        }
      });
    }
  }

  // 🔥 GRAFICO POR TIPO
  const elTipo = document.getElementById("dados-tipo");

  if (elTipo) {
    const dadosTipo = JSON.parse(elTipo.textContent);
    const ctxTipo = document.getElementById("graficoTipo");

    if (ctxTipo) {

      const gradientTipo = ctxTipo.getContext("2d").createLinearGradient(0, 0, 0, 300);
      gradientTipo.addColorStop(0, "#020024");
      gradientTipo.addColorStop(0.5, "#090979");
      gradientTipo.addColorStop(1, "#00d4ff");

      new Chart(ctxTipo, {
        type: 'bar',
        data: {
          labels: dadosTipo.labels,
          datasets: [{
            label: 'Tipos de Manutenção',
            data: dadosTipo.valores,
            backgroundColor: gradientTipo,
            borderColor: "#020024",
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,

          onClick: (evt, elements, chart) => {
            if (elements.length > 0) {
              const index = elements[0].index;
              const tipo = chart.data.labels[index];

              abrirModalTipo(tipo);
            }
          }
        }
      });
    }
  }

  // 🔥 TOP FROTAS
  const elFrota = document.getElementById("dados-frota");

  if (elFrota) {
    const dadosFrota = JSON.parse(elFrota.textContent);
    const ctxFrota = document.getElementById("graficoFrota");

    if (ctxFrota) {

      const gradientFrota = ctxFrota.getContext("2d").createLinearGradient(0, 0, 0, 300);
      gradientFrota.addColorStop(0, "#020024");
      gradientFrota.addColorStop(0.5, "#090979");
      gradientFrota.addColorStop(1, "#00d4ff");

      new Chart(ctxFrota, {
        type: 'bar',
        data: {
          labels: dadosFrota.labels,
          datasets: [{
            label: 'Quantidade',
            data: dadosFrota.valores,
            backgroundColor: gradientFrota,
            borderColor: "#020024",
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,

          onClick: (evt, elements, chart) => {
            if (elements.length > 0) {
              const index = elements[0].index;
              const frota = chart.data.labels[index];

              abrirGraficoFrota(frota);
            }
          }
        }
      });
    }
  }

});


// 🔥 MODAL POR TIPO
function abrirModalTipo(tipo) {

  const el = document.getElementById("dados-tipos-detalhe");
  if (!el) return;

  const dados = JSON.parse(el.textContent);

  const lista =
    dados[tipo] ||
    dados[tipo.toUpperCase()] ||
    dados[tipo.toLowerCase()];

  if (!lista || lista.length === 0) return;

  const container = document.getElementById("listaTipo");
  container.innerHTML = "";

  lista.forEach(item => {
    container.innerHTML += `
      <a href="/manutencoes?frota=${item.frota}" class="linha-tipo text-decoration-none">
        <div>
          🚚 <strong>Frota ${item.frota}</strong><br>
          <small class="text-muted">${item.data}</small>
        </div>
        <span class="badge-tipo">${tipo}</span>
      </a>
    `;
  });

  document.getElementById("tituloModalTipo").innerText = tipo;

  new bootstrap.Modal(
    document.getElementById("modalTipo")
  ).show();
}


// 🔥 GRÁFICO DETALHE FROTA
let chartFrota = null;

function abrirGraficoFrota(frota) {

  const el = document.getElementById("dados-frotas");
  if (!el) return;

  const dados = JSON.parse(el.textContent);
  const dadosFrota = dados[frota];

  if (!dadosFrota) return;

  const labels = Object.keys(dadosFrota);
  const valores = Object.values(dadosFrota);

  if (chartFrota) chartFrota.destroy();

  const ctx = document.getElementById("graficoFrotaDetalhe").getContext("2d");

  const gradientLine = ctx.createLinearGradient(0, 0, 0, 300);
  gradientLine.addColorStop(0, "rgba(0,212,255,0.4)");
  gradientLine.addColorStop(1, "rgba(2,0,36,0)");

  chartFrota = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: `Frota ${frota}`,
        data: valores,
        borderColor: "#020024",
        backgroundColor: gradientLine,
        fill: true,
        tension: 0.3
      }]
    }
  });

  new bootstrap.Modal(
    document.getElementById("modalFrota")
  ).show();
}