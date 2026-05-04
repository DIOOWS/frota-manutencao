console.log("JS CARREGOU 🚀");

document.addEventListener("DOMContentLoaded", function () {

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
      maintainAspectRatio: false
    };
  }

  function estiloBarra(ctx) {
    return {
      backgroundColor: criarGradient(ctx),
      borderRadius: 6,
      barThickness: 45,
      categoryPercentage: 0.6,
      barPercentage: 0.8
    };
  }

  // 🔥 DATALABEL PADRÃO
  function datalabelPadrao() {
    return {
      display: true,

      formatter: function(value, context) {
        if (context.dataset.type === 'bar') return value;
        if (context.dataset.type === 'line') return value + "%";
        return value;
      },

      color: function(context) {
        return context.dataset.type === 'line'
          ? '#ff0000'
          : '#111';
      },

      font: {
        weight: 'bold',
        size: 10
      },

      anchor: 'end',

      align: function(context) {
        return context.dataset.type === 'line'
          ? 'top'
          : 'end';
      }
    };
  }

  // =========================
  // 🔥 PIZZA (INTERNO VS EXTERNO)
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
              display: true,
              color: "#fff",
              font: { weight: 'bold', size: 12 },
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
  // 🔥 GRÁFICO MENSAL
  // =========================
  const elMes = document.getElementById("dados-mes");
  const elFrotaMes = document.getElementById("dados-frota-mes");

  let dadosFrotaMes = {};

  if (elFrotaMes) {
    dadosFrotaMes = JSON.parse(elFrotaMes.textContent);
  }

  if (elMes) {
    const dadosMes = JSON.parse(elMes.textContent);
    const ctxMes = document.getElementById("graficoMes");

    if (ctxMes) {
      const ctx = ctxMes.getContext("2d");

      new Chart(ctxMes, {
        data: {
          labels: dadosMes.labels,
          datasets: [
            {
              type: 'bar',
              label: 'Manutenções',
              data: dadosMes.valores,
              ...estiloBarra(ctx)
            },
            {
              type: 'line',
              label: 'Crescimento %',
              data: dadosMes.crescimento || [],
              borderColor: '#ff0000',
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
              beginAtZero: true,
              position: 'right'
            }
          },
          plugins: {
            datalabels: datalabelPadrao()
          },
          onClick: function(evt, elements) {
            if (elements.length > 0) {
              const index = elements[0].index;
              const mes = dadosMes.labels_original
                ? dadosMes.labels_original[index]
                : dadosMes.labels[index];

              atualizarRanking(mes);
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    }
  }

  // =========================
  // 🔥 TIPOS
  // =========================
  const elTipo = document.getElementById("dados-tipo");

  if (elTipo) {
    const dados = JSON.parse(elTipo.textContent);
    const ctx = document.getElementById("graficoTipo");

    if (ctx) {
      const c = ctx.getContext("2d");

      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: dados.labels,
          datasets: [{
            data: dados.valores,
            ...estiloBarra(c)
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
  // 🔥 PARETO
  // =========================
  const elPareto = document.getElementById("dados-pareto");

  if (elPareto) {
    const dados = JSON.parse(elPareto.textContent);
    const ctx = document.getElementById("graficoPareto");

    if (ctx) {
      const c = ctx.getContext("2d");

      new Chart(ctx, {
        data: {
          labels: dados.labels,
          datasets: [
            {
            type: 'bar',
            label: 'Manutenções',
            data: dados.valores,
            backgroundColor: criarGradient(c),
            borderRadius: 6,
            barThickness: 35,
            maxBarThickness: 40,
            categoryPercentage: 0.6,
            barPercentage: 0.8
          },
          {
            type: 'line',
            label: '% Acumulado',
            data: dados.percentual,
            borderColor: '#ff0000',
            backgroundColor: '#ff0000',
            tension: 0.4,
            pointRadius: 4,
            pointHoverRadius: 6,
            yAxisID: 'y1'
          }
          ]
        },
        options: {
          scales: {
            y: { beginAtZero: true },
            y1: {
              beginAtZero: true,
              position: 'right'
            }
          },
          plugins: {
            legend: { position: 'top' },
            datalabels: datalabelPadrao()
          }
        },
        plugins: [ChartDataLabels]
      });
    }
  }

  // =========================
  // 🔥 RANKING
  // =========================
  const ctxRank = document.getElementById("graficoRank");

  let graficoRank;

  function atualizarRanking(mes) {

    console.log("CLICOU:", mes);

    const dados = dadosFrotaMes[mes] || {};
    const labels = Object.keys(dados);
    const valores = Object.values(dados);

    if (!ctxRank) return;

    if (graficoRank) {
      graficoRank.destroy();
    }

    const ctx = ctxRank.getContext("2d");

    graficoRank = new Chart(ctxRank, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          data: valores,
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

});