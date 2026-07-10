from django.core.exceptions import ValidationError
from ..models import MatchingQuestion, MatchingPair, Question
from .base import BaseQuestionTypeHandler

MAX_PAIR_LENGTH = 500
MIN_PAIRS = 2


def _clean_pairs(post_data):
    lefts = [text.strip() for text in post_data.getlist('data_pairs_left') if text.strip()]
    rights = [text.strip() for text in post_data.getlist('data_pairs_right') if text.strip()]
    return lefts, rights


class MatchingHandler(BaseQuestionTypeHandler):
    type_value = Question.Types.MATCHING

    def validate(self, post_data, errors):
        lefts, rights = _clean_pairs(post_data)
        if len(lefts) < MIN_PAIRS or len(lefts) != len(rights):
            errors.append('Garanta que todas as linhas de colunas (A e B) estejam preenchidas.')
            return
        if any(len(l) > MAX_PAIR_LENGTH or len(r) > MAX_PAIR_LENGTH for l, r in zip(lefts, rights)):
            errors.append(f'Os elementos podem ter no máximo {MAX_PAIR_LENGTH} caracteres.')

    def build_instance(self, statement, explanation, post_data):
        return MatchingQuestion(statement=statement, explanation=explanation)

    def save_dependencies(self, question, post_data):
        lefts, rights = _clean_pairs(post_data)
        if len(lefts) < MIN_PAIRS or len(lefts) != len(rights):
            raise ValidationError('Garanta que todas as linhas de colunas (A e B) estejam preenchidas.')
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