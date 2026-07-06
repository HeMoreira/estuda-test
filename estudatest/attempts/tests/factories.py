"""
Helpers para montar rapidamente Exams e Questions (de todos os tipos)
dentro dos testes do app `attempts`.

Não dependem de nenhum detalhe do app `categories` — a categoria é
sempre deixada como None, já que o campo é opcional em Exam.
"""
from django.contrib.auth.models import User

from exams.models import (
    Exam,
    QuestionOption,
    MultipleChoiceQuestion,
    MultiAnswerQuestion,
    TrueFalseQuestion,
    WrittenQuestion,
    OrderingQuestion,
    OrderingItem,
    MatchingQuestion,
    MatchingPair,
    FlashcardQuestion,
)


def make_user(username='user1', password='senha-forte-123'):
    return User.objects.create_user(username=username, password=password)


def make_exam(user, name='Prova Teste', order_start=1):
    return Exam.objects.create(user=user, name=name)


def add_multiple_choice(exam, order=1, statement='Qual a capital da França?',
                         explanation='Paris é a capital da França.'):
    q = MultipleChoiceQuestion.objects.create(
        exam=exam, order=order, statement=statement, explanation=explanation,
    )
    correct = QuestionOption.objects.create(question=q, text='Paris', is_correct=True, order=1)
    QuestionOption.objects.create(question=q, text='Londres', is_correct=False, order=2)
    QuestionOption.objects.create(question=q, text='Berlim', is_correct=False, order=3)
    return q, correct


def add_multi_answer(exam, order=1, statement='Quais são números primos?',
                      explanation='2 e 3 são primos; 4 não é.'):
    q = MultiAnswerQuestion.objects.create(
        exam=exam, order=order, statement=statement, explanation=explanation,
    )
    opt2 = QuestionOption.objects.create(question=q, text='2', is_correct=True, order=1)
    opt3 = QuestionOption.objects.create(question=q, text='3', is_correct=True, order=2)
    QuestionOption.objects.create(question=q, text='4', is_correct=False, order=3)
    return q, [opt2, opt3]


def add_true_false(exam, order=1, correct_answer=True,
                    statement='O sol é uma estrela?',
                    explanation='Sim, o sol é uma estrela do tipo anã amarela.'):
    q = TrueFalseQuestion.objects.create(
        exam=exam, order=order, statement=statement, explanation=explanation,
        correct_answer=correct_answer,
    )
    return q


def add_written(exam, order=1, expected_answer='python',
                 accepted_alternatives=None, case_sensitive=False,
                 statement='Qual linguagem tem uma cobra como mascote?',
                 explanation='Python.'):
    q = WrittenQuestion.objects.create(
        exam=exam, order=order, statement=statement, explanation=explanation,
        expected_answer=expected_answer,
        case_sensitive=case_sensitive,
        accepted_alternatives=accepted_alternatives or [],
    )
    return q


def add_ordering(exam, order=1,
                  statement='Ordene do menor para o maior:',
                  explanation='1, 2, 3 em ordem crescente.'):
    q = OrderingQuestion.objects.create(
        exam=exam, order=order, statement=statement, explanation=explanation,
    )
    i1 = OrderingItem.objects.create(question=q, text='Um', position=1)
    i2 = OrderingItem.objects.create(question=q, text='Dois', position=2)
    i3 = OrderingItem.objects.create(question=q, text='Três', position=3)
    return q, [i1, i2, i3]


def add_matching(exam, order=1,
                  statement='Relacione o país à capital:',
                  explanation='Brasil-Brasília, França-Paris.'):
    q = MatchingQuestion.objects.create(
        exam=exam, order=order, statement=statement, explanation=explanation,
    )
    p1 = MatchingPair.objects.create(question=q, left='Brasil', right='Brasília', order=1)
    p2 = MatchingPair.objects.create(question=q, left='França', right='Paris', order=2)
    return q, [p1, p2]


def add_flashcard(exam, order=1, front='2 + 2', back='4',
                   statement='Resolva mentalmente:',
                   explanation='Aritmética básica.'):
    q = FlashcardQuestion.objects.create(
        exam=exam, order=order, statement=statement, explanation=explanation,
        front=front, back=back,
    )
    return q