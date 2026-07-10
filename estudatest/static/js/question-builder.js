// question-builder.js — controla os fieldsets por tipo de questão

const PANELS = [
  'multiple_choice', 'multi_answer', 'true_false',
  'written', 'ordering', 'matching', 'flashcard',
];

// ── Seleção de tipo ──
function selectType(type, btn, container) {
  document.getElementById('selectedType').value = type;
  container.querySelectorAll('.question-type-btn').forEach(b => b.classList.remove('question-type-btn--active'));
  btn.classList.add('question-type-btn--active');

  PANELS.forEach(panelType => {
    const panel = document.getElementById('panel-' + panelType);
    if (!panel) return;
    const active = panelType === type;
    panel.classList.toggle('fieldset-panel--active', active);
    panel.style.display = active ? '' : 'none';
  });
}

function bindTypeSelector() {
  const container = document.getElementById('typeSelectorContainer');
  if (!container) return;

  container.addEventListener('click', (e) => {
    if (container.dataset.locked === 'true') return; // bloqueio continua só aqui
    const btn = e.target.closest('.question-type-btn');
    if (btn) selectType(btn.dataset.type, btn, container);
  });

  // sempre sincroniza visual + hidden input na carga inicial, mesmo bloqueado
  const current = document.getElementById('selectedType').value || 'multiple_choice';
  const initialBtn = document.querySelector(`[data-type="${current}"]`);
  if (initialBtn) selectType(current, initialBtn, container);
}

// ── Fábricas de elementos de linha ──
function createRemoveButton(className) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = className;
  btn.textContent = '✕';
  return btn;
}

function createOptionRow({ inputType, radioName, inputName, value, textValue = '', placeholder = '' }) {
  const row = document.createElement('div');
  row.className = 'option-row';

  const inputCheck = document.createElement('input');
  inputCheck.type = inputType;
  inputCheck.name = radioName;
  inputCheck.className = `option-row__${inputType === 'radio' ? 'radio' : 'check'}`;
  inputCheck.value = value;

  const inputText = document.createElement('input');
  inputText.type = 'text';
  inputText.name = inputName;
  inputText.className = 'option-row__input';
  inputText.placeholder = placeholder;
  inputText.value = textValue;

  row.append(inputCheck, inputText, createRemoveButton('option-row__remove js-remove-option'));
  return row;
}

function createOrderRow(index, textValue = '') {
  const row = document.createElement('div');
  row.className = 'option-row';

  const span = document.createElement('span');
  span.className = 'option-row__index';
  span.textContent = index;

  const input = document.createElement('input');
  input.type = 'text';
  input.name = 'data_items';
  input.className = 'option-row__input';
  input.placeholder = `Item ${index}`;
  input.value = textValue;

  row.append(span, input, createRemoveButton('option-row__remove js-remove-order'));
  return row;
}

function createPairRow(leftVal = '', rightVal = '') {
  const row = document.createElement('div');
  row.className = 'pair-row';

  const inputLeft = document.createElement('input');
  inputLeft.type = 'text';
  inputLeft.name = 'data_pairs_left';
  inputLeft.className = 'option-row__input pair-row__input--top';
  inputLeft.placeholder = 'Coluna A (Termo)';
  inputLeft.value = leftVal;

  const inputRight = document.createElement('input');
  inputRight.type = 'text';
  inputRight.name = 'data_pairs_right';
  inputRight.className = 'option-row__input pair-row__input--bottom';
  inputRight.placeholder = 'Coluna B (Significado/Resposta)';
  inputRight.value = rightVal;

  row.append(inputLeft, inputRight, createRemoveButton('option-row__remove js-remove-pair'));
  return row;
}

// ── Gerenciamento de listas ──
function reindexRadios(list, name) {
  list.querySelectorAll(`input[name="${name}"]`).forEach((el, i) => { el.value = i; });
}

function addOption({ listId, inputName, radioName, inputType, placeholder, max }) {
  const list = document.getElementById(listId);
  const count = list.querySelectorAll('.option-row').length;
  if (count >= max) { alert(`Máximo de ${max} opções.`); return; }

  const ph = `${placeholder} ${String.fromCharCode(65 + count)}`;
  const row = createOptionRow({ inputType, radioName, inputName, value: count, placeholder: ph });
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

function addOrderItem() {
  const list = document.getElementById('ord-options');
  const count = list.querySelectorAll('.option-row').length;
  if (count >= 8) { alert('Máximo de 8 itens.'); return; }
  list.appendChild(createOrderRow(count + 1));
}

function removeOrderItem(btn) {
  const list = document.getElementById('ord-options');
  if (list.querySelectorAll('.option-row').length <= 2) { alert('Mínimo de 2 itens.'); return; }
  btn.closest('.option-row').remove();
  list.querySelectorAll('.option-row .option-row__index').forEach((span, i) => { span.textContent = i + 1; });
}

function addPair() {
  const list = document.getElementById('match-pairs');
  if (list.querySelectorAll('.pair-row').length >= 10) { alert('Máximo de 10 pares.'); return; }
  list.appendChild(createPairRow());
}

function removePair(btn) {
  const list = document.getElementById('match-pairs');
  if (list.querySelectorAll('.pair-row').length <= 2) { alert('Mínimo de 2 pares.'); return; }
  btn.closest('.pair-row').remove();
}

// ── Envio: consolida pares de matching em campos hidden ──
function serializeMatchingPairsOnSubmit(form) {
  const lefts = [...form.querySelectorAll('input[name="data_pairs_left"]')].map(i => i.value);
  const rights = [...form.querySelectorAll('input[name="data_pairs_right"]')].map(i => i.value);

  form.querySelectorAll('input[name="data_pairs_left"], input[name="data_pairs_right"]').forEach(i => i.remove());

  lefts.forEach((left, idx) => {
    const hiddenLeft = document.createElement('input');
    hiddenLeft.type = 'hidden'; hiddenLeft.name = 'data_pairs_left'; hiddenLeft.value = left;
    const hiddenRight = document.createElement('input');
    hiddenRight.type = 'hidden'; hiddenRight.name = 'data_pairs_right'; hiddenRight.value = rights[idx];
    form.append(hiddenLeft, hiddenRight);
  });
}

// ── Popular formulário em modo edição ──
function populateChoicePanel(listId, inputType, radioName, options, correctCheck, placeholder) {
  const list = document.getElementById(listId);
  list.innerHTML = '';
  options.forEach((opt, i) => {
    const row = createOptionRow({
      inputType,
      radioName,
      inputName: 'data_options',
      value: i,
      textValue: opt,
      placeholder: `${placeholder} ${String.fromCharCode(65 + i)}`,
    });
    if (correctCheck(i)) row.querySelector(`input[type="${inputType}"]`).checked = true;
    list.appendChild(row);
  });
}

function populateEditData(type, data) {
  if (type === 'multiple_choice') {
    populateChoicePanel('mc-options', 'radio', 'data_correct', data.options || [], i => data.correct == i, 'Alternativa');
  } else if (type === 'multi_answer') {
    populateChoicePanel('ma-options', 'checkbox', 'data_correct', data.options || [], i => (data.correct || []).includes(i), 'Opção');
  } else if (type === 'true_false') {
    const val = data.correct ? 'true' : 'false';
    document.querySelectorAll('#panel-true_false input[name="data_correct"]').forEach(r => { r.checked = r.value === val; });
  } else if (type === 'written') {
    const el = document.querySelector('#panel-written input[name="data_answer"]');
    if (el) el.value = data.answer || '';
  } else if (type === 'ordering') {
    const list = document.getElementById('ord-options');
    list.innerHTML = '';
    (data.items || []).forEach((item, i) => list.appendChild(createOrderRow(i + 1, item)));
  } else if (type === 'matching') {
    const list = document.getElementById('match-pairs');
    list.innerHTML = '';
    (data.pairs || []).forEach(pair => list.appendChild(createPairRow(pair.left, pair.right)));
  } else if (type === 'flashcard') {
    const front = document.querySelector('#panel-flashcard textarea[name="data_front"]');
    const back = document.querySelector('#panel-flashcard textarea[name="data_back"]');
    if (front) front.value = data.front || '';
    if (back) back.value = data.back || '';
  }
}

function initEditMode() {
  const dataEl = document.getElementById('editData');
  if (!dataEl) return;
  const type = document.getElementById('selectedType').value;
  populateEditData(type, JSON.parse(dataEl.textContent));
}

// ── Inicialização de eventos ──
function bindTypeSelector() {
  const container = document.getElementById('typeSelectorContainer');
  if (!container) return;

  container.addEventListener('click', (e) => {
    if (container.dataset.locked === 'true') return; // bloqueia só a troca por clique
    const btn = e.target.closest('.question-type-btn');
    if (btn) selectType(btn.dataset.type, btn, container);
  });

  // A ativação inicial do painel deve acontecer sempre, mesmo bloqueado
  const current = document.getElementById('selectedType').value || 'multiple_choice';
  const initialBtn = document.querySelector(`[data-type="${current}"]`);
  if (initialBtn) selectType(current, initialBtn, container);
}

function bindDynamicPanels() {
  const panelsContainer = document.getElementById('dynamicPanelsContainer');
  if (!panelsContainer) return;

  panelsContainer.addEventListener('click', (e) => {
    const target = e.target;
    if (target.classList.contains('js-remove-option')) return removeOption(target);
    if (target.classList.contains('js-remove-order')) return removeOrderItem(target);
    if (target.classList.contains('js-remove-pair')) return removePair(target);

    const action = target.dataset.action;
    if (action === 'add-option') {
      return addOption({
        listId: target.dataset.target,
        inputName: target.dataset.inputName,
        radioName: target.dataset.radioName,
        inputType: target.dataset.inputType,
        placeholder: target.dataset.placeholder,
        max: parseInt(target.dataset.max, 10),
      });
    }
    if (action === 'add-order') return addOrderItem();
    if (action === 'add-pair') return addPair();
  });
}

function bindFormSubmit() {
  const form = document.getElementById('questionForm');
  if (!form) return;
  form.addEventListener('submit', () => {
    if (document.getElementById('selectedType').value === 'matching') {
      serializeMatchingPairsOnSubmit(form);
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  bindTypeSelector();
  bindDynamicPanels();
  bindFormSubmit();
  initEditMode();
});