(() => {
  const data = JSON.parse(document.getElementById('stats-data').textContent);
  if (!window.Chart) return;

  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();
  // Цвета берутся из токенов CSS, поэтому графики сами подстраиваются под тёмную тему.
  const accent = color('--signal');
  const ink = color('--ink');
  const palette = [accent, color('--blue'), color('--amber'), color('--green'), ink, color('--muted'), color('--red'), color('--rule')];

  Chart.defaults.color = color('--muted');
  Chart.defaults.borderColor = color('--rule');
  Chart.defaults.font.family = color('--mono') || css.fontFamily;
  Chart.defaults.font.size = 11;
  Chart.defaults.maintainAspectRatio = false;
  // Уважаем системную настройку «уменьшить движение».
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) Chart.defaults.animation = false;

  const money = (v) => `${Number(v).toLocaleString('ru-RU')} ₽`;
  const noLegend = { plugins: { legend: { display: false } } };

  new Chart(document.getElementById('ch-requests'), {
    type: 'bar',
    data: { labels: data.months, datasets: [{ label: 'Заявок', data: data.requests, backgroundColor: accent }] },
    options: { ...noLegend, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  new Chart(document.getElementById('ch-revenue'), {
    type: 'line',
    data: { labels: data.months, datasets: [{ label: 'Доход', data: data.revenue, borderColor: ink, backgroundColor: color('--signal-soft'), pointBackgroundColor: accent, pointBorderColor: ink, fill: true, tension: 0, borderWidth: 2 }] },
    options: {
      ...noLegend,
      scales: { y: { beginAtZero: true, ticks: { callback: money } } },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => money(c.parsed.y) } } },
    },
  });

  new Chart(document.getElementById('ch-problems'), {
    type: 'bar',
    data: { labels: data.problems.labels, datasets: [{ label: 'Заявок', data: data.problems.values, backgroundColor: ink }] },
    options: { ...noLegend, indexAxis: 'y', scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  new Chart(document.getElementById('ch-masters'), {
    type: 'bar',
    data: {
      labels: data.masters.labels,
      datasets: [
        { label: 'В работе', data: data.masters.active, backgroundColor: accent },
        { label: 'Выдано за 30 дней', data: data.masters.done, backgroundColor: ink },
      ],
    },
    options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  new Chart(document.getElementById('ch-devices'), {
    type: 'doughnut',
    data: { labels: data.devices.labels, datasets: [{ data: data.devices.values, backgroundColor: palette, borderColor: color('--surface'), borderWidth: 2 }] },
    options: { plugins: { legend: { position: 'right' } } },
  });

  new Chart(document.getElementById('ch-statuses'), {
    type: 'bar',
    data: { labels: data.statuses.labels, datasets: [{ label: 'Заявок', data: data.statuses.values, backgroundColor: [color('--blue'), color('--amber'), accent, color('--green'), color('--muted')] }] },
    options: { ...noLegend, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });
})();
