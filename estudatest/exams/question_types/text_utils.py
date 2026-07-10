def clean_text(value):
    """Normaliza um campo de texto vindo do POST: remove espaços nas pontas."""
    return (value or '').strip()