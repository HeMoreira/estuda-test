document.querySelectorAll('#examForm input[type=text], #examForm select').forEach(el => {
  if (el.tagName === 'SELECT') el.classList.add('form__select');
  else el.classList.add('form__input');
});

function deleteQuestion(qpk, btn) {
  if (!confirm('Remover esta questão?')) return;
  const examPk = btn.dataset.exam;
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
  fetch(`/exams/${examPk}/questions/${qpk}/delete/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': csrf },
  }).then(r => r.json()).then(d => {
    if (d.ok) location.reload();
  });
}

document.querySelectorAll('.question-item__actions button').forEach(btn => {
    btn.addEventListener('click', () => deleteQuestion(btn.dataset.question, btn));
});