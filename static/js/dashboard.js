// ===== MODAL =====
function abrirModal(mes, valor){
  const modal = document.getElementById("modalMes");

  document.getElementById("modalTitulo").innerText = "📊 " + mes;
  document.getElementById("modalInfo").innerText = "Total de manutenções: " + valor;

  // ===== FROTAS =====
  const listaFrotas = document.getElementById("listaFrotas");
  listaFrotas.innerHTML = "";

  (window.detalheFrotas || []).forEach((f, i) => {
    listaFrotas.innerHTML += `
      <li class="list-group-item d-flex justify-content-between">
        <span>#${i+1} - Frota ${f[0]}</span>
        <strong>${f[1]}</strong>
      </li>`;
  });

  // ===== TIPOS =====
  const listaTipos = document.getElementById("listaTipos");
  listaTipos.innerHTML = "";

  (window.detalheTipos || []).forEach((t, i) => {
    listaTipos.innerHTML += `
      <li class="list-group-item d-flex justify-content-between">
        <span>#${i+1} - ${t[0]}</span>
        <strong>${t[1]}</strong>
      </li>`;
  });

  modal.classList.add("ativo");
}

function fecharModal(){
  document.getElementById("modalMes").classList.remove("ativo");
}


// ===== FECHAR CLICANDO FORA =====
document.addEventListener("click", function(e){
  const modal = document.getElementById("modalMes");
  const content = document.querySelector(".modal-content-custom");

  if(modal.classList.contains("ativo")){
    if(content && !content.contains(e.target)){
      modal.classList.remove("ativo");
    }
  }
});


// ===== EVITA FECHAR AO CLICAR DENTRO =====
document.addEventListener("DOMContentLoaded", function(){
  const content = document.querySelector(".modal-content-custom");

  if(content){
    content.addEventListener("click", function(e){
      e.stopPropagation();
    });
  }
});


// ===== GRÁFICO TIPOS =====
function renderTipos(tipos){

  if(!tipos || tipos.length === 0){
    console.log("Sem dados de tipos");
    return;
  }

  const canvas = document.getElementById("graficoTipos");
  if(!canvas) return;

  const ctx = canvas.getContext("2d");

  // 🔥 evita erro do destroy
  if(window.graficoTipos instanceof Chart){
    window.graficoTipos.destroy();
  }

  window.graficoTipos = new Chart(ctx, {
    type:"bar",
    data:{
      labels:tipos.map(t=>t[0] || "Sem tipo"),
      datasets:[{
        data:tipos.map(t=>t[1]),
        backgroundColor:[
          "rgba(255,77,79,0.85)",
          "rgba(82,196,26,0.85)",
          "rgba(250,173,20,0.85)",
          "rgba(22,119,255,0.85)"
        ],
        borderRadius:12
      }]
    },
    options:{
      plugins:{
        legend:{ display:false },
        datalabels:{
          color:"#111",
          font:{ weight:"bold" }
        }
      }
    },
    plugins: window.ChartDataLabels ? [ChartDataLabels] : []
  });

}


// ===== GRÁFICO EVOLUÇÃO =====
function renderEvolucao(evolucao){

  if(!evolucao || evolucao.length === 0){
    console.log("Sem dados de evolução");
    return;
  }

  const canvas = document.getElementById("graficoFrotas");
  if(!canvas) return;

  const ctx = canvas.getContext("2d");

  // 🔥 evita erro do destroy
  if(window.graficoEvolucao instanceof Chart){
    window.graficoEvolucao.destroy();
  }

  const valores = evolucao.map(e => e[1]);

  const media = valores.reduce((a,b)=>a+b,0) / valores.length;

  const gradient = ctx.createLinearGradient(0,0,0,400);
  gradient.addColorStop(0,"rgba(22,119,255,0.7)");
  gradient.addColorStop(1,"rgba(22,119,255,0)");

  window.graficoEvolucao = new Chart(ctx,{
    type:"line",
    data:{
      labels:evolucao.map(e=>e[0]),
      datasets:[

        {
          label:"Manutenções",
          data:valores,
          borderColor:"#1677ff",
          backgroundColor:gradient,
          fill:true,
          tension:.5,
          borderWidth:3,
          pointRadius:6,
          pointHoverRadius:8
        },

        {
          label:"Média",
          data: Array(valores.length).fill(media),
          borderColor:"#999",
          borderDash:[6,6],
          pointRadius:0,
          fill:false
        }

      ]
    },

    options:{
      onClick: function(evt){

        const points = window.graficoEvolucao.getElementsAtEventForMode(
          evt,
          'nearest',
          { intersect: true },
          true
        );

        if(points.length > 0){
          const index = points[0].index;

          const mes = evolucao[index][0];
          const valor = evolucao[index][1];

          abrirModal(mes, valor);
        }
      },

      plugins:{
        legend:{ display:false }
      },

      scales:{
        y:{ beginAtZero:true }
      }
    }

  });

}