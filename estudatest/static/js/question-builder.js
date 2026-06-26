// question-builder.js — controla os fieldsets por tipo de questão

const PANELS = [
  'multiple_choice','multi_answer','true_false',
  'written','ordering','matching','flashcard'
];

function selectType(type, btn) {
  document.getElementById('selectedType').value = type;
  document.querySelectorAll('.question-type-btn').forEach(b => b.classList.remove('question-type-btn--active'));
  btn.classList.add('question-type-btn--active');
  PANELS.forEach(p => {
    const el = document.getElementById('panel-' + p);
    if (el) el.classList.toggle('fieldset-panel--active', p === type);
  });
}

// Activate first/current panel on load
document.addEventListener('DOMContentLoaded', () => {
  const current = document.getElementById('selectedType').value || 'multiple_choice';
  const btn = document.querySelector(`[data-type="${current}"]`);
  if (btn) selectType(current, btn);
});

// ── Multiple choice / Multi-answer helpers ──
function addOption(listId, inputName, radioName, inputType, placeholder, max) {
  const list = document.getElementById(listId);
  const count = list.querySelectorAll('.option-row').length;
  if (count >= max) { alert(`Máximo de ${max} opções.`); return; }
  const row = document.createElement('div');
  row.className = 'option-row';
  row.innerHTML = `
    <input type="${inputType}" name="${radioName}" class="option-row__${inputType === 'radio' ? 'radio' : 'check'}" value="${count}">
    <input type="text" name="${inputName}" class="option-row__input" placeholder="${placeholder} ${String.fromCharCode(65 + count)}">
    <button type="button" class="option-row__remove" onclick="removeOption(this)">✕</button>`;
  list.appendChild(row);
  reindexRadios(list, radioName);
}

function removeOption(btn) {
  const row = btn.closest('.option-row');
  const list = row.parentElement;
  if (list.querySelectorAll('.option-row').length <= 2) { alert('Mínimo de 2 opções.'); return; }
  row.remove();
  const radioName = list.querySelector('input[type=radio], input[type=checkbox]')?.name;
  if (radioName) reindexRadios(list, radioName);
}

function reindexRadios(list, name) {
  list.querySelectorAll(`input[name="${name}"]`).forEach((el, i) => el.value = i);
}

// ── Ordering helpers ──
function addOrderItem() {
  const list = document.getElementById('ord-options');
  const count = list.querySelectorAll('.option-row').length;
  if (count >= 8) { alert('Máximo de 8 itens.'); return; }
  const row = document.createElement('div');
  row.className = 'option-row';
  row.innerHTML = `
    <span style="color:var(--color-text-faint);font-size:.8rem;min-width:1.2rem">${count + 1}</span>
    <input type="text" name="data_items" class="option-row__input" placeholder="Item ${count + 1}">
    <button type="button" class="option-row__remove" onclick="removeOrderItem(this)">✕</button>`;
  list.appendChild(row);
}

function removeOrderItem(btn) {
  const list = document.getElementById('ord-options');
  if (list.querySelectorAll('.option-row').length <= 2) { alert('Mínimo de 2 itens.'); return; }
  btn.closest('.option-row').remove();
  list.querySelectorAll('.option-row span').forEach((s, i) => s.textContent = i + 1);
}

// ── Matching helpers ──
function addPair() {
  const list = document.getElementById('match-pairs');
  if (list.querySelectorAll('.pair-row').length >= 10) { alert('Máximo de 10 pares.'); return; }
  const row = document.createElement('div');
  row.className = 'pair-row';
  row.innerHTML = `
    <input type="text" name="data_pairs_left" class="option-row__input" placeholder="Coluna A">
    <span class="pair-row__sep">→</span>
    <input type="text" name="data_pairs_right" class="option-row__input" placeholder="Coluna B">
    <button type="button" class="option-row__remove" onclick="removePair(this)">✕</button>`;
  list.appendChild(row);
}

function removePair(btn) {
  const list = document.getElementById('match-pairs');
  if (list.querySelectorAll('.pair-row').length <= 2) { alert('Mínimo de 2 pares.'); return; }
  btn.closest('.pair-row').remove();
}

// ── Populate on edit ──
function populateEditData(type, data) {
  if (type === 'multiple_choice') {
    const list = document.getElementById('mc-options');
    list.innerHTML = '';
    (data.options || []).forEach((opt, i) => {
      const row = document.createElement('div');
      row.className = 'option-row';
      row.innerHTML = `
        <input type="radio" name="data_correct" class="option-row__radio" value="${i}" ${data.correct == i ? 'checked' : ''}>
        <input type="text" name="data_options" class="option-row__input" value="${escHtml(opt)}">
        <button type="button" class="option-row__remove" onclick="removeOption(this)">✕</button>`;
      list.appendChild(row);
    });

  } else if (type === 'multi_answer') {
    const list = document.getElementById('ma-options');
    list.innerHTML = '';
    (data.options || []).forEach((opt, i) => {
      const row = document.createElement('div');
      row.className = 'option-row';
      const checked = (data.correct || []).includes(i) ? 'checked' : '';
      row.innerHTML = `
        <input type="checkbox" name="data_correct" class="option-row__check" value="${i}" ${checked}>
        <input type="text" name="data_options" class="option-row__input" value="${escHtml(opt)}">
        <button type="button" class="option-row__remove" onclick="removeOption(this)">✕</button>`;
      list.appendChild(row);
    });

  } else if (type === 'true_false') {
    const val = data.correct ? 'true' : 'false';
    document.querySelectorAll('#panel-true_false input[name="data_correct"]').forEach(r => {
      r.checked = r.value === val;
    });

  } else if (type === 'written') {
    const el = document.querySelector('#panel-written input[name="data_answer"]');
    if (el) el.value = data.answer || '';

  } else if (type === 'ordering') {
    const list = document.getElementById('ord-options');
    list.innerHTML = '';
    (data.items || []).forEach((item, i) => {
      const row = document.createElement('div');
      row.className = 'option-row';
      row.innerHTML = `
        <span style="color:var(--color-text-faint);font-size:.8rem;min-width:1.2rem">${i + 1}</span>
        <input type="text" name="data_items" class="option-row__input" value="${escHtml(item)}">
        <button type="button" class="option-row__remove" onclick="removeOrderItem(this)">✕</button>`;
      list.appendChild(row);
    });

  } else if (type === 'matching') {
    const list = document.getElementById('match-pairs');
    list.innerHTML = '';
    (data.pairs || []).forEach(pair => {
      const row = document.createElement('div');
      row.className = 'pair-row';
      row.innerHTML = `
        <input type="text" name="data_pairs_left" class="option-row__input" value="${escHtml(pair.left)}">
        <span class="pair-row__sep">→</span>
        <input type="text" name="data_pairs_right" class="option-row__input" value="${escHtml(pair.right)}">
        <button type="button" class="option-row__remove" onclick="removePair(this)">✕</button>`;
      list.appendChild(row);
    });

  } else if (type === 'flashcard') {
    const front = document.querySelector('#panel-flashcard textarea[name="data_front"]');
    const back  = document.querySelector('#panel-flashcard textarea[name="data_back"]');
    if (front) front.value = data.front || '';
    if (back)  back.value  = data.back  || '';
  }
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Fix matching POST: build pairs[] from pairs_left/right ──
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('questionForm');
  if (!form) return;
  form.addEventListener('submit', function(e) {
    const type = document.getElementById('selectedType').value;
    if (type === 'matching') {
      const lefts  = [...form.querySelectorAll('input[name="data_pairs_left"]')].map(i => i.value);
      const rights = [...form.querySelectorAll('input[name="data_pairs_right"]')].map(i => i.value);
      // Remove individual left/right fields and replace with combined pairs
      form.querySelectorAll('input[name="data_pairs_left"], input[name="data_pairs_right"]').forEach(i => i.remove());
      lefts.forEach((l, idx) => {
        const hl = document.createElement('input'); hl.type='hidden'; hl.name='data_pairs_left';  hl.value=l;      form.appendChild(hl);
        const hr = document.createElement('input'); hr.type='hidden'; hr.name='data_pairs_right'; hr.value=rights[idx]; form.appendChild(hr);
      });
    }
  });
});
