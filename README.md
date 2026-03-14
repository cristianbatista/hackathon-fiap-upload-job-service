# Upload Job Service

Microsserviço responsável por receber uploads de vídeo de usuários autenticados, criar jobs no PostgreSQL com status `PENDING`, publicar mensagens na fila `video.processing` do RabbitMQ e expor endpoints de listagem de status e download dos ZIPs gerados pelo worker.

Retorna `202` imediatamente — **nunca processa vídeos de forma síncrona**.

---

## Endpoints

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/jobs` | JWT | Upload de vídeo → cria job (202) |
| `GET` | `/jobs` | JWT | Lista jobs do usuário autenticado (paginado) |
| `GET` | `/jobs/{job_id}/download` | JWT | Download do ZIP de frames (apenas jobs `DONE`) |
| `GET` | `/health` | — | Health check |
| `GET` | `/metrics` | — | Métricas Prometheus |
| `GET` | `/ping` | — | Liveness probe |

### POST /jobs

- **Request**: `multipart/form-data` com campo `file` (vídeo)
- **Headers**: `Authorization: Bearer <jwt>`
- **Response 202**:
  ```json
  {"job_id": "<uuid>", "status": "PENDING"}
  ```
- **Erros**:
  - `401` — JWT ausente ou inválido
  - `413` — Arquivo excede `MAX_UPLOAD_SIZE_MB`
  - `422` — MIME type não permitido

### GET /jobs

- **Query params**: `page` (default 1), `limit` (default 20, max 100)
- **Response 200**:
  ```json
  {
    "jobs": [
      {
        "job_id": "<uuid>",
        "filename": "video.mp4",
        "status": "PROCESSING",
        "error_message": null,
        "created_at": "2026-03-13T10:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "limit": 20
  }
  ```

### GET /jobs/{job_id}/download

- **Response 200**: arquivo `.zip` com `Content-Disposition: attachment`
- **Erros**:
  - `404` — job não encontrado ou de outro usuário
  - `409` — job ainda não concluído (`PENDING` ou `PROCESSING`)
  - `410` — job falhou com erro (`ERROR`)

---

## Variáveis de Ambiente

| Variável | Obrigatória | Default | Descrição |
|----------|-------------|---------|-----------|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `RABBITMQ_URL` | ✅ | `amqp://guest:guest@localhost:5672/` | RabbitMQ connection string |
| `STORAGE_PATH` | ✅ | `/storage` | Caminho base para armazenar vídeos e ZIPs |
| `JWT_SECRET` | ✅ | — | Chave secreta HS256 (deve coincidir com auth-service) |
| `MAX_UPLOAD_SIZE_MB` | ❌ | `200` | Tamanho máximo de upload em MB |
| `LOG_LEVEL` | ❌ | `INFO` | Nível de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

Copie `.env.example` para `.env` e preencha os valores obrigatórios.

---

## Como Rodar Localmente

### Com Docker

```bash
# Na raiz do projeto (hackathon-fiap/)
docker build -t upload-job-service services/upload-job-service
docker run -p 8001:8000 \
  -e DATABASE_URL="postgresql://postgres:postgres@host.docker.internal:5432/upload_jobs" \
  -e RABBITMQ_URL="amqp://guest:guest@host.docker.internal:5672/" \
  -e STORAGE_PATH="/storage" \
  -e JWT_SECRET="sua-chave-secreta" \
  -v $(pwd)/storage:/storage \
  upload-job-service
```

### Direto (Python)

```bash
cd services/upload-job-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edite .env com suas credenciais
uvicorn src.main:app --reload --port 8001
```

---

## Como Executar os Testes

```bash
cd services/upload-job-service
pip install -r requirements.txt

# Todos os testes (exceto integração)
pytest -m "not integration"

# Com relatório de cobertura
make coverage

# Testes de integração (requer RabbitMQ rodando)
RABBITMQ_URL=amqp://guest:guest@localhost:5672/ pytest -m integration
```

O gate de CI exige **cobertura ≥ 90%**.

### Targets do Makefile

| Target | Comando |
|--------|---------|
| `make lint` | Executa ruff + black --check |
| `make test` | pytest (exceto integration) |
| `make coverage` | pytest com relatório HTML |

---

## Migrations (Alembic)

```bash
# Criar nova migration
alembic revision --autogenerate -m "descrição"

# Aplicar migrations
alembic upgrade head

# Reverter
alembic downgrade -1
```

---

## Dependências Externas

| Serviço | Uso |
|---------|-----|
| **PostgreSQL 15** | Armazenamento da tabela `jobs` |
| **RabbitMQ** | Fila `video.processing` (durable); DLX `video.dlx` |
| **Volume Docker `video_storage`** | Compartilhado com worker-service para ler vídeos e escrever ZIPs |
| **auth-service** (indireto) | JWT compartilha `JWT_SECRET` e algoritmo HS256 — sem chamada de rede |

---

## Arquitetura de Dados

### Tabela `jobs`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID PK | Identificador único do job |
| `user_id` | UUID | Usuário dono do job (extraído do JWT) |
| `filename` | VARCHAR(512) | Nome original do arquivo |
| `file_size_bytes` | INTEGER | Tamanho do arquivo em bytes |
| `status` | ENUM | `PENDING` → `PROCESSING` → `DONE` ou `ERROR` |
| `error_message` | TEXT nullable | Motivo do erro (se status=ERROR) |
| `result_path` | VARCHAR(1024) nullable | Caminho do ZIP gerado (quando DONE) |
| `created_at` | TIMESTAMPTZ | Data de criação |
| `updated_at` | TIMESTAMPTZ | Última atualização |

### Mensagem na Fila

```json
{
  "job_id": "<uuid>",
  "user_id": "<uuid>",
  "file_path": "/storage/<job_id>/input/<filename>"
}
```

---

## Segurança

- JWT obrigatório em todos os endpoints de negócio
- `user_id` extraído exclusivamente do token JWT (nunca do request body)
- Isolamento total: `GET /jobs` e `GET /jobs/{id}/download` filtram por `user_id` do token
- Validação de MIME type e tamanho antes de qualquer I/O
- Atomicidade: falha no publish → rollback DB + cleanup do arquivo

## Arquitetura

Diagramas Mermaid versionados junto ao serviço:

- [C4 Container Diagram](docs/architecture/c4-container.md) — visão estrutural dos containers e dependências externas
- [Sequence Diagrams](docs/architecture/sequence.md) — upload bem-sucedido, formato inválido, listagem de jobs
