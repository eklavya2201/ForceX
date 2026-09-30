(()=>{const c=document.querySelector('#countdown');if(!c)return;let left=Number(c.dataset.seconds);const draw=()=>{c.textContent=`${Math.floor(left/60)}:${String(left%60).padStart(2,'0')}`;if(left--<=0)location.reload()};draw();setInterval(draw,1000);const t=document.querySelector('#watermark-time');const update=()=>{if(t)t.textContent=new Date().toLocaleString()};update();setInterval(update,20000);document.addEventListener('contextmenu',e=>e.preventDefault())})();
// Deterrents only: a web page cannot stop OS-level screenshots. The desktop client blocks capture for real.
(()=>{const v=document.querySelector('.viewer');if(!v)return;const shield=on=>v.classList.toggle('shielded',on);
// Focus moving into the PDF/text iframe blurs the window too, so only shield when focus left the page entirely.
window.addEventListener('blur',()=>setTimeout(()=>{if(document.activeElement?.tagName!=='IFRAME')shield(true)},0));window.addEventListener('focus',()=>shield(false));document.addEventListener('visibilitychange',()=>shield(document.hidden));
document.addEventListener('keydown',e=>{const k=e.key.toLowerCase();if((e.ctrlKey||e.metaKey)&&(k==='p'||k==='s')){e.preventDefault();e.stopImmediatePropagation()}},true);
document.addEventListener('keyup',e=>{if(e.key==='PrintScreen'){shield(true);navigator.clipboard?.writeText('').catch(()=>{})}});
window.addEventListener('beforeprint',()=>shield(true));window.addEventListener('dragstart',e=>e.preventDefault())})();
