from django.core.exceptions import ValidationError
from ..models import QuestionOption, MultipleChoiceQuestion, MultiAnswerQuestion, Question
from .base import BaseQuestionTypeHandler
from .option_utils import normalize_options, raw_options, MAX_OPTION_LENGTH


class ChoiceQuestionHandler(BaseQuestionTypeHandler):
    """Base compartilhada por múltipla escolha e resposta múltipla."""
    model_class = None
    multiple_correct = False

    # ── Validação ──
    def validate(self, post_data, errors):
        options = normalize_options(post_data)
        if len(options) < 2:
            errors.append('A questão precisa conter pelo menos 2 alternativas válidas e preenchidas.')
        if any(len(opt) > MAX_OPTION_LENGTH for opt in options):
            errors.append(f'As alternativas podem ter no máximo {MAX_OPTION_LENGTH} caracteres.')
        self._validate_correct_selection(post_data, errors)

    def _validate_correct_selection(self, post_data, errors):
        if self.multiple_correct:
            if not post_data.getlist('data_correct'):
                errors.append('Marque pelo menos uma resposta como correta.')
        elif not post_data.get('data_correct'):
            errors.append('É necessário marcar qual alternativa é a correta.')

    # ── Criação ──
    def build_instance(self, statement, explanation, post_data):
        return self.model_class(statement=statement, explanation=explanation)

    def _is_correct(self, index, post_data):
        if self.multiple_correct:
            return str(index) in set(post_data.getlist('data_correct'))
        return str(index) == str(post_data.get('data_correct'))

    def save_dependencies(self, question, post_data):
        options = normalize_options(post_data)
        for index, text in enumerate(options):
            QuestionOption.objects.create(
                question=question, text=text, order=index,
                is_correct=self._is_correct(index, post_data),
            )

    # ── Edição ──
    def update_dependencies(self, question, post_data):
        options = normalize_options(post_data)
        if len(options) < 2:
            raise ValidationError('A atualização deve conter no mínimo 2 alternativas preenchidas.')
        existing = list(question.options.order_by('order'))
        self._sync_options(question, existing, options, post_data)

    def _sync_options(self, question, existing, options, post_data):
        for index, text in enumerate(options):
            is_correct = self._is_correct(index, post_data)
            if index < len(existing):
                option = existing[index]
                option.text, option.is_correct, option.order = text, is_correct, index
                option.save()
            else:
                QuestionOption.objects.create(question=question, text=text, is_correct=is_correct, order=index)
        for extra in existing[len(options):]:
            extra.delete()

    # ── Serialização a partir do banco ──
    def build_edit_json(self, question):
        options = list(question.options.order_by('order'))
        data = {'options': [o.text for o in options]}
        if self.multiple_correct:
            data['correct'] = [i for i, o in enumerate(options) if o.is_correct]
        else:
            data['correct'] = next((i for i, o in enumerate(options) if o.is_correct), None)
        return data

    # ── Serialização a partir de um POST inválido ──
    def build_preview_json(self, post_data):
        options = raw_options(post_data)
        data = {'options': options}
        if self.multiple_correct:
            correct_set = set(post_data.getlist('data_correct'))
            data['correct'] = [i for i in range(len(options)) if str(i) in correct_set]
        else:
            raw_correct = post_data.get('data_correct')
            data['correct'] = int(raw_correct) if raw_correct and raw_correct.isdigit() else None
        return data


class MultipleChoiceHandler(ChoiceQuestionHandler):
    type_value = Question.Types.MULTIPLE_CHOICE
    model_class = MultipleChoiceQuestion
    multiple_correct = False


class MultiAnswerHandler(ChoiceQuestionHandler):
    type_value = Question.Types.MULTI_ANSWER
    model_class = MultiAnswerQuestion
    multiple_correct = True