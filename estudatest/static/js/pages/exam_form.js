// exam_form.js — estilização de inputs e exclusão de questões

function applyFormStyles() {
  document.querySelectorAll('#examForm input[type=text], #examForm select').forEach(el => {
    el.classList.add(el.tagName === 'SELECT' ? 'form__select' : 'form__input');
  });
}

async function deleteQuestion(questionPk, examPk, itemEl) {
  if (!confirm('Remover esta questão?')) return;
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;

  try {
    const response = await fetch(`/exams/${examPk}/questions/${questionPk}/delete/`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': csrf },
    });
    const result = await response.json();
    if (result.ok) {
      itemEl.remove();
    } else {
      alert('Não foi possível remover a questão.');
    }
  } catch (err) {
    alert('Erro de conexão ao remover a questão.');
  }
}

function bindQuestionDeleteButtons() {
  document.querySelectorAll('.question-item__actions [data-question]').forEach(btn => {
    btn.addEventListener('click', () => {
      deleteQuestion(btn.dataset.question, btn.dataset.exam, btn.closest('.question-item'));
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  applyFormStyles();
  bindQuestionDeleteButtons();
});