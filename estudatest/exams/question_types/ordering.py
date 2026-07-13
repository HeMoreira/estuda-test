from django.core.exceptions import ValidationError
from ..models import OrderingQuestion, OrderingItem, Question
from .base import BaseQuestionTypeHandler

MAX_ITEM_LENGTH = 500
MIN_ITEMS = 2
MAX_ITEMS = 8


def _clean_items(post_data):
    return [text.strip() for text in post_data.getlist('data_items') if text.strip()]


class OrderingHandler(BaseQuestionTypeHandler):
    type_value = Question.Types.ORDERING

    def validate(self, post_data, errors):
        items = _clean_items(post_data)
        if len(items) < MIN_ITEMS:
            errors.append(f'Forneça pelo menos {MIN_ITEMS} elementos ordenáveis preenchidos.')
        if len(items) > MAX_ITEMS:
            errors.append(f'Forneça no máximo {MAX_ITEMS} elementos ordenáveis preenchidos.')
        if any(len(item) > MAX_ITEM_LENGTH for item in items):
            errors.append(f'Os elementos podem ter no máximo {MAX_ITEM_LENGTH} caracteres.')

    def build_instance(self, statement, explanation, post_data):
        return OrderingQuestion(statement=statement, explanation=explanation)

    def save_dependencies(self, question, post_data):
        items = _clean_items(post_data)
        if len(items) < MIN_ITEMS:
            raise ValidationError(f'Forneça pelo menos {MIN_ITEMS} elementos ordenáveis preenchidos.')
        OrderingItem.objects.bulk_create([
            OrderingItem(question=question, text=text, position=position)
            for position, text in enumerate(items, start=1)
        ])

    def update_dependencies(self, question, post_data):
        OrderingItem.objects.filter(question=question).delete()
        self.save_dependencies(question, post_data)

    def build_edit_json(self, question):
        items = OrderingItem.objects.filter(question=question).order_by('position')
        return {'items': [item.text for item in items]}

    def build_preview_json(self, post_data):
        return {'items': post_data.getlist('data_items')}