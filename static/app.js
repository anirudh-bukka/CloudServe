const $ = (id) => document.getElementById(id);
let samples = [];
let selected = null;
function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])); }
function showSamples() {
  const query = $('search').value.toLowerCase();
  const visible = samples.filter(s => (s.ticket_id + ' ' + s.subject + ' ' + s.channel).toLowerCase().includes(query));
  $('count').textContent = visible.length;
  $('samples').innerHTML = visible.map(s => `<button class="sample ${selected === s.ticket_id ? 'active' : ''}" data-id="${escapeHtml(s.ticket_id)}"><strong>${escapeHtml(s.subject)}</strong><small>${escapeHtml(s.ticket_id)} · ${escapeHtml(s.channel)}</small></button>`).join('');
  document.querySelectorAll('.sample').forEach(button => button.addEventListener('click', () => loadSample(button.dataset.id)));
}
async function loadSample(id) {
  selected = id; showSamples();
  const response = await fetch('/api/samples/' + encodeURIComponent(id));
  const ticket = await response.json();
  $('subject').value = ticket.subject || '';
  $('body').value = ticket.body || '';
  $('channel').value = ticket.channel || 'email';
  $('tier').value = ticket.customer_tier || 'standard';
  $('result').className = 'result empty';
  $('result').innerHTML = '<span class="empty-icon">✳</span><h3>Ready to analyze</h3><p>Review this ticket, then select Analyze ticket.</p>';
  history.replaceState(null, '', '?ticket=' + encodeURIComponent(id) + '#workspace');
}
function renderDecision(d) {
  const isAuto = d.route === 'auto_respond';
  const sources = d.sources.map(s => `<details class="source"><summary>${escapeHtml(s.title)} · ${escapeHtml(s.passage_id)} · ${Math.round(s.score*100)}% match</summary><p>${escapeHtml(s.text)}</p></details>`).join('');
  $('result').className = 'result';
  $('result').innerHTML = `<span class="status ${isAuto ? 'auto' : 'escalate'}">${isAuto ? '● DRAFT FOR REVIEW' : '● HUMAN REVIEW'}</span><h3>${isAuto ? 'Guidance found' : 'Specialist review recommended'}</h3><p>${escapeHtml(d.reason)}</p><div class="result-grid"><div class="metric"><small>INTENT</small><strong>${escapeHtml(d.classification.intent.replaceAll('_',' '))}</strong></div><div class="metric"><small>URGENCY</small><strong>${escapeHtml(d.classification.urgency)}</strong></div><div class="metric"><small>CONFIDENCE</small><strong>${Math.round(d.classification.confidence*100)}%</strong></div></div>${d.answer ? `<div class="answer">${escapeHtml(d.answer)}</div>` : `<div class="answer">${escapeHtml(d.summary)}</div>`}<div class="guard">Safety checks: injection ${d.guardrails.prompt_injection ? 'flagged' : 'clear'} · private data ${d.guardrails.private_data ? 'flagged' : 'clear'} · ${d.sources.length} source passages found</div><div class="sources"><h4>Retrieved evidence</h4>${sources || '<p>No relevant passage met the threshold.</p>'}</div>`;
}
$('ticket-form').addEventListener('submit', async e => {
  e.preventDefault(); const button = $('run'); button.disabled = true; button.textContent = 'Analyzing…';
  try {
    const response = await fetch('/api/triage', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ticket_id:selected || 'NEW-' + Date.now(), channel:$('channel').value, customer_tier:$('tier').value, subject:$('subject').value, body:$('body').value})});
    const result = await response.json(); if (!response.ok) throw new Error(result.error || 'Request failed'); renderDecision(result);
  } catch(err) { $('result').className='result'; $('result').innerHTML='<h3>Could not analyze this ticket</h3><p>'+escapeHtml(err.message)+'</p>'; }
  finally { button.disabled=false; button.innerHTML='Analyze ticket <span>↗</span>'; }
});
$('search').addEventListener('input', showSamples);
fetch('/api/samples').then(r => r.json()).then(data => { samples=data; showSamples(); const id=new URLSearchParams(location.search).get('ticket'); if (id && samples.some(s=>s.ticket_id===id)) loadSample(id); }).catch(() => {$('samples').textContent='Samples unavailable';});
