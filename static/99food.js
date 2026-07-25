function initMediaCarousel(name) {
  const root = document.querySelector(`[data-carousel="${name}"]`);
  if (!root) return;

  const track = root.querySelector(".media-carousel-track");
  const slides = [...root.querySelectorAll(".media-slide")];
  const dotsRoot = document.querySelector(`[data-carousel-dots="${name}"]`);
  const prevBtn = document.querySelector(`[data-carousel-prev="${name}"]`);
  const nextBtn = document.querySelector(`[data-carousel-next="${name}"]`);
  if (!track || !slides.length) return;

  let index = 0;
  let timer = null;

  function renderDots() {
    if (!dotsRoot) return;
    dotsRoot.innerHTML = slides
      .map((_, slideIndex) => {
        const active = slideIndex === index ? " is-active" : "";
        return `<button class="media-carousel-dot${active}" type="button" data-index="${slideIndex}" aria-label="Ir para slide ${slideIndex + 1}"></button>`;
      })
      .join("");

    dotsRoot.querySelectorAll(".media-carousel-dot").forEach((button) => {
      button.addEventListener("click", () => {
        goTo(Number(button.getAttribute("data-index") || "0"));
      });
    });
  }

  function update() {
    track.style.transform = `translateX(-${index * 100}%)`;
    renderDots();
  }

  function goTo(nextIndex) {
    index = (nextIndex + slides.length) % slides.length;
    update();
  }

  function start() {
    stop();
    timer = window.setInterval(() => {
      goTo(index + 1);
    }, 4800);
  }

  function stop() {
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  prevBtn?.addEventListener("click", () => goTo(index - 1));
  nextBtn?.addEventListener("click", () => goTo(index + 1));

  root.addEventListener("mouseenter", stop);
  root.addEventListener("mouseleave", start);
  root.addEventListener("focusin", stop);
  root.addEventListener("focusout", start);

  update();
  start();
}

document.addEventListener("DOMContentLoaded", () => {
  initMediaCarousel("premiacoes");
  initMediaCarousel("informativos");
});
