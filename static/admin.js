const tabela = document.getElementById("tabela");
const thead = document.getElementById("thead");
const filtroHotzone = document.getElementById("filtro-hotzone");
const filtroTipo = document.getElementById("filtro-tipo");
const filtroBusca = document.getElementById("filtro-busca");
const filtroAnexo = document.getElementById("filtro-anexo");
const filtroSatisfacaoMin = document.getElementById("filtro-satisfacao-min");
const filtroSatisfacaoMax = document.getElementById("filtro-satisfacao-max");
const filtroDataInicial = document.getElementById("filtro-data-inicial");
const filtroDataFinal = document.getElementById("filtro-data-final");
const filtroOrdenacao = document.getElementById("filtro-ordenacao");
const aplicarFiltro = document.getElementById("aplicar-filtro");
const limparFiltro = document.getElementById("limpar-filtro");
const pageSizeSel = document.getElementById("page-size");
const prevBtn = document.getElementById("prev-page");
const nextBtn = document.getElementById("next-page");
const pageInfo = document.getElementById("page-info");
const exportBtn = document.getElementById("exportar-csv");
const feedbackSummary = document.getElementById("feedback-summary");
const feedbackActiveFilters = document.getElementById("feedback-active-filters");

const adminUserForm = document.getElementById("admin-user-form");
const adminUserStatus = document.getElementById("admin-user-status");
const adminUserEmail = document.getElementById("novo-admin-email");
const adminUserPassword = document.getElementById("novo-admin-senha");
const adminUserHierarchy = document.getElementById("novo-admin-hierarquia");
const adminUsersTable = document.getElementById("admin-users-table");
const adminUsersEmpty = document.getElementById("admin-users-empty");
const cancelAdminEditBtn = document.getElementById("cancelar-admin-edit");
const saveAdminBtn = document.getElementById("criar-admin-btn");

let chart;
let page = 1;
let totalPages = 1;
let currentRows = [];
let adminUsers = [];
let editingAdminEmail = "";

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR");
}

function formatCPF(value) {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 11);
  if (digits.length !== 11) return value || "-";
  return digits.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
}

function formatPhone(value) {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 11);
  if (!digits) return "-";
  if (digits.length === 11) return digits.replace(/(\d{2})(\d{5})(\d{4})/, "($1) $2-$3");
  if (digits.length === 10) return digits.replace(/(\d{2})(\d{4})(\d{4})/, "($1) $2-$3");
  return value || "-";
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (!size) return "";
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  if (size >= 1024) return `${Math.round(size / 1024)} KB`;
  return `${size} B`;
}

function formatFeedbackTypeLabel(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "parceiro") return "Ser Parceiro";
  if (normalized === "sugestao") return "Sugestão";
  if (normalized === "reclamacao") return "Reclamação";
  if (normalized === "outro" || normalized === "outros") return "Outros";
  return value || "-";
}

function getFilters() {
  return {
    hotzone: filtroHotzone?.value || "",
    tipo: filtroTipo?.value || "",
    busca: (filtroBusca?.value || "").trim(),
    attachment_mode: filtroAnexo?.value || "",
    satisfacao_min: filtroSatisfacaoMin?.value || "",
    satisfacao_max: filtroSatisfacaoMax?.value || "",
    data_inicial: filtroDataInicial?.value || "",
    data_final: filtroDataFinal?.value || "",
    sort: filtroOrdenacao?.value || "created_at.desc",
    page_size: pageSizeSel?.value || "10",
  };
}

function getActiveFilterLabels(filters) {
  const labels = [];
  if (filters.hotzone) labels.push(`Hotzone: ${filters.hotzone}`);
  if (filters.tipo) labels.push(`Tipo: ${formatFeedbackTypeLabel(filters.tipo)}`);
  if (filters.busca) labels.push(`Busca: ${filters.busca}`);
  if (filters.attachment_mode === "with") labels.push("Com anexo");
  if (filters.attachment_mode === "without") labels.push("Sem anexo");
  if (filters.satisfacao_min) labels.push(`Satisfação min: ${filters.satisfacao_min}`);
  if (filters.satisfacao_max) labels.push(`Satisfação max: ${filters.satisfacao_max}`);
  if (filters.data_inicial) labels.push(`De: ${filters.data_inicial}`);
  if (filters.data_final) labels.push(`Até: ${filters.data_final}`);
  return labels;
}

function setFeedbackSummary(total) {
  const filters = getFilters();
  const activeLabels = getActiveFilterLabels(filters);
  if (feedbackSummary) {
    const plural = total === 1 ? "" : "s";
    feedbackSummary.textContent = `${total} feedback${plural} encontrado${plural}.`;
  }
  if (feedbackActiveFilters) {
    feedbackActiveFilters.textContent = activeLabels.length ? activeLabels.join(" • ") : "Sem filtros aplicados";
  }
}

function renderHeader() {
  if (!thead) return;
  thead.innerHTML = `
    <tr>
      <th>Data</th>
      <th>Tipo / Hotzone</th>
      <th>Nome</th>
      <th>Contato</th>
      <th>Satisfação</th>
      <th>Anexo</th>
      <th>Mensagem</th>
    </tr>
  `;
}

function renderAttachmentCell(row) {
  if (!row.tem_anexo || !row.anexo_url) {
    return '<span style="color:#7f92a6">Sem anexo</span>';
  }
  const meta = [row.anexo_nome, formatBytes(row.anexo_tamanho)].filter(Boolean).join(" • ");
  return `
    <a class="feedback-attachment" href="${escapeHtml(row.anexo_url)}" target="_blank" rel="noopener">
      Abrir anexo
    </a>
    <div style="margin-top:8px;color:#94a3b8;font-size:12px;line-height:1.6;">
      ${escapeHtml(meta || "Arquivo disponível")}
    </div>
  `;
}

function renderTable(rows) {
  if (!tabela) return;
  tabela.innerHTML = "";
  if (!rows.length) {
    tabela.innerHTML = '<tr><td colspan="7" class="table-empty" data-label="Status">Nenhum feedback encontrado com os filtros atuais.</td></tr>';
    return;
  }
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td data-label="Data">${escapeHtml(formatDate(row.created_at))}</td>
      <td data-label="Tipo / Hotzone">
        <div class="feedback-meta">
          <strong>${escapeHtml(formatFeedbackTypeLabel(row.tipo))}</strong>
          <span>${escapeHtml(row.hotzone || "-")}</span>
        </div>
      </td>
      <td data-label="Nome">
        <div class="feedback-meta">
          <strong>${escapeHtml(row.nome_completo || "-")}</strong>
          <span>${escapeHtml(formatCPF(row.cpf || "-"))}</span>
        </div>
      </td>
      <td data-label="Contato">
        <div class="feedback-meta">
          <span>${escapeHtml(row.email || "-")}</span>
          <span>${escapeHtml(formatPhone(row.telefone || "-"))}</span>
        </div>
      </td>
      <td data-label="Satisfação">${escapeHtml(String(row.satisfacao ?? "-"))}</td>
      <td data-label="Anexo">${renderAttachmentCell(row)}</td>
      <td data-label="Mensagem"><div class="feedback-message">${escapeHtml(row.mensagem || "-")}</div></td>
    `;
    tabela.appendChild(tr);
  });
}

function renderChart(rows) {
  const canvas = document.getElementById("chart");
  if (!canvas || typeof Chart === "undefined") return;
  const counts = [0, 0, 0, 0, 0];
  rows.forEach((row) => {
    const index = Number(row.satisfacao || 0) - 1;
    if (index >= 0 && index < counts.length) counts[index] += 1;
  });
  const ctx = canvas.getContext("2d");
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["1", "2", "3", "4", "5"],
      datasets: [{
        label: "Satisfação",
        data: counts,
        backgroundColor: ["#ef4444", "#f97316", "#facc15", "#22c55e", "#15803d"],
        borderRadius: 10,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 } },
      },
    },
  });
}

async function loadData() {
  if (!tabela) return;
  renderHeader();
  tabela.innerHTML = '<tr><td colspan="7" class="table-empty">Carregando feedbacks...</td></tr>';
  const filters = getFilters();
  const query = new URLSearchParams({
    page: String(page),
    page_size: filters.page_size,
    sort: filters.sort,
  });
  Object.entries(filters).forEach(([key, value]) => {
    if (!value || key === "page_size" || key === "sort") return;
    query.set(key, value);
  });

  try {
    const response = await fetch(`/api/admin/feedbacks?${query.toString()}`);
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      tabela.innerHTML = `<tr><td colspan="7" class="table-empty">Erro: ${escapeHtml(payload.error || "desconhecido")}</td></tr>`;
      if (feedbackSummary) feedbackSummary.textContent = "Erro ao carregar feedbacks.";
      return;
    }
    const rows = payload.data || [];
    const total = Number(payload.total ?? rows.length);
    totalPages = Math.max(1, Math.ceil(total / Number(filters.page_size || 10)));
    if (pageInfo) pageInfo.textContent = `Página ${page} de ${totalPages}`;
    currentRows = rows;
    renderTable(rows);
    renderChart(rows);
    setFeedbackSummary(total);
  } catch (error) {
    tabela.innerHTML = '<tr><td colspan="7" class="table-empty">Erro de rede ao carregar feedbacks.</td></tr>';
    if (feedbackSummary) feedbackSummary.textContent = "Erro de rede.";
  }
}

function exportFeedbacksCsv() {
  const headers = ["Data", "Tipo", "Hotzone", "Nome", "CPF", "Telefone", "Email", "Satisfação", "Anexo", "Mensagem"];
  const lines = [headers.join(";")].concat(
    currentRows.map((row) => [
      formatDate(row.created_at).replace(/;/g, ","),
      String(row.tipo || "").replace(/;/g, ","),
      String(row.hotzone || "").replace(/;/g, ","),
      String(row.nome_completo || "").replace(/;/g, ","),
      String(row.cpf || "").replace(/;/g, ","),
      String(row.telefone || "").replace(/;/g, ","),
      String(row.email || "").replace(/;/g, ","),
      String(row.satisfacao || "").replace(/;/g, ","),
      String(row.anexo_url || row.anexo_nome || "").replace(/;/g, ","),
      String(row.mensagem || "").replace(/\n/g, " ").replace(/;/g, ","),
    ].join(";"))
  );
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const anchor = document.createElement("a");
  anchor.href = URL.createObjectURL(blob);
  anchor.download = "feedbacks.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

function setAdminFormMode(isEditing) {
  if (saveAdminBtn) saveAdminBtn.textContent = isEditing ? "Atualizar Login" : "Salvar Login";
  if (cancelAdminEditBtn) cancelAdminEditBtn.style.display = isEditing ? "inline-flex" : "none";
  if (adminUserPassword) adminUserPassword.required = !isEditing;
}

function resetAdminForm() {
  editingAdminEmail = "";
  if (adminUserForm) adminUserForm.reset();
  if (adminUserStatus) {
    adminUserStatus.textContent = "";
    adminUserStatus.style.color = "#8ec9ff";
  }
  setAdminFormMode(false);
}

function startEditAdminUser(email) {
  const user = adminUsers.find((item) => (item.email || "").toLowerCase() === String(email || "").toLowerCase());
  if (!user) return;
  editingAdminEmail = (user.email || "").toLowerCase();
  if (adminUserEmail) adminUserEmail.value = user.email || "";
  if (adminUserHierarchy) adminUserHierarchy.value = user.hierarchy || "admin";
  if (adminUserPassword) adminUserPassword.value = "";
  if (adminUserStatus) {
    adminUserStatus.textContent = `Editando ${user.email}`;
    adminUserStatus.style.color = "#93c5fd";
  }
  setAdminFormMode(true);
  adminUserEmail?.focus();
}

function renderAdminUsers(rows) {
  if (!adminUsersTable || !adminUsersEmpty) return;
  adminUsersTable.innerHTML = "";
  adminUsers = rows || [];
  if (!adminUsers.length) {
    adminUsersEmpty.textContent = "Nenhum login cadastrado.";
    adminUsersEmpty.style.display = "block";
    return;
  }
  adminUsersEmpty.style.display = "none";
  adminUsers.forEach((user) => {
    const tr = document.createElement("tr");
    const activeClass = user.active ? "active" : "inactive";
    const activeLabel = user.active ? "Ativo" : "Inativo";
    tr.innerHTML = `
      <td data-label="Email">${escapeHtml(user.email || "-")}</td>
      <td data-label="Hierarquia">${escapeHtml(user.hierarchy || "-")}</td>
      <td data-label="Status"><span class="status-badge ${activeClass}">${activeLabel}</span></td>
      <td data-label="Criado em">${escapeHtml(formatDate(user.created_at))}</td>
      <td data-label="Ações">
        <div class="user-actions">
          <button type="button" class="muted-btn" data-action="edit" data-email="${escapeHtml(user.email || "")}">Editar</button>
          <button type="button" class="secondary" data-action="toggle" data-email="${escapeHtml(user.email || "")}" data-active="${user.active ? "1" : "0"}">${user.active ? "Desativar" : "Ativar"}</button>
          <button type="button" class="danger-btn" data-action="delete" data-email="${escapeHtml(user.email || "")}">Excluir</button>
        </div>
      </td>
    `;
    adminUsersTable.appendChild(tr);
  });
}

async function loadAdminUsers() {
  if (!adminUsersTable || !adminUsersEmpty) return;
  adminUsersEmpty.textContent = "Carregando logins...";
  adminUsersEmpty.style.display = "block";
  try {
    const response = await fetch("/api/admin/users");
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      adminUsersEmpty.textContent = payload.error || "Erro ao carregar logins.";
      return;
    }
    renderAdminUsers(payload.data || []);
  } catch (error) {
    adminUsersEmpty.textContent = "Erro de rede ao carregar logins.";
  }
}

async function handleAdminUserSubmit(event) {
  event.preventDefault();
  if (!adminUserForm || !adminUserStatus) return;
  const email = (adminUserEmail?.value || "").trim().toLowerCase();
  const password = adminUserPassword?.value || "";
  const hierarquia = (adminUserHierarchy?.value || "").trim();
  const isEditing = Boolean(editingAdminEmail);
  if (!email || !hierarquia || (!isEditing && !password)) {
    adminUserStatus.textContent = isEditing ? "Preencha email e hierarquia." : "Preencha email, senha e hierarquia.";
    adminUserStatus.style.color = "#fca5a5";
    return;
  }

  adminUserStatus.textContent = isEditing ? "Atualizando login..." : "Salvando login...";
  adminUserStatus.style.color = "#93c5fd";
  try {
    const response = await fetch("/api/admin/users", {
      method: isEditing ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        isEditing
          ? { original_email: editingAdminEmail, email, password, hierarquia }
          : { email, password, hierarquia }
      ),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      adminUserStatus.textContent = payload.error || "Erro ao salvar login.";
      adminUserStatus.style.color = "#fca5a5";
      return;
    }
    resetAdminForm();
    adminUserStatus.textContent = payload.message || "Login salvo com sucesso.";
    adminUserStatus.style.color = "#86efac";
    await loadAdminUsers();
  } catch (error) {
    adminUserStatus.textContent = "Erro de rede ao salvar login.";
    adminUserStatus.style.color = "#fca5a5";
  }
}

async function toggleAdminUser(email, currentActive) {
  if (!adminUserStatus) return;
  adminUserStatus.textContent = currentActive ? "Desativando login..." : "Ativando login...";
  adminUserStatus.style.color = "#93c5fd";
  try {
    const response = await fetch("/api/admin/users/status", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, active: !currentActive }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      adminUserStatus.textContent = payload.error || "Erro ao atualizar status.";
      adminUserStatus.style.color = "#fca5a5";
      return;
    }
    adminUserStatus.textContent = payload.message || "Status atualizado com sucesso.";
    adminUserStatus.style.color = "#86efac";
    await loadAdminUsers();
  } catch (error) {
    adminUserStatus.textContent = "Erro de rede ao atualizar status.";
    adminUserStatus.style.color = "#fca5a5";
  }
}

async function deleteAdminUser(email) {
  if (!adminUserStatus) return;
  adminUserStatus.textContent = "Excluindo login...";
  adminUserStatus.style.color = "#93c5fd";
  try {
    const response = await fetch("/api/admin/users", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      adminUserStatus.textContent = payload.error || "Erro ao excluir login.";
      adminUserStatus.style.color = "#fca5a5";
      return;
    }
    if (editingAdminEmail === String(email || "").toLowerCase()) resetAdminForm();
    adminUserStatus.textContent = payload.message || "Login excluído com sucesso.";
    adminUserStatus.style.color = "#86efac";
    await loadAdminUsers();
  } catch (error) {
    adminUserStatus.textContent = "Erro de rede ao excluir login.";
    adminUserStatus.style.color = "#fca5a5";
  }
}

if (aplicarFiltro) {
  aplicarFiltro.addEventListener("click", () => {
    page = 1;
    loadData();
  });
}

if (limparFiltro) {
  limparFiltro.addEventListener("click", () => {
    [filtroHotzone, filtroTipo, filtroBusca, filtroAnexo, filtroSatisfacaoMin, filtroSatisfacaoMax, filtroDataInicial, filtroDataFinal, filtroOrdenacao].forEach((input) => {
      if (!input) return;
      input.value = input === filtroOrdenacao ? "created_at.desc" : "";
    });
    if (pageSizeSel) pageSizeSel.value = "10";
    page = 1;
    loadData();
  });
}

if (filtroBusca) {
  filtroBusca.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      page = 1;
      loadData();
    }
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
  exportBtn.addEventListener("click", exportFeedbacksCsv);
}

if (adminUserForm) {
  adminUserForm.addEventListener("submit", handleAdminUserSubmit);
}

if (cancelAdminEditBtn) {
  cancelAdminEditBtn.addEventListener("click", resetAdminForm);
}

if (adminUsersTable) {
  adminUsersTable.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const action = button.getAttribute("data-action");
    const email = button.getAttribute("data-email") || "";
    if (action === "edit") {
      startEditAdminUser(email);
      return;
    }
    if (action === "toggle") {
      await toggleAdminUser(email, button.getAttribute("data-active") === "1");
      return;
    }
    if (action === "delete") {
      if (!window.confirm(`Excluir o login ${email}?`)) return;
      await deleteAdminUser(email);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  renderHeader();
  setAdminFormMode(false);
  loadData();
  loadAdminUsers();
});
