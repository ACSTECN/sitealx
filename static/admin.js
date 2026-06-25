const tabela=document.getElementById("tabela");
const thead=document.getElementById("thead");
const filtroHotzone=document.getElementById("filtro-hotzone");
const aplicarFiltro=document.getElementById("aplicar-filtro");
const pageSizeSel=document.getElementById("page-size");
const prevBtn=document.getElementById("prev-page");
const nextBtn=document.getElementById("next-page");
const pageInfo=document.getElementById("page-info");
const exportBtn=document.getElementById("exportar-csv");
const adminUserForm=document.getElementById("admin-user-form");
const adminUserStatus=document.getElementById("admin-user-status");
const adminUserEmail=document.getElementById("novo-admin-email");
const adminUserPassword=document.getElementById("novo-admin-senha");
const adminUserHierarchy=document.getElementById("novo-admin-hierarquia");
const adminUsersTable=document.getElementById("admin-users-table");
const adminUsersEmpty=document.getElementById("admin-users-empty");
const cancelAdminEditBtn=document.getElementById("cancelar-admin-edit");
const saveAdminBtn=document.getElementById("criar-admin-btn");
let chart;
let page=1;let totalPages=1;
let currentRows=[];
let adminUsers=[];
let editingAdminEmail="";

function escapeHtml(value){
  return String(value??"")
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;")
    .replace(/'/g,"&#39;");
}

function formatDate(value){
  if(!value)return "-";
  const d=new Date(value);
  if(Number.isNaN(d.getTime()))return value;
  return d.toLocaleString("pt-BR");
}

function setAdminFormMode(isEditing){
  if(saveAdminBtn){saveAdminBtn.textContent=isEditing?"Atualizar Login":"Salvar Login"}
  if(cancelAdminEditBtn){cancelAdminEditBtn.style.display=isEditing?"inline-flex":"none"}
  if(adminUserPassword){adminUserPassword.required=!isEditing}
}

function resetAdminForm(){
  editingAdminEmail="";
  if(adminUserForm)adminUserForm.reset();
  if(adminUserStatus){
    adminUserStatus.textContent="";
    adminUserStatus.style.color="#8ec9ff";
  }
  setAdminFormMode(false);
}

function startEditAdminUser(email){
  const user=adminUsers.find(u=>(u.email||"").toLowerCase()===String(email||"").toLowerCase());
  if(!user)return;
  editingAdminEmail=(user.email||"").toLowerCase();
  if(adminUserEmail)adminUserEmail.value=user.email||"";
  if(adminUserHierarchy)adminUserHierarchy.value=user.hierarchy||"";
  if(adminUserPassword)adminUserPassword.value="";
  if(adminUserStatus){
    adminUserStatus.textContent=`Editando ${user.email}`;
    adminUserStatus.style.color="#93c5fd";
  }
  setAdminFormMode(true);
  adminUserEmail?.focus();
}

function renderAdminUsers(rows){
  if(!adminUsersTable||!adminUsersEmpty)return;
  adminUsersTable.innerHTML="";
  adminUsers=rows||[];
  if(!adminUsers.length){
    adminUsersEmpty.textContent="Nenhum login cadastrado.";
    adminUsersEmpty.style.display="block";
    return;
  }
  adminUsersEmpty.style.display="none";
  adminUsers.forEach(user=>{
    const tr=document.createElement("tr");
    const activeClass=user.active?"active":"inactive";
    const activeLabel=user.active?"Ativo":"Inativo";
    tr.innerHTML=`
      <td>${escapeHtml(user.email||"-")}</td>
      <td>${escapeHtml(user.hierarchy||"-")}</td>
      <td><span class="status-badge ${activeClass}">${activeLabel}</span></td>
      <td>${escapeHtml(formatDate(user.created_at))}</td>
      <td>
        <div class="user-actions">
          <button type="button" class="muted-btn" data-action="edit" data-email="${escapeHtml(user.email||"")}">Editar</button>
          <button type="button" class="secondary" data-action="toggle" data-email="${escapeHtml(user.email||"")}" data-active="${user.active?"1":"0"}">${user.active?"Desativar":"Ativar"}</button>
          <button type="button" class="danger-btn" data-action="delete" data-email="${escapeHtml(user.email||"")}">Excluir</button>
        </div>
      </td>
    `;
    adminUsersTable.appendChild(tr);
  });
}

async function loadAdminUsers(){
  if(!adminUsersTable||!adminUsersEmpty)return;
  adminUsersEmpty.textContent="Carregando logins...";
  adminUsersEmpty.style.display="block";
  try{
    const r=await fetch("/api/admin/users");
    const j=await r.json();
    if(!r.ok||!j.ok){
      adminUsersEmpty.textContent=j.error||"Erro ao carregar logins.";
      return;
    }
    renderAdminUsers(j.data||[]);
  }catch(err){
    adminUsersEmpty.textContent="Erro de rede ao carregar logins.";
  }
}
async function loadData(){
  tabela.innerHTML="<tr><td>Carregando...</td></tr>";
  const filtro=filtroHotzone.value.trim();
  const pageSize=parseInt(pageSizeSel.value||"10",10);
  const url=`/api/admin/feedbacks?hotzone=${encodeURIComponent(filtro)}&page=${page}&page_size=${pageSize}`;
  let dataResp;
  try{
    const r=await fetch(url);
    dataResp=await r.json();
  }catch(e){
    tabela.innerHTML="<tr><td>Erro de rede</td></tr>";
    return;
  }
  if(!dataResp.ok){tabela.innerHTML=`<tr><td>Erro: ${dataResp.error||"desconhecido"}</td></tr>`;return}
  const rows=dataResp.data||[];
  const total=dataResp.total||rows.length;
  totalPages=Math.max(1,Math.ceil(total/pageSize));
  pageInfo.textContent=`Página ${page} de ${totalPages}`;
  currentRows=rows;
  renderHeader();
  renderTable(currentRows);
  renderChart(rows);
}
function renderHeader(){
  if(!thead)return;
  thead.innerHTML="";
  const tr=document.createElement("tr");
  ["Data","Nome","CPF","Hotzone","Telefone","Email","Tipo","Satisfação","Mensagem"].forEach(h=>{
    const th=document.createElement("th");
    th.textContent=h;
    th.style.textAlign="left";
    th.style.padding="8px";
    tr.appendChild(th);
  });
  thead.appendChild(tr);
}
function renderTable(rows){
  tabela.innerHTML="";
  if(!rows.length){tabela.innerHTML="<tr><td>Nenhum dado encontrado</td></tr>";return}
  rows.forEach(r=>{
    const tr=document.createElement("tr");
    const cells=[new Date(r.created_at).toLocaleString(),r.nome_completo,r.cpf,r.hotzone,r.telefone,r.email,r.tipo,r.satisfacao,r.mensagem];
    cells.forEach(c=>{
      const td=document.createElement("td");
      td.textContent=c;
      td.style.padding="8px";
      td.style.borderBottom="1px solid #e5e7eb";
      tr.appendChild(td);
    });
    tabela.appendChild(tr);
  });
}
function renderChart(rows){
  const counts=[0,0,0,0,0,0,0,0,0,0];
  rows.forEach(r=>{const i=(r.satisfacao||0)-1;if(i>=0&&i<10)counts[i]++});
  const canvas=document.getElementById("chart");
  if(!canvas)return;
  const ctx=canvas.getContext("2d");
  if(chart)chart.destroy();
  chart=new Chart(ctx,{type:"bar",data:{labels:["1","2","3","4","5","6","7","8","9","10"],datasets:[{label:"Satisfação",data:counts,backgroundColor:["#ef4444","#f97316","#f59e0b","#fcd34d","#fde047","#a3e635","#34d399","#22c55e","#16a34a","#15803d"]}]} ,options:{responsive:true,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{stepSize:1}}}}});
}
if(aplicarFiltro){aplicarFiltro.addEventListener("click",()=>{page=1;loadData()})}
if(prevBtn){prevBtn.addEventListener("click",()=>{page=Math.max(1,page-1);loadData()})}
if(nextBtn){nextBtn.addEventListener("click",()=>{page=Math.min(totalPages,page+1);loadData()})}
if(pageSizeSel){pageSizeSel.addEventListener("change",()=>{page=1;loadData()})}
if(exportBtn){exportBtn.addEventListener("click",()=>{
  const headers=["Data","Nome","CPF","Hotzone","Telefone","Email","Tipo","Satisfação","Mensagem"];
  const lines=[headers.join(";")].concat(currentRows.map(r=>[
    new Date(r.created_at).toLocaleString().replace(/;/g,","),
    (r.nome_completo||"").replace(/;/g,","),
    r.cpf||"",
    r.hotzone||"",
    r.telefone||"",
    r.email||"",
    r.tipo||"",
    r.satisfacao||"",
    (r.mensagem||"").replace(/\\n/g," ").replace(/;/g,",")
  ].join(";")));
  const blob=new Blob([lines.join("\\n")],{type:"text/csv;charset=utf-8;"});
  const a=document.createElement("a");
  a.href=URL.createObjectURL(blob);
  a.download="feedbacks.csv";
  document.body.appendChild(a);a.click();a.remove();
})}
async function handleAdminUserSubmit(e){
  e.preventDefault();
  if(!adminUserForm||!adminUserStatus)return;
  const email=(adminUserEmail?.value||"").trim().toLowerCase();
  const password=adminUserPassword?.value||"";
  const hierarquia=(adminUserHierarchy?.value||"").trim();
  const isEditing=Boolean(editingAdminEmail);
  if(!email||!hierarquia||(!isEditing&&!password)){
    adminUserStatus.textContent=isEditing?"Preencha email e hierarquia.":"Preencha email, senha e hierarquia.";
    adminUserStatus.style.color="#fca5a5";
    return;
  }
  adminUserStatus.textContent=isEditing?"Atualizando login...":"Salvando login...";
  adminUserStatus.style.color="#93c5fd";
  try{
    const r=await fetch("/api/admin/users",{
      method:isEditing?"PUT":"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(isEditing?{original_email:editingAdminEmail,email,password,hierarquia}:{email,password,hierarquia})
    });
    const j=await r.json();
    if(!r.ok||!j.ok){
      adminUserStatus.textContent=j.error||"Erro ao salvar login.";
      adminUserStatus.style.color="#fca5a5";
      return;
    }
    adminUserStatus.textContent=j.message||"Login salvo com sucesso.";
    adminUserStatus.style.color="#86efac";
    resetAdminForm();
    adminUserStatus.textContent=j.message||"Login salvo com sucesso.";
    adminUserStatus.style.color="#86efac";
    await loadAdminUsers();
  }catch(err){
    adminUserStatus.textContent="Erro de rede ao salvar login.";
    adminUserStatus.style.color="#fca5a5";
  }
}

async function toggleAdminUser(email, currentActive){
  if(!adminUserStatus)return;
  adminUserStatus.textContent=currentActive?"Desativando login...":"Ativando login...";
  adminUserStatus.style.color="#93c5fd";
  try{
    const r=await fetch("/api/admin/users/status",{
      method:"PATCH",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({email,active:!currentActive})
    });
    const j=await r.json();
    if(!r.ok||!j.ok){
      adminUserStatus.textContent=j.error||"Erro ao atualizar status.";
      adminUserStatus.style.color="#fca5a5";
      return;
    }
    adminUserStatus.textContent=j.message||"Status atualizado com sucesso.";
    adminUserStatus.style.color="#86efac";
    await loadAdminUsers();
  }catch(err){
    adminUserStatus.textContent="Erro de rede ao atualizar status.";
    adminUserStatus.style.color="#fca5a5";
  }
}

async function deleteAdminUser(email){
  if(!adminUserStatus)return;
  adminUserStatus.textContent="Excluindo login...";
  adminUserStatus.style.color="#93c5fd";
  try{
    const r=await fetch("/api/admin/users",{
      method:"DELETE",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({email})
    });
    const j=await r.json();
    if(!r.ok||!j.ok){
      adminUserStatus.textContent=j.error||"Erro ao excluir login.";
      adminUserStatus.style.color="#fca5a5";
      return;
    }
    if(editingAdminEmail===String(email||"").toLowerCase())resetAdminForm();
    adminUserStatus.textContent=j.message||"Login excluído com sucesso.";
    adminUserStatus.style.color="#86efac";
    await loadAdminUsers();
  }catch(err){
    adminUserStatus.textContent="Erro de rede ao excluir login.";
    adminUserStatus.style.color="#fca5a5";
  }
}

if(adminUserForm){adminUserForm.addEventListener("submit",handleAdminUserSubmit)}
if(cancelAdminEditBtn){cancelAdminEditBtn.addEventListener("click",resetAdminForm)}
if(adminUsersTable){
  adminUsersTable.addEventListener("click",async e=>{
    const btn=e.target.closest("button[data-action]");
    if(!btn)return;
    const action=btn.getAttribute("data-action");
    const email=btn.getAttribute("data-email")||"";
    if(action==="edit"){
      startEditAdminUser(email);
      return;
    }
    if(action==="toggle"){
      await toggleAdminUser(email,btn.getAttribute("data-active")==="1");
      return;
    }
    if(action==="delete"){
      if(!window.confirm(`Excluir o login ${email}?`))return;
      await deleteAdminUser(email);
    }
  });
}
document.addEventListener("DOMContentLoaded",()=>{loadData();loadAdminUsers();setAdminFormMode(false);});
document.addEventListener("DOMContentLoaded", function () {

    const slides = document.querySelectorAll(".slide");
    let index = 0;

    setInterval(() => {
        slides[index].classList.remove("active");

        index = (index + 1) % slides.length;

        slides[index].classList.add("active");
    }, 3000);

});
