from django.core.exceptions import ValidationError

MAX_OPTIONS = 10
MAX_OPTION_LENGTH = 500


def normalize_options(post_data):
    """Extrai e limpa a lista de alternativas enviada no POST, aplicando o
    limite máximo. Usado na validação/persistência real."""
    options = [text.strip() for text in post_data.getlist('data_options') if text.strip()]
    if len(options) > MAX_OPTIONS:
        raise ValidationError(f'A questão pode ter no máximo {MAX_OPTIONS} alternativas.')
    return options


def raw_options(post_data):
    """Retorna as alternativas exatamente como foram enviadas, sem filtrar
    linhas em branco nem aplicar limites. Usado apenas para reconstruir o
    formulário após um envio inválido, sem alterar o que o usuário digitou."""
    return post_data.getlist('data_options')