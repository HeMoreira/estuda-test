from django.contrib import admin
from django.forms import BaseInlineFormSet
from django.core.exceptions import ValidationError
from polymorphic.admin import PolymorphicChildModelAdmin, PolymorphicParentModelAdmin, PolymorphicChildModelFilter
from .models import (
    Exam, Question, MultipleChoiceQuestion, MultiAnswerQuestion,
    TrueFalseQuestion, WrittenQuestion, OrderingQuestion,
    MatchingQuestion, FlashcardQuestion, QuestionOption,
    OrderingItem, MatchingPair
)

# ==========================================
# 1. VALIDADORES DE FORMULÁRIO (SEGURANÇA)
# ==========================================

class ChoiceQuestionInlineFormSet(BaseInlineFormSet):
    """Garante que as regras de alternativas sejam cumpridas antes de salvar."""
    def clean(self):
        super().clean()
        if any(self.errors):
            return  # Não valida se já houver erros individuais nos forms

        correct_count = 0
        total_options = 0

        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                total_options += 1
                if form.cleaned_data.get('is_correct', False):
                    correct_count += 1

        # Identifica o tipo de questão através do formulário pai
        model_instance = self.instance

        if total_options == 0:
            raise ValidationError("A questão precisa ter pelo menos uma alternativa cadastrada.")

        if isinstance(model_instance, MultipleChoiceQuestion):
            if correct_count > 1:
                raise ValidationError("Uma questão de Múltipla Escolha só pode ter UMA alternativa correta.")
            if correct_count < 1:
                raise ValidationError("Uma questão de Múltipla Escolha precisa ter exatamente UMA alternativa correta.")

        elif isinstance(model_instance, MultiAnswerQuestion):
            if correct_count < 1:
                raise ValidationError("Uma questão de Resposta Múltipla precisa ter pelo menos UMA alternativa correta.")


# ==========================================
# 2. INLINES (GERENCIAMENTO NA MESMA TELA)
# ==========================================

class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    formset = ChoiceQuestionInlineFormSet
    extra = 4
    min_num = 1


class OrderingItemInline(admin.TabularInline):
    model = OrderingItem
    extra = 3
    min_num = 2  # Ordenar precisa de pelo menos 2 itens


class MatchingPairInline(admin.TabularInline):
    model = MatchingPair
    extra = 3
    min_num = 1

# ==========================================
# 3. ADMIN DOS MODELOS FILHOS (POLIMÓRFICOS)
# ==========================================

class ChildQuestionAdmin(PolymorphicChildModelAdmin):
    """Classe base para todas as subquestões."""
    base_model = Question
    list_display = ['statement_preview', 'exam', 'order']
    search_fields = ['statement', 'explanation']


@admin.register(MultipleChoiceQuestion)
class MultipleChoiceQuestionAdmin(ChildQuestionAdmin):
    base_model = MultipleChoiceQuestion
    inlines = [QuestionOptionInline]


@admin.register(MultiAnswerQuestion)
class MultiAnswerQuestionAdmin(ChildQuestionAdmin):
    base_model = MultiAnswerQuestion
    inlines = [QuestionOptionInline]


@admin.register(TrueFalseQuestion)
class TrueFalseQuestionAdmin(ChildQuestionAdmin):
    base_model = TrueFalseQuestion
    fields = ['exam', 'order', 'statement', 'explanation', 'correct_answer']


@admin.register(WrittenQuestion)
class WrittenQuestionAdmin(ChildQuestionAdmin):
    base_model = WrittenQuestion
    fields = ['exam', 'order', 'statement', 'explanation', 'expected_answer', 'case_sensitive', 'accepted_alternatives']


@admin.register(OrderingQuestion)
class OrderingQuestionAdmin(ChildQuestionAdmin):
    base_model = OrderingQuestion
    inlines = [OrderingItemInline]


@admin.register(MatchingQuestion)
class MatchingQuestionAdmin(ChildQuestionAdmin):
    base_model = MatchingQuestion
    inlines = [MatchingPairInline]


@admin.register(FlashcardQuestion)
class FlashcardQuestionAdmin(ChildQuestionAdmin):
    base_model = FlashcardQuestion
    fields = ['exam', 'order', 'statement', 'explanation', 'front', 'back']


# ==========================================
# 4. ADMIN DO MODELO PAI (VISÃO GERAL)
# ==========================================

@admin.register(Question)
class QuestionParentAdmin(PolymorphicParentModelAdmin):
    base_model = Question
    child_models = (
        MultipleChoiceQuestion, MultiAnswerQuestion, TrueFalseQuestion,
        WrittenQuestion, OrderingQuestion, MatchingQuestion, FlashcardQuestion
    )
    list_display = ['statement_preview', 'exam', 'question_type_display', 'order']
    list_filter = ['exam', PolymorphicChildModelFilter]
    search_fields = ['statement']

    # 1. REMOVE O BOTÃO DE ADICIONAR DESTA TELA
    def has_add_permission(self, request):
        return False

    def question_type_display(self, obj):
        return obj.get_question_type_display()
    question_type_display.short_description = 'Tipo de Questão'

# ==========================================
# 5. ADMIN DO EXAME
# ==========================================

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'user', 'question_count', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['name', 'user__username', 'category__name']
    readonly_fields = ['created_at', 'updated_at']
    
    # Define o comportamento de preenchimento automático do usuário logado por segurança
    def save_model(self, request, obj, form, change):
        if not change: # Se estiver criando um novo exame
            obj.user = request.user
        super().save_model(request, request, obj, form, change)