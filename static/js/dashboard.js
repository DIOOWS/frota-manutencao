console.log("JS CARREGOU 🚀");

document.addEventListener("DOMContentLoaded", function () {

  // =========================
  // 🎨 CORES
  // =========================
  const styles = getComputedStyle(document.documentElement);

  const c1 = styles.getPropertyValue('--gradient-start').trim();
  const c2 = styles.getPropertyValue('--gradient-mid').trim();
  const c3 = styles.getPropertyValue('--gradient-end').trim();

  function criarGradient(ctx) {
    const gradient = ctx.createLinearGradient(0, 0, 400, 0);
    gradient.addColorStop(0, c1);
    gradient.addColorStop(0.05, c2);
    gradient.addColorStop(1, c3);
    return gradient;
  }

  function configPadrao() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 1000,
        easing: 'easeOutQuart'
      },
      plugins: {
        tooltip: {
          backgroundColor: "#020024",
          titleColor: "#00d4ff",
          bodyColor: "#ffffff",
          borderColor: "#00d4ff",
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: function(context) {
              if (context.dataset.type === 'line') {
                return context.raw + "%";
              }
              return context.raw + " manutenções";
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          beginAtZero: true,
          grid: { color: "#e5e7eb" }
        }
      }
    };
  }

  // =========================
  // 🔥 DADOS FROTA (CORRIGIDO)
  // =========================
  const elFrota = document.getElementById("dados-frota");

  let dadosFrota = {};

  if (elFrota) {
    dadosFrota = JSON.parse(elFrota.textContent);
  }

  // =========================
  // 🔥 FUNÇÃO CLICK FROTA
  // =========================
  window.verFrota = function(frota) {
    const dados = dadosFrota[frota] || [];

    let html = "";

    if (dados.length === 0) {
      html = "<li>Nenhum registro encontrado</li>";
    } else {
      dados.forEach(item => {
        html += `<li>${item.data} - ${item.tipo}</li>`;
      });
    }

    document.getElementById("detalheFrota").innerHTML = html;
  };

  // =========================
  // 🔥 PIZZA ATENDIMENTO
  // =========================
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
            backgroundColor: ["#01C0F2", "#090979"]
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            datalabels: {
              color: '#000',
              anchor: 'end',
              align: 'end',
              offset: 10,
              formatter: (value) => value + '%',
              font: {
                weight: 'bold',
                size: 14
              }
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    }
  }

  // =========================
  // 🔥 GRÁFICO POR MÊS
  // =========================
  const elMes = document.getElementById("dados-mes");

  if (elMes) {
    const dadosMes = JSON.parse(elMes.textContent);
    const ctxMes = document.getElementById("graficoMes");

    if (ctxMes) {
      const ctx = ctxMes.getContext("2d");

      new Chart(ctxMes, {
        type: 'bar',
        data: {
          labels: dadosMes.labels,
          datasets: [{
            label: 'Manutenções',
            data: dadosMes.valores,
            backgroundColor: criarGradient(ctx),
            barThickness: 60
          }]
        },
        options: {
          ...configPadrao(),
          plugins: {
            ...configPadrao().plugins,
            datalabels: {
              anchor: 'end',
              align: 'top',
              color: '#000',
              font: { weight: 'bold', size: 12 },
              formatter: (v) => v
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    }
  }

  // =========================
  // 🔥 GRÁFICO POR TIPO
  // =========================
  const elTipo = document.getElementById("dados-tipo");

  if (elTipo) {
    const dadosTipo = JSON.parse(elTipo.textContent);
    const ctxTipo = document.getElementById("graficoTipo");

    if (ctxTipo) {
      const ctx = ctxTipo.getContext("2d");

      new Chart(ctxTipo, {
        type: 'bar',
        data: {
          labels: dadosTipo.labels,
          datasets: [{
            label: 'Tipos de Manutenção',
            data: dadosTipo.valores,
            backgroundColor: criarGradient(ctx),
            barThickness: 60
          }]
        },
        options: {
          ...configPadrao(),
          plugins: {
            ...configPadrao().plugins,
            datalabels: {
              anchor: 'end',
              align: 'top',
              color: '#000',
              font: { weight: 'bold', size: 12 },
              formatter: (v) => v
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    }
  }

  // =========================
  // 🔥 PARETO
  // =========================
  const elPareto = document.getElementById("dados-pareto");

  if (elPareto) {
    const dados = JSON.parse(elPareto.textContent);
    const ctxPareto = document.getElementById("graficoPareto");

    if (ctxPareto) {
      const ctx = ctxPareto.getContext("2d");

      new Chart(ctxPareto, {
        data: {
          labels: dados.labels,
          datasets: [
            {
              type: 'bar',
              label: 'Manutenções',
              data: dados.valores,
              backgroundColor: dados.labels.map(label =>
                label === "Outros" ? "#999999" : criarGradient(ctx)
              ),
              barThickness: 60
            },
            {
              type: 'line',
              label: '% Acumulado',
              data: dados.percentual,
              borderColor: '#ff0000',
              borderWidth: 2,
              yAxisID: 'y1',
              tension: 0.4,
              pointRadius: 4,
              pointBackgroundColor: '#ff0000'
            },
            {
              type: 'line',
              label: '80%',
              data: dados.labels.map(() => 80),
              borderColor: '#00ff00',
              borderWidth: 2,
              borderDash: [5, 5],
              pointRadius: 0,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          ...configPadrao(),
          scales: {
            y: { beginAtZero: true },
            y1: {
              beginAtZero: true,
              position: 'right',
              max: 100,
              ticks: {
                callback: v => v + "%"
              }
            }
          },
          plugins: {
            ...configPadrao().plugins,
            datalabels: {
              anchor: 'end',
              align: 'top',
              color: '#000',
              font: { weight: 'bold', size: 12 },
              formatter: (value, ctx) => {
                if (ctx.dataset.type === 'bar') return value;
                return null;
              }
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    }
  }

});