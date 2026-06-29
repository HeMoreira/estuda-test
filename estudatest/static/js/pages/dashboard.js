function openTestDetail(id) {
    fetch(DETAIL_BASE + id + '/')
    .then(r => r.json())
    .then(d => {
        document.getElementById('modalTestName').textContent = d.name;
        document.getElementById('modalQCount').textContent = d.question_count + ' questão' + (d.question_count !== 1 ? 'ões' : '');

        const catEl = document.getElementById('modalCategory');
        if (d.category) { catEl.textContent = d.category; catEl.style.display = ''; }
        else catEl.style.display = 'none';

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

        document.getElementById('modalEditBtn').href = '/tests/' + id + '/edit/';
        document.getElementById('modalStartForm').action = '/attempts/start/' + id + '/';

        document.getElementById('testDetailBackdrop').classList.add('modal-backdrop--open');
    })
    .catch(err => console.error('Erro ao carregar detalhes:', err));
}

function closeTestDetail() {
  document.getElementById('testDetailBackdrop').classList.remove('modal-backdrop--open');
}

function drawScoreAsDonut(canvasId, pct) {
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext('2d');
    const cx = 40, cy = 40, r = 30, lw = 10;
    ctx.clearRect(0, 0, 80, 80);
    ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2);
    ctx.strokeStyle = '#2e3033'; ctx.lineWidth = lw; ctx.stroke();
    const angle = (pct/100) * Math.PI * 2 - Math.PI/2;
    ctx.beginPath(); ctx.arc(cx,cy,r,-Math.PI/2, angle);
    const color = pct >= 70 ? '#1D9E75' : pct >= 40 ? '#BA7517' : '#E24B4A';
    ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.lineCap = 'round'; ctx.stroke();
}

document.getElementById('testDetailBackdrop').addEventListener('click', function(e) {
    if (e.target === this) closeTestDetail();
});
document.getElementById('categoryBackdrop').addEventListener('click', function(e) {
    if (e.target === this) closeCategoryModal();
});
document.querySelectorAll('.test-card').forEach(card => {
    const urgencyBar = card.querySelector('.test-card__urgency-bar');
    const lastAttemptText = card.querySelector('.test-card__last-attempt');

    card.addEventListener('click', () => openTestDetail(card.dataset.id));
    urgencyBar.style.backgroundColor = urgencyBar.dataset.urgency_color;
    if (lastAttemptText.dataset.last_attempt) {
        lastAttemptText.style.color = urgencyBar.dataset.urgency_color;
    } else {
        lastAttemptText.style.color = 'var(--color-text-faint)';
    }
});