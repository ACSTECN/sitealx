const yearEl=document.getElementById("year");if(yearEl){yearEl.textContent=new Date().getFullYear();}
let currentSlide=0;const slides=[...document.querySelectorAll(".slide")];const prevBtn=document.getElementById("prev");const nextBtn=document.getElementById("next");function showSlide(i){slides.forEach(s=>s.classList.remove("active"));slides[i].classList.add("active")}function next(){currentSlide=(currentSlide+1)%slides.length;showSlide(currentSlide)}function prev(){currentSlide=(currentSlide-1+slides.length)%slides.length;showSlide(currentSlide)}if(prevBtn&&nextBtn){prevBtn.addEventListener("click",prev);nextBtn.addEventListener("click",next);setInterval(next,6000)}
const statusEl=document.getElementById("form-status");function setStatus(t,c){if(!statusEl)return;statusEl.textContent=t;statusEl.style.color=c||"#111";}
document.addEventListener("DOMContentLoaded",()=>{const p=new URLSearchParams(location.search);if(p.get("sent")==="1"){setStatus("Sugestão enviada com sucesso!","#16a34a")}})
function onlyDigits(v){return v.replace(/\D/g,"")}
function formatCPF(v){const d=onlyDigits(v).slice(0,11);const p=[d.slice(0,3),d.slice(3,6),d.slice(6,9),d.slice(9,11)];let out="";if(p[0])out+=p[0];if(p[1])out+="."+p[1];if(p[2])out+="."+p[2];if(p[3])out+="-"+p[3];return out}
function formatPhone(v){const d=onlyDigits(v).slice(0,11);const p=[d.slice(0,2),d.slice(2,7),d.slice(7,11)];let out="";if(p[0])out+="("+p[0]+") ";if(p[1])out+=p[1];if(p[2])out+="-"+p[2];return out}
const cpfEl=document.getElementById("cpf");const telEl=document.getElementById("telefone");if(cpfEl)cpfEl.addEventListener("input",e=>{e.target.value=formatCPF(e.target.value)});if(telEl)telEl.addEventListener("input",e=>{e.target.value=formatPhone(e.target.value)})
const qs=new URLSearchParams(location.search);const qSatis=qs.get("satisfacao");if(qSatis){const el=document.querySelector(`input[name="satisfacao"][value="${qSatis}"]`);if(el){el.checked=true}}
const form=document.getElementById("feedback-form");if(form){form.setAttribute("novalidate","");form.addEventListener("submit",async e=>{e.preventDefault();const nome=document.getElementById("nome").value.trim();const cpf=document.getElementById("cpf").value.trim();const hotzone=document.getElementById("hotzone").value.trim();const telefone=document.getElementById("telefone").value.trim();const email=document.getElementById("email").value.trim();const tipo=document.getElementById("tipo").value;const mensagem=document.getElementById("mensagem").value.trim();const satisfacao=parseInt((document.querySelector('input[name="satisfacao"]:checked')||{}).value||qs.get("satisfacao")||"10",10);if(!nome||!cpf||!hotzone||!telefone||!email||!mensagem){setStatus("Preencha todos os campos.","#b91c1c");return}const cpfDigits=onlyDigits(cpf);if(cpfDigits.length!==11){setStatus("CPF inválido.","#b91c1c");return}try{const r=await fetch("/api/feedback",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nome_completo:nome,cpf:cpfDigits,hotzone,telefone,email,tipo,mensagem,satisfacao})});const j=await r.json();if(!r.ok||!j.ok){setStatus("Erro ao enviar: "+(j.error||""),"#b91c1c");return}form.reset();setStatus("Sugestão enviada com sucesso!","#16a34a")}catch(err){setStatus("Erro de rede.","#b91c1c")}})}
document.addEventListener("DOMContentLoaded", function () {

    const slides = document.querySelectorAll(".slide");
    let index = 0;

    setInterval(() => {
        slides[index].classList.remove("active");

        index = (index + 1) % slides.length;

        slides[index].classList.add("active");
    }, 3000);

});

const texto = "Mais que entregas, somos parceiros no seu crescimento.";
const elemento = document.getElementById("typing");

let i = 0;

function digitar() {
  if (i < texto.length) {
    elemento.innerHTML += texto.charAt(i);
    i++;
    setTimeout(digitar, 80);
  }
}

digitar();
