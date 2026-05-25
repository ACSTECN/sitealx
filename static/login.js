const form=document.getElementById("login-form");
const statusEl=document.getElementById("login-status");
async function handleLogin(e){
  e.preventDefault();
  const email=document.getElementById("login-email").value.trim().toLowerCase();
  const password=document.getElementById("login-senha").value;
  if(!email||!password){statusEl.textContent="Informe email e senha.";statusEl.style.color="#b91c1c";return}
  try{
    const r=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});
    const j=await r.json();
    if(!r.ok||!j.ok){statusEl.textContent=j.error||"Erro ao autenticar.";statusEl.style.color="#b91c1c";return}
    window.location.href="/admin";
  }catch(err){
    statusEl.textContent="Erro de rede.";
    statusEl.style.color="#b91c1c";
  }
}
if(form){form.addEventListener("submit",handleLogin)}
