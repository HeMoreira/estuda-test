# EstudaTest

Aplicação Django para criação e gerenciamento de provas de estudo com repetição espaçada.

## Configuração

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente
```bash

# Defina SECRET_KEY, DEBUG, ALLOWED_HOSTS e DATABASE_URL em um arquivo .env
```

### 3. Aplicar migrations
```bash
python manage.py migrate
```

### 4. Criar superusuário (administrador)
```bash
python manage.py createsuperuser
```
> Contas de admin só podem ser criadas via terminal.

### 5. Rodar o servidor
```bash
python manage.py runserver
```

Acesse: http://127.0.0.1:8000

---

## Estrutura de apps

| App | Responsabilidade |
|-----|-----------------|
| `accounts` | Login/logout via `django.contrib.auth` |
| `categories` | Categorias do usuário + dashboard principal |
| `exams` | Provas e questões (7 tipos) |
| `attempts` | Realização, progresso em sessão e histórico |

## Tipos de questão suportados

- Múltipla escolha (até 5 alternativas)
- Resposta múltipla (até 8 opções)
- Verdadeiro ou Falso
- Resposta escrita (com normalização de texto)
- Ordenar elementos (drag-and-drop, até 8 itens)
- Relacionar colunas (até 10 pares)
- Flashcard (autoavaliado)

## Algoritmo de repetição espaçada

`limite_dias = 30 + (n/50)² × 335`

- 0 tentativas → vermelho após 30 dias
- 25 tentativas → vermelho após ~114 dias
- 50 tentativas → vermelho após 365 dias

## Segurança

- Todas as rotas protegidas por `@login_required` (deny by default)
- Validação de propriedade `obj.user == request.user` em toda operação (proteção IDOR)
- CSRF token em todos os formulários
- Escape automático de HTML pelo template engine do Django (proteção XSS)
- Acesso ao banco exclusivamente via Django ORM (proteção SQL Injection)
- Credenciais em variáveis de ambiente via `.env` (nunca no código)
