const elements = {
  banner: document.getElementById('status-banner'),
  title: document.getElementById('status-title'),
  description: document.getElementById('status-description'),
  checked: document.getElementById('checked-at'),
  service: document.getElementById('service-value'),
  documents: document.getElementById('documents-value'),
  training: document.getElementById('training-value'),
  database: document.getElementById('database-value'),
  automation: document.getElementById('automation-value'),
};

async function refreshStatus() {
  try {
    const response = await fetch('/api/health', { cache: 'no-store' });
    const health = await response.json();
    const healthy = response.ok && health.status === 'ok';
    elements.banner.classList.toggle('is-degraded', !healthy);
    elements.title.textContent = healthy ? 'All systems operational' : 'Service needs attention';
    elements.description.textContent = healthy
      ? 'The support workspace and decision log are responding normally.'
      : 'One or more service checks are unavailable. Please try again shortly.';
    elements.service.textContent = healthy ? 'Operational' : 'Degraded';
    elements.documents.textContent = Number.isInteger(health.documents) ? health.documents.toLocaleString() : '—';
    elements.training.textContent = Number.isInteger(health.training_examples) ? health.training_examples.toLocaleString() : '—';
    elements.database.textContent = health.database === 'ok' ? 'Connected' : 'Unavailable';
    elements.automation.textContent = health.automation_enabled === true
      ? 'Automatic responses enabled'
      : health.automation_enabled === false ? 'Automatic responses disabled' : 'Automation setting unavailable';
  } catch {
    elements.banner.classList.add('is-degraded');
    elements.title.textContent = 'Unable to reach service';
    elements.description.textContent = 'The health check did not respond. Please try again shortly.';
    elements.service.textContent = 'Unavailable';
    elements.documents.textContent = '—';
    elements.training.textContent = '—';
    elements.database.textContent = 'Unavailable';
    elements.automation.textContent = 'Automation setting unavailable';
  }
  elements.checked.textContent = `Last checked ${new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date())}`;
}

refreshStatus();
setInterval(refreshStatus, 30_000);
