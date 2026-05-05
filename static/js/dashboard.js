console.log("JS CARREGOU 🚀");

document.addEventListener("DOMContentLoaded", function () {

  const styles = getComputedStyle(document.documentElement);
  const c1 = styles.getPropertyValue('--gradient-start').trim();
  const c2 = styles.getPropertyValue('--gradient-mid').trim();
  const c3 = styles.getPropertyValue('--gradient-end').trim();

  function criarGradient(ctx) {
    const gradient = ctx.createLinearGradient(0, 0, 400, 0);
    gradient.addColorStop(0, c1);
    gradient.addColorStop(0.5, c2);
    gradient.addColorStop(1, c3);
    return gradient;
  }

  function configPadrao() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      hover: { animationDuration: 0 },
      responsiveAnimationDuration: 0,
      interaction: { mode: 'index', intersect: false }
    };
  }

  function estiloBarra(ctx) {
    return {
      backgroundColor: criarGradient(ctx),
      borderRadius: 6,
      maxBarThickness: 35
    };
  }

  function datalabelPadrao() {
    return {
      display: true,
      formatter: value => value,
      color: '#111',
      font: { weight: 'bold', size: 10 },
      anchor: 'end',
      align: 'top'
    };
  }

  // =========================
  // 🔥 INTERNO VS EXTERNO
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
          ...configPadrao(),
          plugins: {
            datalabels: {
              color: "#fff",
              formatter: function(value, context) {
                const total = context.chart._metasets[0].total;
                return ((value / total) * 100).toFixed(1) + "%";
              }
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    }
  }

  // =========================
  // 🔥 MENSAL
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
            ...estiloBarra(ctx)
          }]
        },
        options: {
          ...configPadrao(),
          plugins: {
            datalabels: datalabelPadrao()
          }
        },
        plugins: [ChartDataLabels]
      });
    }
  }

  // =========================
  // 🔥 CORRETIVA GRANDE (FIXADO)
  // =========================
  const elCorretiva = document.getElementById("dados-corretiva");

  if (elCorretiva) {
    const dados = JSON.parse(elCorretiva.textContent);
    const ctx = document.getElementById("graficoCorretivaGrande");

    if (ctx) {
      new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: dados.labels,
          datasets: [{
            data: dados.valores,
            backgroundColor: ["#00d4ff", "#020024"],
            borderWidth: 0
          }]
        },
        options: {
          ...configPadrao(),
          cutout: "65%", // 🔥 igual ao outro (mais elegante)
          plugins: {
            legend: {
              position: 'top' // 🔥 IGUAL AO INTERNO
            },
            datalabels: {
              color: "#fff",
              formatter: function(value, context) {
                const total = context.chart._metasets[0].total;
                return ((value / total) * 100).toFixed(1) + "%";
              }
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
    const dadosPareto = JSON.parse(elPareto.textContent);
    const ctxPareto = document.getElementById("graficoPareto");

    if (ctxPareto) {
      const ctx = ctxPareto.getContext("2d");

      new Chart(ctxPareto, {
        type: 'bar',
        data: {
          labels: dadosPareto.labels,
          datasets: [
            {
              label: 'Manutenções',
              data: dadosPareto.valores,
              ...estiloBarra(ctx)
            },
            {
              label: '% Acumulado',
              data: dadosPareto.percentual,
              type: 'line',
              borderColor: '#ff8c00',
              backgroundColor: '#ff8c00',
              tension: 0.3,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          ...configPadrao(),
          scales: {
            y: { beginAtZero: true },
            y1: {
              position: 'right',
              beginAtZero: true,
              max: 100,
              grid: { drawOnChartArea: false }
            }
          },
          plugins: {
            datalabels: datalabelPadrao()
          }
        },
        plugins: [ChartDataLabels]
      });
    }
  }

});