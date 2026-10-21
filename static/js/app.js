// Мобильное меню
document.querySelectorAll('[data-nav-toggle]').forEach((btn) => {
  const nav = document.querySelector('[data-nav]');
  btn.addEventListener('click', () => {
    const open = nav.classList.toggle('is-open');
    btn.setAttribute('aria-expanded', String(open));
  });
});

// Подтверждение опасных действий: <form data-confirm="Текст вопроса">
document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (e) => {
    if (!window.confirm(form.dataset.confirm)) e.preventDefault();
  });
});

// Превью выбранных фото и проверка лимитов до отправки формы
document.querySelectorAll('form[data-photo-preview]').forEach((form) => {
  const input = form.querySelector('input[type=file]');
  const box = form.querySelector('[data-preview]');
  if (!input || !box) return;
  const MAX_FILES = 5;
  const MAX_SIZE = 5 * 1024 * 1024;
  input.addEventListener('change', () => {
    box.replaceChildren();
    const files = Array.from(input.files);
    let error = '';
    if (files.length > MAX_FILES) error = `Можно прикрепить не больше ${MAX_FILES} фото.`;
    const big = files.find((f) => f.size > MAX_SIZE);
    if (big) error = `Файл «${big.name}» больше 5 МБ.`;
    input.setCustomValidity(error);
    if (error) { input.reportValidity(); return; }
    files.forEach((f) => {
      const img = document.createElement('img');
      img.alt = f.name;
      img.src = URL.createObjectURL(f);
      img.onload = () => URL.revokeObjectURL(img.src);
      box.append(img);
    });
  });
});
