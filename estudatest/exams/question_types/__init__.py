from ..models import Question
from .choice import MultipleChoiceHandler, MultiAnswerHandler
from .true_false import TrueFalseHandler
from .written import WrittenHandler
from .ordering import OrderingHandler
from .matching import MatchingHandler
from .flashcard import FlashcardHandler

QUESTION_TYPE_HANDLERS = {
    Question.Types.MULTIPLE_CHOICE: MultipleChoiceHandler(),
    Question.Types.MULTI_ANSWER: MultiAnswerHandler(),
    Question.Types.TRUE_FALSE: TrueFalseHandler(),
    Question.Types.WRITTEN: WrittenHandler(),
    Question.Types.ORDERING: OrderingHandler(),
    Question.Types.MATCHING: MatchingHandler(),
    Question.Types.FLASHCARD: FlashcardHandler(),
}


def get_handler(question_type):
    handler = QUESTION_TYPE_HANDLERS.get(question_type)
    if handler is None:
        raise ValueError(f'Tipo de questão desconhecido: {question_type}')
    return handler


def is_registered_type(question_type):
    return question_type in QUESTION_TYPE_HANDLERS