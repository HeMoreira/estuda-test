from django.core.exceptions import ValidationError
from ..models import TrueFalseQuestion, Question
from .base import BaseQuestionTypeHandler

TRUE_VALUES = ('true', '1', 'verdadeiro')
VALID_VALUES = ('true', 'false', '1', '0', 'verdadeiro', 'falso')


class TrueFalseHandler(BaseQuestionTypeHandler):
    type_value = Question.Types.TRUE_FALSE

    def validate(self, post_data, errors):
        if post_data.get('data_correct') not in VALID_VALUES:
            errors.append('Selecione verdadeiro ou falso.')

    def build_instance(self, statement, explanation, post_data):
        value = post_data.get('data_correct', 'false')
        return TrueFalseQuestion(
            statement=statement, explanation=explanation,
            correct_answer=value in TRUE_VALUES,
        )

    def update_dependencies(self, question, post_data):
        value = post_data.get('data_correct')
        if value not in VALID_VALUES:
            raise ValidationError('Valor inválido enviado para a resposta de Verdadeiro ou Falso.')
        question.truefalsequestion.correct_answer = value in TRUE_VALUES
        question.truefalsequestion.save()

    def build_edit_json(self, question):
        return {'correct': bool(question.truefalsequestion.correct_answer)}

    def build_preview_json(self, post_data):
        return {'correct': post_data.get('data_correct') in TRUE_VALUES}