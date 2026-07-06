from django.contrib import admin
from django.utils.html import format_html
from .models import Attempt, AnswerRecord

class AnswerRecordInline(admin.TabularInline):
    model = AnswerRecord
    extra = 0
    readonly_fields = ['question', 'readable_given_answer', 'is_correct']
    fields = ['question', 'readable_given_answer', 'is_correct']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def readable_given_answer(self, obj):
        """Formata o JSON da resposta para exibição amigável."""
        if obj.given_answer is None:
            return "-"
        if isinstance(obj.given_answer, list):
            return ", ".join(str(x) for x in obj.given_answer)
        if isinstance(obj.given_answer, dict):
            return ", ".join(f"{k}: {v}" for k, v in obj.given_answer.items())
        return str(obj.given_answer)
    
    readable_given_answer.short_description = 'Resposta Dada'


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'exam', 'score_display', 'duration_display', 'started_at', 'is_finished']
    list_filter = ['exam', 'started_at', ('finished_at', admin.EmptyFieldListFilter)]
    search_fields = ['user__username', 'exam__name']
    
    readonly_fields = ['user', 'exam', 'started_at', 'finished_at', 'duration', 'score']
    
    inlines = [AnswerRecordInline]

    def score_display(self, obj):
        """Exibe a nota em formato de porcentagem colorida no painel."""
        percent = obj.score_percent()
        if percent is None:
            return format_html('<span style="color: gray;">Em andamento</span>')
        
        color = "green" if percent >= 70 else "red"
        return format_html('<strong style="color: {};">{}%</strong>', color, percent)
    
    score_display.short_description = 'Nota (%)'
    score_display.admin_order_field = 'score'

    def duration_display(self, obj):
        """Formata a duração para omitir microsegundos."""
        if obj.duration:
            return str(obj.duration).split('.')[0]
        return "-"
    
    duration_display.short_description = 'Duração'

    def is_finished(self, obj):
        """Indica com um ícone visual se a tentativa foi concluída."""
        return obj.finished_at is not None
    
    is_finished.boolean = True
    is_finished.short_description = 'Concluído'