const yearEl = document.getElementById("year");
if (yearEl) {
  yearEl.textContent = new Date().getFullYear();
}

const slides = [...document.querySelectorAll(".slide")];
const prevBtn = document.getElementById("prev");
const nextBtn = document.getElementById("next");
let currentSlide = 0;

function showSlide(index) {
  slides.forEach((slide) => slide.classList.remove("active"));
  if (slides[index]) {
    slides[index].classList.add("active");
  }
}

function nextSlide() {
  if (!slides.length) return;
  currentSlide = (currentSlide + 1) % slides.length;
  showSlide(currentSlide);
}

function prevSlide() {
  if (!slides.length) return;
  currentSlide = (currentSlide - 1 + slides.length) % slides.length;
  showSlide(currentSlide);
}

if (prevBtn && nextBtn && slides.length) {
  prevBtn.addEventListener("click", prevSlide);
  nextBtn.addEventListener("click", nextSlide);
  setInterval(nextSlide, 6000);
}

const statusEl = document.getElementById("form-status");
function setStatus(text, color) {
  if (!statusEl) return;
  statusEl.textContent = text;
  statusEl.style.color = color || "#111";
}

function onlyDigits(value) {
  return String(value || "").replace(/\D/g, "");
}

function formatCPF(value) {
  const digits = onlyDigits(value).slice(0, 11);
  const parts = [digits.slice(0, 3), digits.slice(3, 6), digits.slice(6, 9), digits.slice(9, 11)];
  let output = "";
  if (parts[0]) output += parts[0];
  if (parts[1]) output += `.${parts[1]}`;
  if (parts[2]) output += `.${parts[2]}`;
  if (parts[3]) output += `-${parts[3]}`;
  return output;
}

function formatPhone(value) {
  const digits = onlyDigits(value).slice(0, 11);
  const parts = [digits.slice(0, 2), digits.slice(2, 7), digits.slice(7, 11)];
  let output = "";
  if (parts[0]) output += `(${parts[0]}) `;
  if (parts[1]) output += parts[1];
  if (parts[2]) output += `-${parts[2]}`;
  return output;
}

const cpfEl = document.getElementById("cpf");
const telEl = document.getElementById("telefone");
const tipoEl = document.getElementById("tipo");
const anexoEl = document.getElementById("anexo");
const anexoWrapper = document.getElementById("anexo-wrapper");
const anexoStatusEl = document.getElementById("anexo-status");
const form = document.getElementById("feedback-form");
const qs = new URLSearchParams(location.search);

function syncAttachmentVisibility() {
  if (!tipoEl || !anexoWrapper || !anexoEl) return;
  if (anexoStatusEl) {
    anexoStatusEl.textContent = "Anexo liberado para qualquer tipo de envio.";
  }
}

if (cpfEl) {
  cpfEl.addEventListener("input", (event) => {
    event.target.value = formatCPF(event.target.value);
  });
}

if (telEl) {
  telEl.addEventListener("input", (event) => {
    event.target.value = formatPhone(event.target.value);
  });
}

if (tipoEl) {
  tipoEl.addEventListener("change", syncAttachmentVisibility);
}

const qSatis = qs.get("satisfacao");
if (qSatis) {
  const radio = document.querySelector(`input[name="satisfacao"][value="${qSatis}"]`);
  if (radio) radio.checked = true;
}

document.addEventListener("DOMContentLoaded", () => {
  if (qs.get("sent") === "1") {
    setStatus("Sugestão enviada com sucesso!", "#16a34a");
  }
  syncAttachmentVisibility();
});

if (form) {
  form.setAttribute("novalidate", "");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const nome = document.getElementById("nome").value.trim();
    const cpf = document.getElementById("cpf").value.trim();
    const hotzone = document.getElementById("hotzone").value.trim();
    const telefone = document.getElementById("telefone").value.trim();
    const email = document.getElementById("email").value.trim();
    const tipo = tipoEl ? tipoEl.value : "sugestao";
    const mensagem = document.getElementById("mensagem").value.trim();
    const satisfacao = parseInt(
      (document.querySelector('input[name="satisfacao"]:checked') || {}).value || qs.get("satisfacao") || "10",
      10
    );
    const cpfDigits = onlyDigits(cpf);
    const selectedFile = anexoEl?.files?.[0];

    if (!nome || !cpf || !hotzone || !telefone || !email || !mensagem) {
      setStatus("Preencha todos os campos.", "#b91c1c");
      return;
    }

    if (cpfDigits.length !== 11) {
      setStatus("CPF inválido.", "#b91c1c");
      return;
    }

    if (selectedFile && selectedFile.size > 10 * 1024 * 1024) {
      setStatus("O arquivo deve ter no máximo 10 MB.", "#b91c1c");
      return;
    }

    const formData = new FormData(form);
    formData.set("nome_completo", nome);
    formData.set("cpf", cpfDigits);
    formData.set("hotzone", hotzone);
    formData.set("telefone", telefone);
    formData.set("email", email);
    formData.set("tipo", tipo);
    formData.set("mensagem", mensagem);
    formData.set("satisfacao", String(Number.isNaN(satisfacao) ? 10 : satisfacao));

    try {
      setStatus("Enviando sua mensagem...", "#93c5fd");
      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setStatus(`Erro ao enviar: ${payload.error || ""}`, "#b91c1c");
        return;
      }
      form.reset();
      syncAttachmentVisibility();
      setStatus("Sugestão enviada com sucesso!", "#16a34a");
    } catch (error) {
      setStatus("Erro de rede.", "#b91c1c");
    }
  });
}

const texto = "Mais que entregas, somos parceiros no seu crescimento.";
const elemento = document.getElementById("typing");
let i = 0;

function digitar() {
  if (!elemento) return;
  if (i < texto.length) {
    elemento.innerHTML += texto.charAt(i);
    i += 1;
    setTimeout(digitar, 80);
  }
}

digitar();
