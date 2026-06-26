// attempt.js — drag-to-order, flashcard reveal, option highlight

// ── Option highlight on select ──
document.querySelectorAll('.attempt-option').forEach(label => {
  const input = label.querySelector('input');
  if (!input) return;
  input.addEventListener('change', () => {
    if (input.type === 'radio') {
      // deselect siblings
      const name = input.name;
      document.querySelectorAll(`input[name="${name}"]`).forEach(r => {
        r.closest('.attempt-option')?.classList.remove('attempt-option--selected');
      });
    }
    label.classList.toggle('attempt-option--selected', input.checked);
  });
});

// ── Flashcard ──
function revealFlashcard() {
  const back = document.getElementById('flashcardBack');
  const opts = document.getElementById('flashcardOptions');
  if (back)  back.classList.add('flashcard-back--visible');
  if (opts) opts.style.display = 'flex';
}

// ── Drag-to-order ──
const orderingList = document.getElementById('orderingList');
if (orderingList) {
  let dragged = null;

  orderingList.querySelectorAll('.ordering-item').forEach(item => {
    item.addEventListener('dragstart', e => {
      dragged = item;
      item.style.opacity = '0.4';
    });
    item.addEventListener('dragend', () => {
      item.style.opacity = '1';
      dragged = null;
      updateOrderingInputs();
    });
    item.addEventListener('dragover', e => {
      e.preventDefault();
      const bounding = item.getBoundingClientRect();
      const offset   = e.clientY - bounding.top - bounding.height / 2;
      if (offset < 0) {
        orderingList.insertBefore(dragged, item);
      } else {
        orderingList.insertBefore(dragged, item.nextSibling);
      }
    });
  });

  function updateOrderingInputs() {
    const container = document.getElementById('orderingInputs');
    container.innerHTML = '';
    orderingList.querySelectorAll('.ordering-item').forEach(item => {
      const inp = document.createElement('input');
      inp.type  = 'hidden';
      inp.name  = 'answer';
      inp.value = item.dataset.idx;
      container.appendChild(inp);
    });
  }

  // Init hidden inputs
  updateOrderingInputs();
}

// ── Multi-answer: at least one checked before submit ──
const answerForm = document.getElementById('answerForm');
if (answerForm) {
  answerForm.addEventListener('submit', function(e) {
    const checkboxes = answerForm.querySelectorAll('input[type="checkbox"][name="answer"]');
    if (checkboxes.length > 0) {
      const anyChecked = [...checkboxes].some(c => c.checked);
      if (!anyChecked) {
        e.preventDefault();
        alert('Selecione ao menos uma opção.');
      }
    }
    // Matching: ensure all selects filled
    const selects = answerForm.querySelectorAll('select[name="answer"]');
    if (selects.length > 0) {
      const anyEmpty = [...selects].some(s => !s.value);
      if (anyEmpty) {
        e.preventDefault();
        alert('Preencha todas as correspondências.');
      }
    }
  });
}
