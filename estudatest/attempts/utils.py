# utils.py
import random


LIST_ANSWER_TYPES = {'multi_answer', 'ordering', 'matching', 'multiple_choice'}


def _get_shuffled_data(request, attempt_id, question):
    """Retorna (e cacheia na sessão) os dados embaralhados de ordering/matching."""
    shuffle_key = f'shuffle_{attempt_id}_{question.id}'
    shuffled = request.session.get(shuffle_key)
    if shuffled is not None:
        return shuffled

    if question.question_type == 'ordering':
        indexed = [(item.id, item.text) for item in question.items.all()]
        random.shuffle(indexed)
        shuffled = {'indexed': indexed}
    elif question.question_type == 'matching':
        rights = [pair.right for pair in question.pairs.all()]
        random.shuffle(rights)
        shuffled = {'rights': rights}
    else:
        shuffled = {}

    request.session[shuffle_key] = shuffled
    request.session.modified = True
    return shuffled


def _get_given_answer(request, question_type):
    """Extrai a resposta enviada no formato esperado por check_answer."""
    if question_type in LIST_ANSWER_TYPES:
        return request.POST.getlist('answer')
    return request.POST.get('answer', '')


def _compute_navigation(n, total):
    """Retorna (is_last, next_n) considerando todas as questões da prova,
    flashcards inclusive — a ordem de exibição segue estritamente a
    sequência 1..total definida em `exam.questions.order_by('order')`."""
    is_last = (n == total)
    next_n = n + 1 if not is_last else None
    return is_last, next_n