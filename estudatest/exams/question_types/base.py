class BaseQuestionTypeHandler:
    """Contrato que cada tipo de questão implementa.

    Concentra validação, criação e serialização de um tipo específico,
    eliminando os antigos if/elif repetidos por utils.py.
    """
    type_value = None

    def validate(self, post_data, errors):
        raise NotImplementedError

    def build_instance(self, statement, explanation, post_data):
        raise NotImplementedError

    def save_dependencies(self, question, post_data):
        """Cria registros relacionados (opções, itens, pares) na criação."""
        return

    def update_dependencies(self, question, post_data):
        """Atualiza registros relacionados na edição. Por padrão, reaproveita save_dependencies."""
        self.save_dependencies(question, post_data)

    def build_edit_json(self, question):
        """Serializa uma questão já salva no formato usado pelo editor JS."""
        return {}

    def build_preview_json(self, post_data):
        """Serializa um POST (possivelmente inválido) no mesmo formato de
        build_edit_json, para repopular o formulário sem perder o que o
        usuário digitou quando a validação falha."""
        return {}