console.log("JS CARREGOU 🚀");

document.addEventListener("DOMContentLoaded", function () {

  // =========================
  // 🔥 REGISTRA PLUGIN DE LABELS
  // =========================
  if (typeof Chart !== "undefined" && typeof ChartDataLabels !== "undefined") {
    Chart.register(ChartDataLabels);
  }

  const styles = getComputedStyle(document.documentElement);
  const c1 = styles.getPropertyValue("--gradient-start").trim();
  const c2 = styles.getPropertyValue("--gradient-mid").trim();
  const c3 = styles.getPropertyValue("--gradient-end").trim();

  function criarGradient(ctx) {
    const gradient = ctx.createLinearGradient(0, 0, 400, 0);
    gradient.addColorStop(0, c1 || "#020024");
    gradient.addColorStop(0.5, c2 || "#090979");
    gradient.addColorStop(1, c3 || "#00d4ff");
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
      align: "top",
      offset: 2,
      clamp: false,
      clip: false
    };
  }

  function moeda(valor) {
    const numero = Number(valor || 0);

    return numero.toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL"
    });
  }

  function numeroCompacto(valor) {
    const numero = Number(valor || 0);
    const absoluto = Math.abs(numero);

    if (absoluto >= 1000000) {
      return (numero / 1000000).toLocaleString("pt-BR", {
        maximumFractionDigits: 1
      }) + " mi";
    }

    if (absoluto >= 1000) {
      return (numero / 1000).toLocaleString("pt-BR", {
        maximumFractionDigits: 0
      }) + "k";
    }

    return numero.toLocaleString("pt-BR", {
      maximumFractionDigits: 0
    });
  }

  function temValor(valor) {
    return Number(valor || 0) !== 0;
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
              display: true,
              color: "#fff",
              font: {
                weight: "900",
                size: 11
              },
              formatter: function (value, context) {
                const total = context.chart._metasets[0].total;

                if (!total) {
                  return "0%";
                }

                return ((value / total) * 100).toFixed(1) + "%";
              }
            }
          }
        }
      });
    }
  }

  // =========================
  // 🔥 MENSAL MANUTENÇÕES
  // =========================
  const elMes = document.getElementById("dados-mes");

  if (elMes) {
    const dadosMes = JSON.parse(elMes.textContent);
    const ctxMes = document.getElementById("graficoMes");

    if (ctxMes) {
      const params = new URLSearchParams(window.location.search);
      const mesFiltrado = params.get("mes");

      let datasetsMensal;

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
      } else {
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
        }
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
              display: true,
              color: "#fff",
              font: {
                weight: "900",
                size: 11
              },
              formatter: function (value, context) {
                const total = context.chart._metasets[0].total;

                if (!total) {
                  return "0%";
                }

                return ((value / total) * 100).toFixed(1) + "%";
              }
            }
          }
        }
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
          layout: {
            padding: {
              top: 25
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              grace: "15%"
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
        }
      });
    }
  }

  // =========================================================
  // 💰 GESTÃO - EVOLUÇÃO FINANCEIRA MENSAL
  // =========================================================
  const elEvolucaoFinanceira = document.getElementById("dados-evolucao-financeira");

  if (elEvolucaoFinanceira) {
    const dados = JSON.parse(elEvolucaoFinanceira.textContent);

    const ctxEntradasSaidas = document.getElementById("graficoEvolucaoEntradasSaidas");
    const ctxLucro = document.getElementById("graficoEvolucaoLucro");

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

          layout: {
            padding: {
              top: 35
            }
          },

          scales: {
            y: {
              beginAtZero: true,
              grace: "22%",
              ticks: {
                callback: function (value) {
                  return moeda(value);
                }
              }
            }
          },

          plugins: {
            legend: {
              position: "top"
            },

            tooltip: {
              callbacks: {
                label: function (context) {
                  return `${context.dataset.label}: ${moeda(context.raw)}`;
                }
              }
            },

            datalabels: {
              display: function (context) {
                return temValor(context.raw);
              },
              formatter: function (value) {
                return numeroCompacto(value);
              },
              color: "#111827",
              font: {
                weight: "900",
                size: 11
              },
              anchor: "end",
              align: "top",
              offset: 2,
              clamp: false,
              clip: false
            }
          }
        }
      });
    }

    if (ctxLucro) {
      new Chart(ctxLucro, {
        type: "line",
        data: {
          labels: dados.labels,
          datasets: [
            {
              label: "Resultado",
              data: dados.lucros,
              borderColor: "#2563eb",
              backgroundColor: "rgba(37, 99, 235, 0.15)",
              tension: 0.35,
              fill: true,
              pointRadius: 5,
              pointHoverRadius: 7,
              pointBackgroundColor: "#ffffff",
              pointBorderColor: "#2563eb",
              pointBorderWidth: 2
            }
          ]
        },
        options: {
          ...configPadrao(),

          layout: {
            padding: {
              top: 35,
              bottom: 18
            }
          },

          scales: {
            y: {
              grace: "25%",
              ticks: {
                callback: function (value) {
                  return moeda(value);
                }
              }
            }
          },

          plugins: {
            legend: {
              position: "top"
            },

            tooltip: {
              callbacks: {
                label: function (context) {
                  return `${context.dataset.label}: ${moeda(context.raw)}`;
                }
              }
            },

            datalabels: {
              display: function (context) {
                return temValor(context.raw);
              },
              formatter: function (value) {
                return numeroCompacto(value);
              },
              color: function (context) {
                return Number(context.raw || 0) < 0 ? "#dc2626" : "#059669";
              },
              font: {
                weight: "900",
                size: 11
              },
              anchor: "end",
              align: function (context) {
                return Number(context.raw || 0) < 0 ? "bottom" : "top";
              },
              offset: 6,
              clamp: false,
              clip: false
            }
          }
        }
      });
    }
  }

});