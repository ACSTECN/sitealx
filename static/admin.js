const tabela = document.getElementById("tabela");
const thead = document.getElementById("thead");
const filtroHotzone = document.getElementById("filtro-hotzone");
const aplicarFiltro = document.getElementById("aplicar-filtro");
const pageSizeSel = document.getElementById("page-size");
const prevBtn = document.getElementById("prev-page");
const nextBtn = document.getElementById("next-page");
const pageInfo = document.getElementById("page-info");
const exportBtn = document.getElementById("exportar-csv");
let chart;
let page = 1;
let totalPages = 1;
let currentRows = [];

const tipoLabels = {
  "sugestao": "Sugestão",
  "reclamacao": "Reclamação",
  "outros": "Outros"
};

function formatTipo(tipo) {
  return tipoLabels[tipo] || tipo;
}

function formatCPF(cpf) {
  if (!cpf) return "";
  const digits = cpf.replace(/\D/g, "");
  if (digits.length === 11) {
    return digits.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
  }
  return cpf;
}

async function loadData() {
  console.log("=== loadData started ===");
  tabela.innerHTML = "<tr><td>Carregando...</td></tr>";
  const filtro = filtroHotzone.value.trim();
  const pageSize = parseInt(pageSizeSel.value || "10", 10);
  const url = `/api/admin/feedbacks?hotzone=${encodeURIComponent(filtro)}&page=${page}&page_size=${pageSize}`;
  console.log("Fetching URL:", url);
  let dataResp;
  try {
    const r = await fetch(url);
    console.log("Response status:", r.status);
    const text = await r.text();
    console.log("Response raw text:", text);
    dataResp = JSON.parse(text);
    console.log("Parsed dataResp:", dataResp);
  } catch (e) {
    console.error("Fetch/parse error:", e);
    tabela.innerHTML = "<tr><td>Erro de rede: " + e.message + "</td></tr>";
    return;
  }

  let rows;
  let total;
  if (dataResp.ok) {
    console.log("Got ok: true response");
    rows = dataResp.data || [];
    total = dataResp.total || rows.length;
  } else if (Array.isArray(dataResp)) {
    console.log("Got direct array response");
    rows = dataResp;
    total = rows.length;
  } else if (Array.isArray(dataResp.error)) {
    console.log("Got error that is an array");
    rows = dataResp.error;
    total = rows.length;
  } else {
    console.error("Unknown error response:", dataResp);
    tabela.innerHTML = `<tr><td>Erro: ${dataResp.error || "desconhecido"}</td></tr>`;
    return;
  }

  console.log("Using rows:", rows);
  totalPages = Math.max(1, Math.ceil(total / pageSize));
  pageInfo.textContent = `Página ${page} de ${totalPages}`;
  currentRows = rows;
  renderHeader();
  renderTable(currentRows);
  renderChart(rows);
  console.log("=== loadData complete ===");
}

function renderHeader() {
  console.log("renderHeader called");
  if (!thead) return;
  thead.innerHTML = "";
  const tr = document.createElement("tr");
  ["Data", "Nome", "CPF", "Hotzone", "Telefone", "Email", "Tipo", "Satisfação", "Mensagem"].forEach(h => {
    const th = document.createElement("th");
    th.textContent = h;
    th.style.textAlign = "left";
    th.style.padding = "16px";
    tr.appendChild(th);
  });
  thead.appendChild(tr);
}

function renderTable(rows) {
  console.log("renderTable called with rows:", rows);
  tabela.innerHTML = "";
  if (!rows.length) {
    tabela.innerHTML = "<tr><td>Nenhum dado encontrado</td></tr>";
    return;
  }
  rows.forEach(r => {
    const tr = document.createElement("tr");
    // Converte satisfação do banco (1-5) para 1-10
    const satisfaçãoExibida = (r.satisfacao || 1) * 2;
    const cells = [
      new Date(r.created_at).toLocaleString("pt-BR"),
      r.nome_completo || r["nome completo"] || "",
      formatCPF(r.cpf),
      r.hotzone,
      r.telefone,
      r.email,
      formatTipo(r.tipo),
      satisfaçãoExibida,
      r.mensagem
    ];
    cells.forEach(c => {
      const td = document.createElement("td");
      td.textContent = c;
      td.style.padding = "16px";
      td.style.verticalAlign = "top";
      tr.appendChild(td);
    });
    tabela.appendChild(tr);
  });
}

function renderChart(rows) {
  console.log("renderChart called");
  const counts = [0,0,0,0,0,0,0,0,0,0]; // 1-10
  rows.forEach(r => {
    const satisfaçãoDb = r.satisfacao || 1; // 1-5
    const satisfação1a10 = satisfaçãoDb * 2;
    const i = satisfação1a10 - 1;
    if (i >=0 && i < 10) counts[i]++;
  });
  const canvas = document.getElementById("chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["1","2","3","4","5","6","7","8","9","10"],
      datasets: [{
        label: "Satisfação",
        data: counts,
        backgroundColor: ["#ef4444","#f97316","#f59e0b","#fcd34d","#fde047","#a3e635","#34d399","#22c55e","#16a34a","#15803d"]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
    }
  });
}

if (aplicarFiltro) {
  aplicarFiltro.addEventListener("click", () => { page = 1; loadData(); });
}
if (prevBtn) {
  prevBtn.addEventListener("click", () => { page = Math.max(1, page - 1); loadData(); });
}
if (nextBtn) {
  nextBtn.addEventListener("click", () => { page = Math.min(totalPages, page + 1); loadData(); });
}
if (pageSizeSel) {
  pageSizeSel.addEventListener("change", () => { page = 1; loadData(); });
}
if (exportBtn) {
  exportBtn.addEventListener("click", () => {
    const headers = ["Data","Nome","CPF","Hotzone","Telefone","Email","Tipo","Satisfação","Mensagem"];
    const lines = [headers.join(";")].concat(currentRows.map(r => [
      new Date(r.created_at).toLocaleString("pt-BR").replace(/;/g,","),
      (r.nome_completo || r["nome completo"] || "").replace(/;/g,","),
      r.cpf || "",
      r.hotzone || "",
      r.telefone || "",
      r.email || "",
      formatTipo(r.tipo || ""),
      r.satisfacao || "",
      (r.mensagem || "").replace(/\n/g," ").replace(/;/g,",")
    ].join(";")));
    const blob = new Blob([lines.join("\n")], {type: "text/csv;charset=utf-8;"});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "feedbacks.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
  });
}
document.addEventListener("DOMContentLoaded", loadData);
