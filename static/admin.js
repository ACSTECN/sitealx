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
    sugestao: "Sugestão",
    reclamacao: "Reclamação",
    outros: "Outros"
};

function formatTipo(tipo) {
    return tipoLabels[tipo] || tipo || "";
}

function formatCPF(cpf) {
    if (!cpf) return "";

    const digits = cpf.replace(/\D/g, "");

    if (digits.length === 11) {
        return digits.replace(
            /(\d{3})(\d{3})(\d{3})(\d{2})/,
            "$1.$2.$3-$4"
        );
    }

    return cpf;
}

function formatDate(data) {
    if (!data) return "";

    return new Date(data).toLocaleString("pt-BR");
}

function renderStars(valor) {
    const nota = Number(valor || 0);
    return "⭐".repeat(Math.min(nota, 5));
}

async function loadData() {
    tabela.innerHTML = `
        <tr>
            <td colspan="9" style="padding:30px;text-align:center;color:#94a3b8;">
                Carregando feedbacks...
            </td>
        </tr>
    `;

    const filtro = filtroHotzone.value.trim();
    const pageSize = parseInt(pageSizeSel.value || "10", 10);

    const url = `/api/admin/feedbacks?hotzone=${encodeURIComponent(filtro)}&page=${page}&page_size=${pageSize}`;

    let dataResp;

    try {
        const r = await fetch(url);
        dataResp = await r.json();
    } catch (e) {
        tabela.innerHTML = `
            <tr>
                <td colspan="9" style="padding:30px;text-align:center;color:#ef4444;">
                    Erro de rede ao carregar feedbacks.
                </td>
            </tr>
        `;
        return;
    }

    let rows = [];
    let total = 0;

    if (Array.isArray(dataResp)) {
        rows = dataResp;
        total = rows.length;
    } else if (dataResp.ok) {
        rows = dataResp.data || [];
        total = dataResp.total || rows.length;
    } else if (Array.isArray(dataResp.error)) {
        rows = dataResp.error;
        total = rows.length;
    } else {
        tabela.innerHTML = `
            <tr>
                <td colspan="9" style="padding:30px;text-align:center;color:#ef4444;">
                    Erro ao carregar dados.
                </td>
            </tr>
        `;
        return;
    }

    totalPages = Math.max(1, Math.ceil(total / pageSize));

    if (page > totalPages) {
        page = totalPages;
    }

    currentRows = rows;

    pageInfo.textContent = `Página ${page} de ${totalPages}`;

    renderHeader();
    renderTable(rows);
    renderChart(rows);
}

function renderHeader() {
    thead.innerHTML = "";

    const tr = document.createElement("tr");

    [
        "Data",
        "Nome",
        "CPF",
        "Hotzone",
        "Telefone",
        "Email",
        "Tipo",
        "Satisfação",
        "Mensagem"
    ].forEach(h => {
        const th = document.createElement("th");
        th.textContent = h;
        tr.appendChild(th);
    });

    thead.appendChild(tr);
}

function renderTable(rows) {
    tabela.innerHTML = "";

    if (!rows.length) {
        tabela.innerHTML = `
            <tr>
                <td colspan="9" style="padding:30px;text-align:center;color:#94a3b8;">
                    Nenhum feedback encontrado.
                </td>
            </tr>
        `;
        return;
    }

    rows.forEach(r => {
        const tr = document.createElement("tr");

        const tipo = formatTipo(r.tipo);

        tr.innerHTML = `
            <td>${formatDate(r.created_at)}</td>
            <td><strong>${r.nome_completo || ""}</strong></td>
            <td>${formatCPF(r.cpf || "")}</td>
            <td>${r.hotzone || ""}</td>
            <td>${r.telefone || ""}</td>
            <td>${r.email || ""}</td>
            <td>
                <span class="tipo-badge ${r.tipo || "outros"}">
                    ${tipo}
                </span>
            </td>
            <td>
                <span class="stars">
                    ${renderStars(r.satisfacao)}
                </span>
            </td>
            <td>${r.mensagem || ""}</td>
        `;

        tabela.appendChild(tr);
    });
}

function renderChart(rows) {
    const counts = [0, 0, 0, 0, 0];

    rows.forEach(r => {
        const nota = Number(r.satisfacao || 0);

        if (nota >= 1 && nota <= 5) {
            counts[nota - 1]++;
        }
    });

    const canvas = document.getElementById("chart");

    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    if (chart) chart.destroy();

    chart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["1", "2", "3", "4", "5"],
            datasets: [{
                label: "Satisfação",
                data: counts,
                backgroundColor: [
                    "#ef4444",
                    "#f97316",
                    "#f59e0b",
                    "#22c55e",
                    "#15803d"
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

if (aplicarFiltro) {
    aplicarFiltro.addEventListener("click", () => {
        page = 1;
        loadData();
    });
}

if (prevBtn) {
    prevBtn.addEventListener("click", () => {
        page = Math.max(1, page - 1);
        loadData();
    });
}

if (nextBtn) {
    nextBtn.addEventListener("click", () => {
        page = Math.min(totalPages, page + 1);
        loadData();
    });
}

if (pageSizeSel) {
    pageSizeSel.addEventListener("change", () => {
        page = 1;
        loadData();
    });
}

if (exportBtn) {
    exportBtn.addEventListener("click", () => {
        const headers = [
            "Data",
            "Nome",
            "CPF",
            "Hotzone",
            "Telefone",
            "Email",
            "Tipo",
            "Satisfação",
            "Mensagem"
        ];

        const lines = [headers.join(";")].concat(
            currentRows.map(r => [
                formatDate(r.created_at).replace(/;/g, ","),
                (r.nome_completo || "").replace(/;/g, ","),
                r.cpf || "",
                r.hotzone || "",
                r.telefone || "",
                r.email || "",
                formatTipo(r.tipo || ""),
                r.satisfacao || "",
                (r.mensagem || "").replace(/\n/g, " ").replace(/;/g, ",")
            ].join(";"))
        );

        const blob = new Blob([lines.join("\n")], {
            type: "text/csv;charset=utf-8;"
        });

        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "feedbacks.csv";
        document.body.appendChild(a);
        a.click();
        a.remove();
    });
}

document.addEventListener("DOMContentLoaded", loadData);