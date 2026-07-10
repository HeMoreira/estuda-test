from django.core.exceptions import ValidationError
from ..models import FlashcardQuestion, Question
from .base import BaseQuestionTypeHandler
from .text_utils import clean_text

MAX_TEXT_LENGTH = 1000


class FlashcardHandler(BaseQuestionTypeHandler):
    type_value = Question.Types.FLASHCARD

    def validate(self, post_data, errors):
        front = clean_text(post_data.get('data_front'))
        back = clean_text(post_data.get('data_back'))
        if not front or not back:
            errors.append('Texto de frente e verso são obrigatórios para o Flashcard.')
        elif len(front) > MAX_TEXT_LENGTH or len(back) > MAX_TEXT_LENGTH:
            errors.append(f'O texto de frente e verso podem ter no máximo {MAX_TEXT_LENGTH} caracteres.')

    def build_instance(self, statement, explanation, post_data):
        return FlashcardQuestion(
            statement=statement, explanation=explanation,
            front=clean_text(post_data.get('data_front')),
            back=clean_text(post_data.get('data_back')),
        )

    def update_dependencies(self, question, post_data):
        front, back = clean_text(post_data.get('data_front')), clean_text(post_data.get('data_back'))
        if not front or not back:
            raise ValidationError('Texto de frente e verso são obrigatórios para o Flashcard.')
        question.flashcardquestion.front = front
        question.flashcardquestion.back = back
        question.flashcardquestion.save()

    def build_edit_json(self, question):
        return {'front': question.flashcardquestion.front, 'back': question.flashcardquestion.back}

    def build_preview_json(self, post_data):
        return {
            'front': post_data.get('data_front', ''),
            'back': post_data.get('data_back', ''),
        }