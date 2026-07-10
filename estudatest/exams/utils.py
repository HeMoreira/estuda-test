from django.core.exceptions import ValidationError
from categories.models import Category
from .question_types import get_handler, is_registered_type

MAX_STATEMENT_LENGTH = 1000


# ── Categoria padrão ──
def _get_or_create_default_category(request):
    category, _ = Category.objects.get_or_create(user=request.user, name='~ sem categoria')
    return category


def save_exam_with_default_category_if_needed(request, form):
    exam = form.save(commit=False)
    exam.user = request.user
    if not exam.category:
        exam.category = _get_or_create_default_category(request)
    exam.save()
    return exam


# ── Validação de payload de questão ──
def _normalize_text(value):
    return (value or '').strip()


def _validate_common_fields(statement, explanation, errors):
    if not statement or not explanation:
        errors.append('O enunciado e a explicação da questão não podem ficar vazios.')
    if len(statement) > MAX_STATEMENT_LENGTH or len(explanation) > MAX_STATEMENT_LENGTH:
        errors.append(f'O enunciado e a explicação podem ter no máximo {MAX_STATEMENT_LENGTH} caracteres.')


def validate_question_payload(question_type, post_data):
    errors = []
    statement = _normalize_text(post_data.get('statement'))
    explanation = _normalize_text(post_data.get('explanation'))

    _validate_common_fields(statement, explanation, errors)

    if not is_registered_type(question_type):
        errors.append('Tipo de questão inválido.')
    else:
        get_handler(question_type).validate(post_data, errors)

    if errors:
        raise ValidationError(errors)
    return statement, explanation


# ── Serialização para o editor ──
def build_question_edit_data(instance, question_type):
    """Dados vindos do banco, para popular o editor ao abrir uma questão existente."""
    return get_handler(question_type).build_edit_json(instance)


def build_question_preview_data(question_type, post_data):
    """Dados vindos de um POST (possivelmente inválido), para repopular o
    editor sem perder o que o usuário digitou. Usado tanto em adição quanto
    em edição quando a validação falha."""
    if not is_registered_type(question_type):
        return {}
    return get_handler(question_type).build_preview_json(post_data)


# ── Achatamento de erros de validação ──
def flatten_validation_errors(exc):
    if not isinstance(exc, ValidationError):
        return [str(exc)]

    if hasattr(exc, 'error_dict') and exc.error_dict:
        messages = []
        for field, field_errors in exc.error_dict.items():
            for item in field_errors:
                if isinstance(item, ValidationError):
                    messages.extend(flatten_validation_errors(item))
                else:
                    messages.append(f'{field}: {item}')
        return messages

    return [message for message in exc.messages if message]