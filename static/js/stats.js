(() => {
  const data = JSON.parse(document.getElementById('stats-data').textContent);
  if (!window.Chart) return;

  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();
  const accent = color('--accent');
  const palette = [accent, '#6366f1', '#f59e0b', '#ec4899', '#0ea5e9', '#84cc16', '#a855f7', '#ef4444'];

  Chart.defaults.color = color('--muted');
  Chart.defaults.borderColor = color('--border');
  Chart.defaults.font.family = css.fontFamily;
  Chart.defaults.maintainAspectRatio = false;
  // Уважаем системную настройку «уменьшить движение».
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) Chart.defaults.animation = false;

  const money = (v) => `${Number(v).toLocaleString('ru-RU')} ₽`;
  const noLegend = { plugins: { legend: { display: false } } };

  new Chart(document.getElementById('ch-requests'), {
    type: 'bar',
    data: { labels: data.months, datasets: [{ label: 'Заявок', data: data.requests, backgroundColor: accent, borderRadius: 4 }] },
    options: { ...noLegend, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  new Chart(document.getElementById('ch-revenue'), {
    type: 'line',
    data: { labels: data.months, datasets: [{ label: 'Доход', data: data.revenue, borderColor: accent, backgroundColor: accent + '33', fill: true, tension: 0.3 }] },
    options: {
      ...noLegend,
      scales: { y: { beginAtZero: true, ticks: { callback: money } } },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => money(c.parsed.y) } } },
    },
  });

  new Chart(document.getElementById('ch-problems'), {
    type: 'bar',
    data: { labels: data.problems.labels, datasets: [{ label: 'Заявок', data: data.problems.values, backgroundColor: palette[1], borderRadius: 4 }] },
    options: { ...noLegend, indexAxis: 'y', scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  new Chart(document.getElementById('ch-masters'), {
    type: 'bar',
    data: {
      labels: data.masters.labels,
      datasets: [
        { label: 'В работе', data: data.masters.active, backgroundColor: palette[2], borderRadius: 4 },
        { label: 'Выдано за 30 дней', data: data.masters.done, backgroundColor: accent, borderRadius: 4 },
      ],
    },
    options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  new Chart(document.getElementById('ch-devices'), {
    type: 'doughnut',
    data: { labels: data.devices.labels, datasets: [{ data: data.devices.values, backgroundColor: palette, borderColor: color('--surface') }] },
    options: { plugins: { legend: { position: 'right' } } },
  });

  new Chart(document.getElementById('ch-statuses'), {
    type: 'bar',
    data: { labels: data.statuses.labels, datasets: [{ label: 'Заявок', data: data.statuses.values, backgroundColor: palette.slice(0, 5).reverse(), borderRadius: 4 }] },
    options: { ...noLegend, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });
})();
