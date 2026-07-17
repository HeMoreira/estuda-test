from itertools import zip_longest
 
from django.core.exceptions import ValidationError
from ..models import MatchingQuestion, MatchingPair, Question
from .base import BaseQuestionTypeHandler
 
MAX_PAIR_LENGTH = 500
MIN_PAIRS = 2
MAX_PAIRS = 10
 
 
def _clean_pairs(post_data):
    """Pareia os valores brutos de 'data_pairs_left'/'data_pairs_right' pela
    posição original da linha (usando zip_longest para não perder linhas
    quando as duas listas chegam com tamanhos diferentes).
 
    Linhas totalmente em branco são descartadas normalmente. Linhas com
    apenas um dos lados preenchido são reportadas em `partial_rows` (1-based)
    para que `validate()` possa avisar o usuário, em vez de deixar o par
    ser silenciosamente desalinhado com o par seguinte.
    """
    raw_lefts = post_data.getlist('data_pairs_left')
    raw_rights = post_data.getlist('data_pairs_right')
 
    lefts, rights, partial_rows = [], [], []
    for i, (raw_l, raw_r) in enumerate(zip_longest(raw_lefts, raw_rights, fillvalue=''), start=1):
        l, r = raw_l.strip(), raw_r.strip()
        if not l and not r:
            continue
        if not l or not r:
            partial_rows.append(i)
            continue
        lefts.append(l)
        rights.append(r)
    return lefts, rights, partial_rows
 
 
class MatchingHandler(BaseQuestionTypeHandler):
    type_value = Question.Types.MATCHING
 
    def validate(self, post_data, errors):
        lefts, rights, partial_rows = _clean_pairs(post_data)
 
        if partial_rows:
            linhas = ', '.join(str(i) for i in partial_rows)
            errors.append(
                f'Preencha as duas colunas (A e B) da(s) linha(s) {linhas}, '
                'ou deixe a linha inteira em branco.'
            )
 
        if len(lefts) < MIN_PAIRS:
            errors.append(f'Forneça pelo menos {MIN_PAIRS} pares completos (colunas A e B preenchidas).')
        elif len(lefts) > MAX_PAIRS:
            errors.append(f'A questão pode ter no máximo {MAX_PAIRS} pares.')
 
        if any(len(l) > MAX_PAIR_LENGTH or len(r) > MAX_PAIR_LENGTH for l, r in zip(lefts, rights)):
            errors.append(f'Os elementos podem ter no máximo {MAX_PAIR_LENGTH} caracteres.')
 
    def build_instance(self, statement, explanation, post_data):
        return MatchingQuestion(statement=statement, explanation=explanation)
 
    def save_dependencies(self, question, post_data):
        lefts, rights, partial_rows = _clean_pairs(post_data)
        if partial_rows or len(lefts) < MIN_PAIRS or len(lefts) > MAX_PAIRS or any(len(l) > MAX_PAIR_LENGTH or len(r) > MAX_PAIR_LENGTH for l, r in zip(lefts, rights)):
            raise ValidationError('Garanta que todas as linhas de colunas (A e B) tenham sidas preenchidas corretamente.')
        MatchingPair.objects.bulk_create([
            MatchingPair(question=question, left=l, right=r, order=i)
            for i, (l, r) in enumerate(zip(lefts, rights))
        ])
 
    def update_dependencies(self, question, post_data):
        MatchingPair.objects.filter(question=question).delete()
        self.save_dependencies(question, post_data)
 
    def build_edit_json(self, question):
        pairs = MatchingPair.objects.filter(question=question).order_by('order')
        return {'pairs': [{'left': p.left, 'right': p.right} for p in pairs]}
 
    def build_preview_json(self, post_data):
        lefts = post_data.getlist('data_pairs_left')
        rights = post_data.getlist('data_pairs_right')
        return {'pairs': [{'left': l, 'right': r} for l, r in zip(lefts, rights)]}