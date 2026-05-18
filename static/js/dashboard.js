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
      hover: {
        animationDuration: 0
      },
      responsiveAnimationDuration: 0,
      interaction: {
        mode: "index",
        intersect: false
      }
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
      color: "#111",
      font: {
        weight: "bold",
        size: 10
      },
      anchor: "end",
      align: "top"
    };
  }

  function moeda(valor) {
    const numero = Number(valor || 0);

    return numero.toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL"
    });
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
        type: "doughnut",
        data: {
          labels: dados.labels,
          datasets: [
            {
              data: dados.valores,
              backgroundColor: ["#01C0F2", "#090979"]
            }
          ]
        },
        options: {
          ...configPadrao(),
          plugins: {
            datalabels: {
              color: "#fff",
              formatter: function (value, context) {
                const total = context.chart._metasets[0].total;

                if (!total) {
                  return "0%";
                }

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
      const params = new URLSearchParams(window.location.search);
      const mesFiltrado = params.get("mes");

      let datasetsMensal;

      // 🔥 SE FILTRO ATIVO (3 BARRAS)
      if (mesFiltrado) {
        datasetsMensal = [
          {
            label: "Corretiva",
            data: dadosMes.corretivas,
            backgroundColor: "#c90000",
            borderRadius: 4,
            maxBarThickness: 35
          },
          {
            label: "Total Manutenção",
            data: dadosMes.valores,
            backgroundColor: "#002b70",
            borderRadius: 4,
            maxBarThickness: 35
          },
          {
            label: "Preventiva",
            data: dadosMes.preventivas,
            backgroundColor: "#4f8733",
            borderRadius: 4,
            maxBarThickness: 35
          }
        ];
      }

      // 🔥 SEM FILTRO (1 BARRA)
      else {
        const ctx = ctxMes.getContext("2d");

        datasetsMensal = [
          {
            label: "Manutenções",
            data: dadosMes.valores,
            ...estiloBarra(ctx)
          }
        ];
      }

      new Chart(ctxMes, {
        type: "bar",
        data: {
          labels: dadosMes.labels,
          datasets: datasetsMensal
        },
        options: {
          ...configPadrao(),

          onClick: function (evt, elements) {
            if (elements.length > 0) {
              const index = elements[0].index;
              const mesSelecionado = dadosMes.labels[index];

              // Converte 05-2026 para 2026-05
              const partes = mesSelecionado.split("-");

              if (partes.length === 2) {
                const mesUrl = `${partes[1]}-${partes[0]}`;
                window.location.href = `/?mes=${mesUrl}`;
              }
            }
          },

          layout: {
            padding: {
              top: 25
            }
          },

          scales: {
            y: {
              beginAtZero: true,
              grace: "15%"
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

  // =========================
  // 🔥 CORRETIVA GRANDE
  // =========================
  const elCorretiva = document.getElementById("dados-corretiva");

  if (elCorretiva) {
    const dados = JSON.parse(elCorretiva.textContent);
    const ctx = document.getElementById("graficoCorretivaGrande");

    if (ctx) {
      new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: dados.labels,
          datasets: [
            {
              data: dados.valores,
              backgroundColor: ["#00d4ff", "#020024"],
              borderWidth: 0
            }
          ]
        },
        options: {
          ...configPadrao(),
          cutout: "65%",
          plugins: {
            legend: {
              position: "top"
            },
            datalabels: {
              color: "#fff",
              formatter: function (value, context) {
                const total = context.chart._metasets[0].total;

                if (!total) {
                  return "0%";
                }

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
        type: "bar",
        data: {
          labels: dadosPareto.labels,
          datasets: [
            {
              label: "Manutenções",
              data: dadosPareto.valores,
              ...estiloBarra(ctx)
            },
            {
              label: "% Acumulado",
              data: dadosPareto.percentual,
              type: "line",
              borderColor: "#ff8c00",
              backgroundColor: "#ff8c00",
              tension: 0.3,
              yAxisID: "y1"
            }
          ]
        },
        options: {
          ...configPadrao(),
          scales: {
            y: {
              beginAtZero: true
            },
            y1: {
              position: "right",
              beginAtZero: true,
              max: 100,
              grid: {
                drawOnChartArea: false
              }
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

  // =========================
  // 💰 GESTÃO - EVOLUÇÃO FINANCEIRA MENSAL
  // =========================
  const elEvolucaoFinanceira = document.getElementById("dados-evolucao-financeira");

  if (elEvolucaoFinanceira) {
    const dados = JSON.parse(elEvolucaoFinanceira.textContent);

    const ctxEntradasSaidas = document.getElementById("graficoEvolucaoEntradasSaidas");
    const ctxLucro = document.getElementById("graficoEvolucaoLucro");
    const ctxSaldo = document.getElementById("graficoEvolucaoSaldo");

    // =========================
    // ENTRADAS X SAÍDAS
    // =========================
    if (ctxEntradasSaidas) {
      new Chart(ctxEntradasSaidas, {
        type: "bar",
        data: {
          labels: dados.labels,
          datasets: [
            {
              label: "Entradas",
              data: dados.entradas,
              backgroundColor: "#10b981",
              borderRadius: 6,
              maxBarThickness: 34
            },
            {
              label: "Saídas",
              data: dados.saidas,
              backgroundColor: "#ef4444",
              borderRadius: 6,
              maxBarThickness: 34
            }
          ]
        },
        options: {
          ...configPadrao(),
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                callback: value => moeda(value)
              }
            }
          },
          plugins: {
            tooltip: {
              callbacks: {
                label: context => `${context.dataset.label}: ${moeda(context.raw)}`
              }
            },
            datalabels: {
              display: false
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    }

    // =========================
    // LUCRO MENSAL
    // =========================
    if (ctxLucro) {
      new Chart(ctxLucro, {
        type: "line",
        data: {
          labels: dados.labels,
          datasets: [
            {
              label: "Lucro",
              data: dados.lucros,
              borderColor: "#2563eb",
              backgroundColor: "rgba(37, 99, 235, 0.15)",
              tension: 0.35,
              fill: true,
              pointRadius: 4,
              pointHoverRadius: 6
            }
          ]
        },
        options: {
          ...configPadrao(),
          scales: {
            y: {
              ticks: {
                callback: value => moeda(value)
              }
            }
          },
          plugins: {
            tooltip: {
              callbacks: {
                label: context => `${context.dataset.label}: ${moeda(context.raw)}`
              }
            },
            datalabels: {
              display: false
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    }

    // =========================
    // SALDO FINAL POR MÊS
    // =========================
    if (ctxSaldo) {
      new Chart(ctxSaldo, {
        type: "bar",
        data: {
          labels: dados.labels,
          datasets: [
            {
              label: "Saldo Final",
              data: dados.saldos_finais,
              backgroundColor: "#0f172a",
              borderRadius: 6,
              maxBarThickness: 42
            }
          ]
        },
        options: {
          ...configPadrao(),
          scales: {
            y: {
              ticks: {
                callback: value => moeda(value)
              }
            }
          },
          plugins: {
            tooltip: {
              callbacks: {
                label: context => `${context.dataset.label}: ${moeda(context.raw)}`
              }
            },
            datalabels: {
              display: false
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    }
  }

});