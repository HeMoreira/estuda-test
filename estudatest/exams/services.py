from django.core.exceptions import ValidationError
from django.db import transaction
from .utils import (
    _create_polymorphic_instance,
    _process_question_dependencies,
    _update_polymorphic_instance,
    validate_question_payload,
)

class QuestionService:
    @staticmethod
    @transaction.atomic
    def create_question(exam, question_type, post_data):
        stmt, expl = validate_question_payload(question_type, post_data)
        q = _create_polymorphic_instance(question_type, stmt, expl, post_data)
        if q is None:
            raise ValidationError('Tipo de questão inválido.')
        q.exam = exam
        q.order = exam.questions.count()
        q.save()
        _process_question_dependencies(q, question_type, post_data)
        return q

    @staticmethod
    @transaction.atomic
    def update_question(instance, question_type, post_data):
        stmt, expl = validate_question_payload(question_type, post_data)
        instance.statement = stmt
        instance.explanation = expl
        instance.save()
        _update_polymorphic_instance(instance, question_type, post_data)
        return instance
