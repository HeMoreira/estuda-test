// Utilitários
function drawScoreAsDonut(canvasId, pct) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const cx = 40, cy = 40, r = 30, lw = 10;
    
    ctx.clearRect(0, 0, 80, 80);
    
    // Círculo de fundo
    ctx.beginPath(); 
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = '#2e3033'; 
    ctx.lineWidth = lw; 
    ctx.stroke();
    
    // Arco do score
    const angle = (pct / 100) * Math.PI * 2 - Math.PI / 2;
    ctx.beginPath(); 
    ctx.arc(cx, cy, r, -Math.PI / 2, angle);
    
    const color = pct >= 70 ? '#1D9E75' : pct >= 40 ? '#BA7517' : '#E24B4A';
    ctx.strokeStyle = color; 
    ctx.lineWidth = lw; 
    ctx.lineCap = 'round'; 
    ctx.stroke();
}

// Modais do Dashboard
function openCategoryModal() {
    document.getElementById('categoryNameInput').value = '';
    document.getElementById('categoryFormErrors').innerHTML = '';
    document.getElementById('categoryBackdrop').classList.add('modal-backdrop--open');
    setTimeout(() => document.getElementById('categoryNameInput').focus(), 100);
}

function closeCategoryModal() {
    document.getElementById('categoryBackdrop').classList.remove('modal-backdrop--open');
}

function openExamDetail(id) {
    // Garante que a URL base global do Django existe antes de fazer o fetch
    if (typeof DETAIL_BASE === 'undefined') return console.error('DETAIL_BASE não definida.');

    fetch(DETAIL_BASE.replace('PK', id))
        .then(r => r.json())
        .then(d => {
            document.getElementById('modalExamName').textContent = d.name;
            document.getElementById('modalQCount').textContent = `${d.question_count} quest${d.question_count !== 1 ? 'ões' : 'ão'}`;

            const catEl = document.getElementById('modalCategory');
            if (d.category) { 
                catEl.textContent = d.category;
            } else {
                catEl.style.display = 'none';
            }

            document.getElementById('modalUpdated').textContent = 'Atualizada em ' + d.updated_at;
            document.getElementById('modalAttemptCount').textContent = d.attempt_count || '0';
            document.getElementById('modalLastDate').textContent = d.last_attempt_date || '—';
            document.getElementById('modalAvgDuration').textContent = d.avg_duration || '—';
            document.getElementById('modalLastDuration').textContent = d.last_duration || '—';

            const scoreRow = document.getElementById('modalScoreRow');
            if (d.score_percent !== null && d.score_percent !== undefined) {
                scoreRow.style.display = 'flex';
                document.getElementById('scoreChartLabel').textContent = d.score_percent + '%';
                document.getElementById('scoreChartDesc').textContent = 'na última tentativa';
                drawScoreAsDonut('scoreChart', d.score_percent);
            } else {
                scoreRow.style.display = 'none';
            }

            document.getElementById('modalEditBtn').href = `/exams/${id}/edit/`;
            document.getElementById('modalStartForm').action = `/attempts/start/${id}/`;

            document.getElementById('examDetailBackdrop').classList.add('modal-backdrop--open');
        })
        .catch(err => console.error('Erro ao carregar detalhes:', err));
}

function closeExamDetail() {
    document.getElementById('examDetailBackdrop').classList.remove('modal-backdrop--open');
}

// Submissão do formulário de categoria via AJAX
function submitCategory() {
    const name = document.getElementById('categoryNameInput').value.trim();
    const errEl = document.getElementById('categoryFormErrors');
    errEl.innerHTML = '';

    if (!name) {
        errEl.innerHTML = '<div class="form__error">Informe um nome para a categoria.</div>';
        return;
    }

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/categories/create/', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/x-www-form-urlencoded', 
            'X-CSRFToken': csrfToken 
        },
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

// Inicialização dos cards e listeners para os modais
document.querySelectorAll('.exam-card').forEach(card => {
    const urgencyBar = card.querySelector('.exam-card__urgency-bar');
    const lastAttemptText = card.querySelector('.exam-card__last-attempt');

    if (urgencyBar) {
        urgencyBar.style.backgroundColor = urgencyBar.dataset.urgency_color;
        if (lastAttemptText) {
            lastAttemptText.style.color = lastAttemptText.dataset.last_attempt 
                ? urgencyBar.dataset.urgency_color 
                : 'var(--color-text-faint)';
        }
    }
    card.addEventListener('click', () => openExamDetail(card.dataset.id));
});

const newCategoryButton = document.querySelector('#new-category-button');
if (newCategoryButton) {
    newCategoryButton.addEventListener('click', openCategoryModal);
}
const categorySaveBtn = document.getElementById('categorySaveBtn');
if (categorySaveBtn) {
    categorySaveBtn.addEventListener('click', submitCategory);
}

const examDetailBackdrop = document.getElementById('examDetailBackdrop');
if (examDetailBackdrop) {
    examDetailBackdrop.addEventListener('click', function(e) {
        if (e.target === this) closeExamDetail();
    });
}

const categoryBackdrop = document.getElementById('categoryBackdrop');
if (categoryBackdrop) {
    categoryBackdrop.addEventListener('click', function(e) {
        if (e.target === this) closeCategoryModal();
    });
}

document.querySelectorAll('#examDetailModal .modal__close, #examDetailModal .modal-close-btn').forEach(btn => {
    btn.addEventListener('click', closeExamDetail);
});
document.querySelectorAll('#categoryModal .modal__close, #categoryModal .modal-close-btn').forEach(btn => {
    btn.addEventListener('click', closeCategoryModal);
});

// Atalho da tecla ESC para fechar ambos os modais
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeCategoryModal();
        closeExamDetail();
    }
});