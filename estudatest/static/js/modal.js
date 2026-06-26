// modal.js — Category popup AJAX
function openCategoryModal() {
  document.getElementById('categoryNameInput').value = '';
  document.getElementById('categoryFormErrors').innerHTML = '';
  document.getElementById('categoryBackdrop').classList.add('modal-backdrop--open');
  setTimeout(() => document.getElementById('categoryNameInput').focus(), 100);
}

function closeCategoryModal() {
  document.getElementById('categoryBackdrop').classList.remove('modal-backdrop--open');
}

function submitCategory() {
  const name = document.getElementById('categoryNameInput').value.trim();
  const errEl = document.getElementById('categoryFormErrors');
  errEl.innerHTML = '';
  if (!name) {
    errEl.innerHTML = '<div class="form__error">Informe um nome para a categoria.</div>';
    return;
  }
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
  fetch('/categories/create/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf },
    body: 'name=' + encodeURIComponent(name),
  })
  .then(r => r.json())
  .then(d => {
    if (d.ok) {
      closeCategoryModal();
      location.reload();
    } else {
      errEl.innerHTML = '<div class="form__error">Erro ao salvar. Tente novamente.</div>';
    }
  })
  .catch(() => {
    errEl.innerHTML = '<div class="form__error">Erro de conexão.</div>';
  });
}

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeCategoryModal();
    if (typeof closeTestDetail === 'function') closeTestDetail();
  }
});
