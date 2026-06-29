// attempt.js — option highlight, drag-to-order, flashcard, matching by click

// ── Generic option highlight ──
document.querySelectorAll('.attempt-option').forEach(label => {
  const input = label.querySelector('input');
  if (!input) return;
  input.addEventListener('change', () => {
    if (input.type === 'radio') {
      document.querySelectorAll(`input[name="${input.name}"]`).forEach(r =>
        r.closest('.attempt-option')?.classList.remove('attempt-option--selected')
      );
    }
    label.classList.toggle('attempt-option--selected', input.checked);
  });
});

// ── Flashcard reveal ──
function revealFlashcard() {
  document.getElementById('flashcardBack')?.classList.add('flashcard-back--visible');
}

// ── Drag-to-order ──
(function initOrdering() {
  const list = document.getElementById('orderingList');
  if (!list) return;

  let dragged = null;

  function syncInputs() {
    const container = document.getElementById('orderingInputs');
    container.innerHTML = '';
    list.querySelectorAll('.ordering-item').forEach(item => {
      const inp = document.createElement('input');
      inp.type = 'hidden'; inp.name = 'answer'; inp.value = item.dataset.orig;
      container.appendChild(inp);
    });
  }
  syncInputs();

  list.querySelectorAll('.ordering-item').forEach(item => {
    item.addEventListener('dragstart', () => {
      dragged = item;
      requestAnimationFrame(() => item.style.opacity = '0.4');
    });
    item.addEventListener('dragend', () => {
      item.style.opacity = '1';
      dragged = null;
      syncInputs();
    });
    item.addEventListener('dragover', e => {
      e.preventDefault();
      if (!dragged || dragged === item) return;
      const mid = item.getBoundingClientRect().top + item.offsetHeight / 2;
      list.insertBefore(dragged, e.clientY < mid ? item : item.nextSibling);
    });
  });
})();

// ── Matching by click ──
(function initMatching() {
  const leftCol  = document.getElementById('matchLeft');
  const rightCol = document.getElementById('matchRight');
  if (!leftCol || !rightCol) return;

  const total    = window.MATCH_TOTAL || 0;
  const pairsDoneEl = document.getElementById('matchPairsDone');
  const statusEl    = document.getElementById('matchStatus');

  let selLeft  = null;
  let selRight = null;
  let done     = 0;

  function setStatus() {
    if (statusEl) statusEl.textContent = `${done} / ${total} pares associados`;
  }

  function syncInputs() {
    const container = document.getElementById('matchingInputs');
    container.innerHTML = '';
    // Emit right-side values in left-column DOM order (matched ones only)
    leftCol.querySelectorAll('.matching-btn--matched').forEach(lb => {
      const inp = document.createElement('input');
      inp.type = 'hidden'; inp.name = 'answer'; inp.value = lb.dataset.pairedRight;
      container.appendChild(inp);
    });
  }

  function tryLock() {
    if (!selLeft || !selRight) return;
    const lb = selLeft, rb = selRight;
    selLeft = null; selRight = null;

    // Store pairing on left button
    lb.dataset.pairedRight = rb.dataset.right;

    [lb, rb].forEach(b => {
      b.classList.remove('matching-btn--selected');
      b.classList.add('matching-btn--matched');
      b.disabled = true;
    });

    done++;
    syncInputs();
    setStatus();

    // Show confirmation tag
    const tag = document.createElement('div');
    tag.className = 'matching-pair-tag';
    tag.textContent = `✓ ${lb.dataset.left} → ${rb.dataset.right}`;
    pairsDoneEl.appendChild(tag);
  }

  // Expose click handler globally (called from template onclick)
  window.matchClick = function(side, btn) {
    if (btn.disabled || btn.classList.contains('matching-btn--matched')) return;

    if (side === 'left') {
      if (selLeft) selLeft.classList.remove('matching-btn--selected');
      selLeft = (selLeft === btn) ? null : btn;
      if (selLeft) selLeft.classList.add('matching-btn--selected');
    } else {
      if (selRight) selRight.classList.remove('matching-btn--selected');
      selRight = (selRight === btn) ? null : btn;
      if (selRight) selRight.classList.add('matching-btn--selected');
    }

    tryLock();
  };

  setStatus();
})();

// ── Form validation ──
const answerForm = document.getElementById('answerForm');
if (answerForm) {
  answerForm.addEventListener('submit', function(e) {
    // Multi-answer
    const cbs = answerForm.querySelectorAll('input[type="checkbox"][name="answer"]');
    if (cbs.length > 0 && ![...cbs].some(c => c.checked)) {
      e.preventDefault();
      alert('Selecione ao menos uma opção.');
      return;
    }
    // Matching: all pairs done
    const total = window.MATCH_TOTAL || 0;
    if (total > 0) {
      const done = document.querySelectorAll('#matchLeft .matching-btn--matched').length;
      if (done < total) {
        e.preventDefault();
        alert(`Associe todos os ${total} pares antes de confirmar.`);
        return;
      }
    }
  });
}
