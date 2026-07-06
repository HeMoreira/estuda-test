from django.core.exceptions import ValidationError
from categories.models import Category
from .models import QuestionOption
from .models import Question, MultipleChoiceQuestion, MultiAnswerQuestion, TrueFalseQuestion, WrittenQuestion, OrderingQuestion, MatchingQuestion, FlashcardQuestion, MatchingPair, OrderingItem

def _get_or_create_default_category(request):
    category, _ = Category.objects.get_or_create(
        user=request.user, 
        name='~ sem categoria'
    )
    return category

def save_exam_with_default_category_if_needed(request, form):
    exam = form.save(commit=False)
    exam.user = request.user
    if not exam.category:
        exam.category = _get_or_create_default_category(request)
    exam.save()
    return exam

def _normalize_text(value):
    return (value or '').strip()

def _normalize_option_values(post_data):
    opts = [t.strip() for t in post_data.getlist('data_options') if t.strip() != '']
    if len(opts) > 10:
        raise ValidationError('A questão pode ter no máximo 10 alternativas.')
    return opts

def _validate_specific_question_types(q_type, post_data, errors):
    if q_type in (Question.Types.MULTIPLE_CHOICE, Question.Types.MULTI_ANSWER):
        opts = _normalize_option_values(post_data)
        if len(opts) < 2:
            errors.append('A questão precisa conter pelo menos 2 alternativas válidas e preenchidas.')

        if q_type == Question.Types.MULTIPLE_CHOICE:
            correct_index = post_data.get('data_correct')
            if correct_index is None or correct_index == '':
                errors.append('É necessário marcar qual alternativa é a correta.')
        else:
            if not post_data.getlist('data_correct'):
                errors.append('Marque pelo menos uma resposta como correta.')

        for opt in opts:
            if len(opt) > 500:
                errors.append('As alternativas podem ter no máximo 500 caracteres.')
                break

    elif q_type == Question.Types.TRUE_FALSE:
        val = post_data.get('data_correct')
        if val not in ('true', 'false', '1', '0', 'verdadeiro', 'falso'):
            errors.append('Selecione verdadeiro ou falso.')

    elif q_type == Question.Types.WRITTEN:
        ans = _normalize_text(post_data.get('data_answer'))
        if not ans:
            errors.append('A resposta escrita esperada não pode ficar vazia.')

        if len(ans) > 255:
            errors.append('A resposta escrita pode ter no máximo 255 caracteres.')

    elif q_type == Question.Types.ORDERING:
        items = [t.strip() for t in post_data.getlist('data_items') if t.strip() != '']
        if len(items) < 2:
            errors.append('Forneça pelo menos 2 elementos ordenáveis preenchidos.')

        for _, text in enumerate(items, start=1):
            if len(text) > 500:
                errors.append('Os elementos podem ter no máximo 500 caracteres.')
                break

    elif q_type == Question.Types.MATCHING:
        lefts = [l.strip() for l in post_data.getlist('data_pairs_left') if l.strip() != '']
        rights = [r.strip() for r in post_data.getlist('data_pairs_right') if r.strip() != '']
        if len(lefts) < 2 or len(lefts) != len(rights):
            errors.append('Garanta que todas as linhas de colunas (A e B) estejam preenchidas.')

        for _, (l, r) in enumerate(zip(lefts, rights), start=1):
            if len(l) > 500 or len(r) > 500:
                errors.append('Os elementos podem ter no máximo 500 caracteres.')
                break

    elif q_type == Question.Types.FLASHCARD:
        front = _normalize_text(post_data.get('data_front'))
        back = _normalize_text(post_data.get('data_back'))
        if not front or not back:
            errors.append('Texto de frente e verso são obrigatórios para o Flashcard.')

        if len(front) > 1000 or len(back) > 1000:
            errors.append('O texto de frente e verso podem ter no máximo 1000 caracteres.')
    return errors

def validate_question_payload(q_type, post_data):
    errors = []
    statement = _normalize_text(post_data.get('statement'))
    explanation = _normalize_text(post_data.get('explanation'))

    if not statement or not explanation:
        errors.append('O enunciado e a explicação da questão não podem ficar vazios.')
        # raise ValidationError({'empty_fields': 'O enunciado e a explicação da questão não podem ficar vazios.'})

    if len(statement) > 1000 or len(explanation) > 1000:
        errors.append('O enunciado e a explicação da questão podem ter no máximo 1000 caracteres.')
        # raise ValidationError({'too_long_fields': 'O enunciado e a explicação da questão podem ter no máximo 1000 caracteres.'})

    errors = _validate_specific_question_types(q_type, post_data, errors)

    if errors:
        raise ValidationError(errors)
    return statement, explanation

def _create_polymorphic_instance(q_type, stmt, expl, post_data):
    """Instancia os objetos corretos de acordo com suas subclasses polimórficas."""
    stmt = _normalize_text(stmt)
    expl = _normalize_text(expl)
    if q_type == Question.Types.MULTIPLE_CHOICE:
        return MultipleChoiceQuestion(statement=stmt, explanation=expl)
    elif q_type == Question.Types.MULTI_ANSWER:
        return MultiAnswerQuestion(statement=stmt, explanation=expl)
    elif q_type == Question.Types.TRUE_FALSE:
        val = post_data.get('data_correct', 'false')
        return TrueFalseQuestion(statement=stmt, explanation=expl, correct_answer=(val in ('true', '1', 'verdadeiro')))
    elif q_type == Question.Types.WRITTEN:
        ans = post_data.get('data_answer', '').strip()
        return WrittenQuestion(statement=stmt, explanation=expl, expected_answer=ans)
    elif q_type == Question.Types.ORDERING:
        return OrderingQuestion(statement=stmt, explanation=expl)
    elif q_type == Question.Types.MATCHING:
        return MatchingQuestion(statement=stmt, explanation=expl)
    elif q_type == Question.Types.FLASHCARD:
        front = post_data.get('data_front', '').strip()
        back = post_data.get('data_back', '').strip()
        return FlashcardQuestion(statement=stmt, explanation=expl, front=front, back=back)
    return None

def _process_question_dependencies(q, q_type, post_data):
    """Gera e acopla dependências estruturais limpando strings vazias e aplicando validação de segurança."""
    if q_type in (Question.Types.MULTIPLE_CHOICE, Question.Types.MULTI_ANSWER):
        opts = _normalize_option_values(post_data)

        if q_type == Question.Types.MULTIPLE_CHOICE:
            correct_index = post_data.get('data_correct')
            for i, text in enumerate(opts):
                QuestionOption.objects.create(question=q, text=text, is_correct=(str(i) == str(correct_index)), order=i)
        else:
            correct_set = set(post_data.getlist('data_correct'))
            for i, text in enumerate(opts):
                QuestionOption.objects.create(question=q, text=text, is_correct=(str(i) in correct_set), order=i)

    elif q_type == Question.Types.ORDERING:
        items = [t.strip() for t in post_data.getlist('data_items') if t.strip() != ""]
        if len(items) < 2:
            raise ValidationError("Forneça pelo menos 2 elementos ordenáveis preenchidos.")
            
        for pos, text in enumerate(items, start=1):
            OrderingItem.objects.create(question=q, text=text, position=pos)

    elif q_type == Question.Types.MATCHING:
        lefts = [l.strip() for l in post_data.getlist('data_pairs_left') if l.strip() != ""]
        rights = [r.strip() for r in post_data.getlist('data_pairs_right') if r.strip() != ""]
        
        if len(lefts) < 2 or len(lefts) != len(rights):
            raise ValidationError("Garanta que todas as linhas de colunas (A e B) estejam preenchidas.")
            
        for i, (l, r) in enumerate(zip(lefts, rights)):
            MatchingPair.objects.create(question=q, left=l, right=r, order=i)

def _update_polymorphic_instance(instance, q_type, post_data):
    """Atualiza de forma atômica e limpa os campos internos e registros dependentes."""
    if q_type in (Question.Types.MULTIPLE_CHOICE, Question.Types.MULTI_ANSWER):
        opts = _normalize_option_values(post_data)
        if len(opts) < 2:
            raise ValidationError("A atualização deve conter no mínimo 2 alternativas preenchidas.")

        correct_index = post_data.get('data_correct') if q_type == Question.Types.MULTIPLE_CHOICE else None
        correct_set = set(post_data.getlist('data_correct')) if q_type == Question.Types.MULTI_ANSWER else None
        
        if q_type == Question.Types.MULTIPLE_CHOICE and correct_index is None:
            raise ValidationError("Selecione uma alternativa válida.")
        if q_type == Question.Types.MULTI_ANSWER and not correct_set:
            raise ValidationError("Selecione ao menos uma alternativa válida.")

        existing = list(instance.options.order_by('order'))
        for i, text in enumerate(opts):
            is_correct = (str(i) == str(correct_index)) if q_type == Question.Types.MULTIPLE_CHOICE else (str(i) in correct_set)

            if i < len(existing):
                opt = existing[i]
                opt.text = text
                opt.is_correct = is_correct
                opt.order = i
                opt.save()
            else:
                QuestionOption.objects.create(question=instance, text=text, is_correct=is_correct, order=i)

        if len(existing) > len(opts):
            for extra in existing[len(opts):]:
                extra.delete()

    elif q_type == Question.Types.TRUE_FALSE:
        val = post_data.get('data_correct')
        if val not in ('true', 'false', '1', '0', 'verdadeiro'):
            raise ValidationError("Valor inválido enviado para a resposta de Verdadeiro ou Falso.")
        instance.truefalsequestion.correct_answer = (val in ('true', '1', 'verdadeiro'))
        instance.truefalsequestion.save()

    elif q_type == Question.Types.WRITTEN:
        ans = post_data.get('data_answer', '').strip()
        if not ans:
            raise ValidationError("A resposta escrita esperada não pode ficar vazia.")
        instance.writtenquestion.expected_answer = ans
        instance.writtenquestion.save()

    elif q_type == Question.Types.ORDERING:
        items = [t.strip() for t in post_data.getlist('data_items') if t.strip() != ""]
        if len(items) < 2:
            raise ValidationError("Adicione pelo menos 2 elementos à ordenação.")
            
        OrderingItem.objects.filter(question=instance).delete()
        for pos, text in enumerate(items, start=1):
            OrderingItem.objects.create(question=instance, text=text, position=pos)

    elif q_type == Question.Types.MATCHING:
        lefts = [l.strip() for l in post_data.getlist('data_pairs_left') if l.strip() != ""]
        rights = [r.strip() for r in post_data.getlist('data_pairs_right') if r.strip() != ""]
        if len(lefts) < 2 or len(lefts) != len(rights):
            raise ValidationError("Preencha todas as relações correspondentes.")

        MatchingPair.objects.filter(question=instance).delete()
        for i, (l, r) in enumerate(zip(lefts, rights)):
            MatchingPair.objects.create(question=instance, left=l, right=r, order=i)

    elif q_type == Question.Types.FLASHCARD:
        front = post_data.get('data_front', '').strip()
        back = post_data.get('data_back', '').strip()
        if not front or not back:
            raise ValidationError("Texto de frente e verso são obrigatórios para o Flashcard.")
            
        instance.flashcardquestion.front = front
        instance.flashcardquestion.back = back
        instance.flashcardquestion.save()

def _build_question_json_data(instance, q_type):
    """Mapeia os dados salvos em dicionários nativos para o script renderizar em tela."""
    if q_type == 'multiple_choice':
        opts = list(instance.options.order_by('order'))
        return {
            'options': [o.text for o in opts],
            'correct': next((i for i, o in enumerate(opts) if o.is_correct), None),
        }
    elif q_type == 'multi_answer':
        opts = list(instance.options.order_by('order'))
        return {
            'options': [o.text for o in opts],
            'correct': [i for i, o in enumerate(opts) if o.is_correct],
        }
    elif q_type == 'true_false':
        return {'correct': bool(getattr(instance.truefalsequestion, 'correct_answer', False))}
    elif q_type == 'written':
        return {'answer': getattr(instance.writtenquestion, 'expected_answer', '')}
    elif q_type == 'ordering':
        return {'items': [it.text for it in instance.orderingquestion.items.order_by('position')]}
    elif q_type == 'matching':
        return {'pairs': [{'left': p.left, 'right': p.right} for p in instance.matchingquestion.pairs.order_by('order')]}
    elif q_type == 'flashcard':
        return {
            'front': getattr(instance.flashcardquestion, 'front', ''),
            'back': getattr(instance.flashcardquestion, 'back', '')
        }
    return {}

def _flatten_validation_errors(exc):
    if not isinstance(exc, ValidationError):
        return [str(exc)]

    messages = []
    if hasattr(exc, 'error_dict') and exc.error_dict:
        for field, field_errors in exc.error_dict.items():
            for item in field_errors:
                if isinstance(item, ValidationError):
                    messages.extend(_flatten_validation_errors(item))
                else:
                    messages.append(f"{field}: {item}")
        return messages

    return [message for message in exc.messages if message]
