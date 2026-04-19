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
            data: dados.valores
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
      new Chart(ctxMes, {
        type: 'bar',
        data: {
          labels: dadosMes.labels,
          datasets: [{
            label: 'Manutenções',
            data: dadosMes.valores
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
      new Chart(ctxTipo, {
        type: 'bar',
        data: {
          labels: dadosTipo.labels,
          datasets: [{
            label: 'Tipos de Manutenção',
            data: dadosTipo.valores
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false
        }
      });
    }
  }

  // 🔥 TOP FROTAS (COM CLICK)
  const elFrota = document.getElementById("dados-frota");

  if (elFrota) {
    const dadosFrota = JSON.parse(elFrota.textContent);
    const ctxFrota = document.getElementById("graficoFrota");

    if (ctxFrota) {
      new Chart(ctxFrota, {
        type: 'bar',
        data: {
          labels: dadosFrota.labels,
          datasets: [{
            label: 'Quantidade',
            data: dadosFrota.valores
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          onClick: function(evt, elements) {

            if (elements.length > 0) {
              const index = elements[0].index;
              const frota = this.data.labels[index];

              abrirGraficoFrota(frota);
            }

          }
        }
      });
    }
  }

});


// 🔥 CONTROLE GLOBAL DO CHART
let chartFrota = null;


// 🔥 HISTÓRICO DA FROTA (MODAL)
function abrirGraficoFrota(frota) {

  const el = document.getElementById("dados-frotas");

  if (!el) return;

  const dados = JSON.parse(el.textContent);
  const dadosFrota = dados[frota];

  if (!dadosFrota) return;

  const labels = Object.keys(dadosFrota);
  const valores = Object.values(dadosFrota);

  if (chartFrota) {
    chartFrota.destroy();
  }

  chartFrota = new Chart(
    document.getElementById("graficoFrotaDetalhe"),
    {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: `Frota ${frota}`,
          data: valores,
          borderWidth: 2,
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false
      }
    }
  );

  new bootstrap.Modal(
    document.getElementById("modalFrota")
  ).show();
}