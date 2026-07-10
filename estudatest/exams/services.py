from django.core.exceptions import ValidationError
from django.db import transaction
from .question_types import get_handler
from .utils import validate_question_payload


class QuestionService:
    """Orquestra criação/edição de questões, delegando as regras
    específicas de cada tipo ao handler correspondente (question_types/)."""

    @staticmethod
    @transaction.atomic
    def create_question(exam, question_type, post_data):
        statement, explanation = validate_question_payload(question_type, post_data)
        handler = get_handler(question_type)

        question = handler.build_instance(statement, explanation, post_data)
        if question is None:
            raise ValidationError('Tipo de questão inválido.')

        question.exam = exam
        question.order = exam.questions.count()
        question.save()
        handler.save_dependencies(question, post_data)
        return question

    @staticmethod
    @transaction.atomic
    def update_question(instance, question_type, post_data):
        statement, explanation = validate_question_payload(question_type, post_data)
        instance.statement = statement
        instance.explanation = explanation
        instance.save()
        get_handler(question_type).update_dependencies(instance, post_data)
        return instance