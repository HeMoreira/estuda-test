// attempt.js — option highlight, drag-to-order, flashcard reveal, matching by click

document.addEventListener('DOMContentLoaded', () => {
  initOptionHighlight();
  initFlashcard();
  initOrdering();
  initMatching();
  initFormValidation();
});

// ── Generic option highlight (radio/checkbox selected state) ──
function initOptionHighlight() {
  document.querySelectorAll('.attempt-option').forEach(label => {
    const input = label.querySelector('input');
    if (!input) return;

    input.addEventListener('change', () => {
      if (input.type === 'radio') {
        document.querySelectorAll(`input[name="${input.name}"]`).forEach(radio =>
          radio.closest('.attempt-option')?.classList.remove('attempt-option--selected')
        );
      }
      label.classList.toggle('attempt-option--selected', input.checked);
    });
  });
}

// ── Flashcard reveal ──
function initFlashcard() {
  const revealBtn = document.querySelector('[data-action="reveal-flashcard"]');
  const back = document.getElementById('flashcardBack');
  if (!revealBtn || !back) return;

  revealBtn.addEventListener('click', () => back.classList.add('flashcard-back--visible'));
}

// ── Drag-to-order ──
function initOrdering() {
  const list = document.getElementById('orderingList');
  if (!list) return;

  const inputsContainer = document.getElementById('orderingInputs');
  let dragged = null;

  function syncInputs() {
    inputsContainer.innerHTML = '';
    list.querySelectorAll('.ordering-item').forEach(item => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'answer';
      input.value = item.dataset.orig;
      inputsContainer.appendChild(input);
    });
  }

  list.querySelectorAll('.ordering-item').forEach(item => {
    item.addEventListener('dragstart', () => {
      dragged = item;
      requestAnimationFrame(() => { item.style.opacity = '0.4'; });
    });
    item.addEventListener('dragend', () => {
      item.style.opacity = '1';
      dragged = null;
      syncInputs();
    });
    item.addEventListener('dragover', e => {
      e.preventDefault();
      if (!dragged || dragged === item) return;
      const midpoint = item.getBoundingClientRect().top + item.offsetHeight / 2;
      list.insertBefore(dragged, e.clientY < midpoint ? item : item.nextSibling);
    });
  });

  syncInputs();
}

// ── Matching by click ──
function initMatching() {
  const leftCol = document.getElementById('matchLeft');
  const rightCol = document.getElementById('matchRight');
  if (!leftCol || !rightCol) return;

  const inputsContainer = document.getElementById('matchingInputs');
  let selectedLeft = null;
  let selectedRight = null;

  function syncInputs() {
    inputsContainer.innerHTML = '';
    // Emite os valores da direita na ordem do DOM da esquerda (apenas os já pareados)
    leftCol.querySelectorAll('.matching-btn--matched').forEach(leftBtn => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'answer';
      input.value = leftBtn.dataset.pairedRight;
      inputsContainer.appendChild(input);
    });
  }

  function tryLock() {
    if (!selectedLeft || !selectedRight) return;

    const leftBtn = selectedLeft;
    const rightBtn = selectedRight;
    selectedLeft = null;
    selectedRight = null;

    leftBtn.dataset.pairedRight = rightBtn.dataset.right;

    [leftBtn, rightBtn].forEach(btn => {
      btn.classList.remove('matching-btn--selected');
      btn.classList.add('matching-btn--matched');
      btn.disabled = true;
    });

    syncInputs();
  }

  function handleClick(e) {
    const btn = e.target.closest('.matching-btn');
    if (!btn || btn.disabled || btn.classList.contains('matching-btn--matched')) return;

    if (btn.dataset.matchSide === 'left') {
      selectedLeft?.classList.remove('matching-btn--selected');
      selectedLeft = (selectedLeft === btn) ? null : btn;
      selectedLeft?.classList.add('matching-btn--selected');
    } else {
      selectedRight?.classList.remove('matching-btn--selected');
      selectedRight = (selectedRight === btn) ? null : btn;
      selectedRight?.classList.add('matching-btn--selected');
    }

    tryLock();
  }

  leftCol.addEventListener('click', handleClick);
  rightCol.addEventListener('click', handleClick);
}

// ── Form validation ──
function initFormValidation() {
  const form = document.getElementById('answerForm');
  if (!form) return;

  form.addEventListener('submit', e => {
    if (!validateMultiAnswer(form)) {
      e.preventDefault();
      alert('Selecione ao menos uma opção.');
      return;
    }
    if (!validateMatching()) {
      e.preventDefault();
    }
  });
}

function validateMultiAnswer(form) {
  const checkboxes = form.querySelectorAll('input[type="checkbox"][name="answer"]');
  if (checkboxes.length === 0) return true;
  return [...checkboxes].some(cb => cb.checked);
}

function validateMatching() {
  const leftCol = document.getElementById('matchLeft');
  if (!leftCol) return true;

  const total = leftCol.querySelectorAll('.matching-btn').length;
  const matched = leftCol.querySelectorAll('.matching-btn--matched').length;

  if (matched < total) {
    alert(`Associe todos os ${total} pares antes de confirmar.`);
    return false;
  }
  return true;
}