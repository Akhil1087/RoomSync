document.addEventListener('DOMContentLoaded', () => {
  const fab = document.getElementById('chatFab'), box = document.getElementById('chatBox'), close = document.getElementById('chatClose');
  if (fab && box) { fab.onclick = () => box.classList.toggle('open'); close.onclick = () => box.classList.remove('open'); }
  const form = document.getElementById('chatForm');
  if (form) form.addEventListener('submit', async e => {
    e.preventDefault(); const input = document.getElementById('chatInput'); const text = input.value.trim(); if (!text) return;
    addChat(text, 'me'); input.value = '';
    try { const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('meta[name="csrf-token"]')?.content || ''}, body:JSON.stringify({message:text})}); const data = await r.json(); addChat(data.reply, 'bot'); }
    catch { addChat('Sorry, the assistant is temporarily unavailable.', 'bot'); }
  });
  function addChat(text, who) { const m=document.getElementById('chatMessages'); const div=document.createElement('div'); div.className=who; div.textContent=text; m.appendChild(div); m.scrollTop=m.scrollHeight; }
  if (window.PG && document.getElementById('pgMap')) { const map=L.map('pgMap').setView([window.PG.lat,window.PG.lon],16); L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors'}).addTo(map); L.marker([window.PG.lat,window.PG.lon]).addTo(map).bindPopup(window.PG.name).openPopup(); }
});
