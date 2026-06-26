"""
Validates and normalises question data JSONField per question type.
Also provides answer-checking logic.
"""
import unicodedata
import re


def validate_question_data(question_type, data):
    """Returns (cleaned_data, errors_list). `data` is a dict from POST."""
    errors = []

    if question_type == 'multiple_choice':
        options = data.get('options', [])
        if isinstance(options, str):
            options = [options]
        correct = data.get('correct', '')
        options = [o.strip() for o in options if str(o).strip()]
        if len(options) < 2:
            errors.append('Múltipla escolha requer ao menos 2 alternativas.')
        if len(options) > 5:
            errors.append('Múltipla escolha permite no máximo 5 alternativas.')
        try:
            correct_idx = int(correct)
            if not (0 <= correct_idx < len(options)):
                raise ValueError
        except (ValueError, TypeError):
            errors.append('Selecione a alternativa correta.')
            correct_idx = 0
        return {'options': options, 'correct': correct_idx}, errors

    elif question_type == 'multi_answer':
        options = data.get('options', [])
        if isinstance(options, str):
            options = [options]
        correct = data.get('correct', [])
        if isinstance(correct, str):
            correct = [correct]
        options = [o.strip() for o in options if str(o).strip()]
        if len(options) < 2:
            errors.append('Resposta múltipla requer ao menos 2 opções.')
        if len(options) > 8:
            errors.append('Resposta múltipla permite no máximo 8 opções.')
        try:
            correct_idxs = [int(c) for c in correct if 0 <= int(c) < len(options)]
        except (ValueError, TypeError):
            correct_idxs = []
        if not correct_idxs:
            errors.append('Selecione ao menos uma resposta correta.')
        return {'options': options, 'correct': correct_idxs}, errors

    elif question_type == 'true_false':
        correct = data.get('correct', '')
        if str(correct).lower() not in ['true', 'false']:
            errors.append('Selecione Verdadeiro ou Falso como resposta.')
        val = str(correct).lower() == 'true'
        return {'correct': val}, errors

    elif question_type == 'written':
        answer = str(data.get('answer', '')).strip()
        if not answer:
            errors.append('Informe a resposta esperada.')
        return {'answer': answer}, errors

    elif question_type == 'ordering':
        items = data.get('items', [])
        if isinstance(items, str):
            items = [items]
        items = [i.strip() for i in items if str(i).strip()]
        if len(items) < 2:
            errors.append('Ordenar elementos requer ao menos 2 itens.')
        if len(items) > 8:
            errors.append('Ordenar elementos permite no máximo 8 itens.')
        return {'items': items}, errors

    elif question_type == 'matching':
        lefts  = data.get('pairs_left', [])
        rights = data.get('pairs_right', [])
        if isinstance(lefts, str):
            lefts = [lefts]
        if isinstance(rights, str):
            rights = [rights]
        pairs = [
            {'left': l.strip(), 'right': r.strip()}
            for l, r in zip(lefts, rights)
            if l.strip() and r.strip()
        ]
        if len(pairs) < 2:
            errors.append('Relacionar colunas requer ao menos 2 pares.')
        if len(pairs) > 10:
            errors.append('Relacionar colunas permite no máximo 10 pares.')
        return {'pairs': pairs}, errors

    elif question_type == 'flashcard':
        front = str(data.get('front', '')).strip()
        back  = str(data.get('back',  '')).strip()
        if not front:
            errors.append('Informe a frente do flashcard.')
        if not back:
            errors.append('Informe o verso do flashcard.')
        return {'front': front, 'back': back}, errors

    errors.append('Tipo de questão inválido.')
    return data, errors


def normalize_written(text):
    text = str(text).lower().strip()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def check_answer(question, given_answer):
    qt   = question.question_type
    data = question.data

    if qt == 'multiple_choice':
        try:
            return int(given_answer) == int(data['correct'])
        except (ValueError, TypeError, KeyError):
            return False

    elif qt == 'multi_answer':
        try:
            given   = sorted(int(x) for x in (given_answer if isinstance(given_answer, list) else [given_answer]))
            correct = sorted(int(x) for x in data.get('correct', []))
            return given == correct
        except (ValueError, TypeError):
            return False

    elif qt == 'true_false':
        given = str(given_answer).lower() in ['true', '1', 'verdadeiro']
        return given == data.get('correct', False)

    elif qt == 'written':
        return normalize_written(given_answer) == normalize_written(data.get('answer', ''))

    elif qt == 'ordering':
        try:
            items   = data.get('items', [])
            given   = [str(x) for x in (given_answer if isinstance(given_answer, list) else [given_answer])]
            correct = [str(i) for i in range(len(items))]
            return given == correct
        except (TypeError, KeyError):
            return False

    elif qt == 'matching':
        try:
            pairs = data.get('pairs', [])
            given = given_answer if isinstance(given_answer, list) else [given_answer]
            return all(given[i] == pairs[i]['right'] for i in range(len(pairs)))
        except (IndexError, TypeError, KeyError):
            return False

    elif qt == 'flashcard':
        return str(given_answer).lower() in ['true', '1', 'correct', 'correto']

    return False
