# EstudaTest

Aplicação Django para criação e gerenciamento de provas para fins de estudos com sistema de repetição espaçada.

## Configuração

### 1. Acesse a subpasta principal
```bash
cd estudatest
```
> Lembre-se de definir um ambiente virtual caso queira

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente
```bash
# Defina SECRET_KEY, DEBUG, ALLOWED_HOSTS e DATABASE_URL em um arquivo .env
```
> Exemplo:
> ```bash
> SECRET_KEY=sua_chave_secreta
> DEBUG=True
> ALLOWED_HOSTS=127.0.0.1,localhost
> DATABASE_URL=sqlite:///db.sqlite3
> ```

### 4. Aplicar migrations
```bash
python manage.py migrate
```

### 5. Popular banco de dados (Opcional)
```bash
# Provas e questões de exemplo para testes / estudos
python manage.py loaddata tech_exams.json
```
> Esse comando popula o banco de dados com um usuário e algumas provas/questões úteis para desenvolvimento/estudos. Caso opte por pular essa etapa, você ainda poderá criar seu próprio usuário e exames.
> A senha do usuário 'Tech_Exams' é `3$tud@T3$t`

### 6. Criar superusuário (administrador)
```bash
python manage.py createsuperuser
```
> Contas de admin só podem ser criadas via terminal.

### 7. Rodar o servidor
```bash
python manage.py runserver
```

Acesse: http://127.0.0.1:8000 ou http://localhost:8000

---

## Estrutura de apps

| App | Responsabilidade |
|-----|-----------------|
| `main`       | dashboard principal do usuário logado |
| `accounts`   | Login/logout via `django.contrib.auth` |
| `categories` | Gerenciamento de Categorias do usuário |
| `exams`      | Gerenciamento de Provas e Questões |
| `attempts`   | Realização e histórico de provas |

## Tipos de questão suportados

- Múltipla escolha
- Resposta múltipla
- Verdadeiro ou Falso
- Resposta escrita
- Ordenar elementos
- Relacionar colunas
- Flashcard (autoavaliado)

## Algoritmo de repetição espaçada

Usa fórmulas para estimar o tempo de esquecimento de conteúdo, te lembrando de realizar a prova novamente.
`limite_dias = 1 + (n/50)² × 364`

n = número de tentativas
- 0 tentativas → Alerta máximo de esquecimento após 1 dia
- 25 tentativas → Alerta máximo de esquecimento após 92 dias
- 50 tentativas → Alerta máximo de esquecimento após 365 dias

## Segurança

- Todas as rotas protegidas por `@login_required`
- Validação de propriedade `obj.user == request.user` em toda operação (proteção IDOR)
- CSRF token em todos os formulários
- Credenciais em variáveis de ambiente via `.env` (nunca no código)
<!-- - Escape automático de HTML pelo template engine do Django (proteção XSS)
- Acesso ao banco exclusivamente via Django ORM (proteção SQL Injection)
-->
