from django.core.exceptions import ValidationError
from ..models import WrittenQuestion, Question
from .base import BaseQuestionTypeHandler
from .text_utils import clean_text

MAX_ANSWER_LENGTH = 255


class WrittenHandler(BaseQuestionTypeHandler):
    type_value = Question.Types.WRITTEN

    def validate(self, post_data, errors):
        answer = clean_text(post_data.get('data_answer'))
        if not answer:
            errors.append('A resposta escrita esperada não pode ficar vazia.')
        elif len(answer) > MAX_ANSWER_LENGTH:
            errors.append(f'A resposta escrita pode ter no máximo {MAX_ANSWER_LENGTH} caracteres.')

    def build_instance(self, statement, explanation, post_data):
        return WrittenQuestion(
            statement=statement, explanation=explanation,
            expected_answer=clean_text(post_data.get('data_answer')),
        )

    def update_dependencies(self, question, post_data):
        answer = clean_text(post_data.get('data_answer'))
        if not answer or len(answer) > MAX_ANSWER_LENGTH:
            raise ValidationError('A resposta escrita esperada não pode ficar vazia.')
        question.writtenquestion.expected_answer = answer
        question.writtenquestion.save()

    def build_edit_json(self, question):
        return {'answer': question.writtenquestion.expected_answer}

    def build_preview_json(self, post_data):
        return {'answer': post_data.get('data_answer', '')}