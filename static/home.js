function initHeroSlider(){
  const root=document.querySelector(".hero-slider");
  if(!root)return;
  const slides=[...root.querySelectorAll(".hero-slide")];
  const dots=[...root.querySelectorAll(".hero-dot")];
  if(!slides.length)return;
  let index=Math.max(0,slides.findIndex(s=>s.classList.contains("is-active")));
  if(index<0)index=0;
  function apply(i){
    slides.forEach((s,si)=>s.classList.toggle("is-active",si===i));
    dots.forEach((d,di)=>d.classList.toggle("is-active",di===i));
    index=i;
  }
  dots.forEach((d,di)=>d.addEventListener("click",()=>apply(di)));
  let timer=null;
  function start(){
    stop();
    timer=setInterval(()=>apply((index+1)%slides.length),6500);
  }
  function stop(){
    if(timer){clearInterval(timer);timer=null}
  }
  root.addEventListener("mouseenter",stop);
  root.addEventListener("mouseleave",start);
  apply(index);
  start();
}
function initShowcaseCounter(){
  const badge=document.querySelector(".showcase-badge[data-count-to]");
  if(!badge)return;
  const countEl=badge.querySelector(".showcase-count");
  if(!countEl)return;
  const to=parseInt(badge.getAttribute("data-count-to")||"0",10);
  if(!Number.isFinite(to)||to<=0)return;
  let started=false;
  function run(){
    if(started)return;
    started=true;
    let n=0;
    countEl.textContent=String(n);
    const t=setInterval(()=>{
      n+=1;
      countEl.textContent=String(n);
      if(n>=to)clearInterval(t);
    },110);
  }
  if("IntersectionObserver" in window){
    const obs=new IntersectionObserver((entries)=>{
      if(entries.some(e=>e.isIntersecting)){
        obs.disconnect();
        run();
      }
    },{threshold:.4});
    obs.observe(badge);
  }else{
    run();
  }
}
document.addEventListener("DOMContentLoaded",()=>{initHeroSlider();initShowcaseCounter();});
