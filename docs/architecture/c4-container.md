# C4 Container Diagram — Upload Job Service

**Nível**: Container (C4 Nível 2)  
**Serviço**: `upload-job-service`  
**Atualizado**: 2026-03-13

---

```mermaid
C4Container
    title Container Diagram — Upload Job Service

    Person(user, "Usuário Autenticado", "Faz upload de vídeos, acompanha status dos jobs e baixa ZIPs")
    System_Ext(authService, "Auth Service", "Emite tokens JWT; não é consultado em tempo de request (validação local)")
    System_Ext(workerService, "Worker Service", "Consome fila video_processing e atualiza status dos jobs")

    Container_Boundary(uploadBoundary, "upload-job-service") {
        Container(api, "Upload API", "Python 3.11, FastAPI", "POST /jobs (upload), GET /jobs (listagem), GET /jobs/{id}/download, GET /health, GET /metrics")
        Container(jwtGuard, "JWT Guard", "python-jose", "Valida token JWT localmente (sem chamada de rede ao auth-service)")
        Container(fileStorage, "File Storage", "Python / aiofiles", "Salva binário do vídeo em volume Docker compartilhado; retorna path para o job")
        Container(jobService, "Job Service", "Python", "Cria job PENDING, publica mensagem na fila, lista e filtra jobs do usuário")
        Container(metricsMiddleware, "Metrics Middleware", "prometheus-fastapi-instrumentator", "Expõe /metrics na porta 8000")
    }

    ContainerDb(postgres, "PostgreSQL", "PostgreSQL 15", "Tabela jobs: id, user_id, filename, status, file_path, created_at, updated_at, error_message")
    ContainerDb(volume, "Volume Storage", "Docker Volume", "Armazena binários de vídeo e ZIPs gerados pelo worker; path /data/uploads e /data/outputs")
    ContainerQueue(rabbitmq, "RabbitMQ", "RabbitMQ 3", "Fila 'video_processing' (durable); mensagens persistidas")

    Rel(user, api, "POST /jobs, GET /jobs, GET /jobs/{id}/download", "HTTPS / REST")
    Rel(api, jwtGuard, "Valida Bearer token em cada request protegido", "In-process")
    Rel(api, jobService, "Delega criação, listagem e download de jobs", "In-process")
    Rel(jobService, fileStorage, "Persiste arquivo do vídeo em upload", "In-process")
    Rel(fileStorage, volume, "Escreve/lê binários de vídeo e ZIPs", "Filesystem")
    Rel(jobService, postgres, "INSERT / SELECT jobs (filtrando por user_id)", "PostgreSQL protocol")
    Rel(jobService, rabbitmq, "Publica {job_id, file_path} em video_processing", "AMQP")
    Rel(workerService, postgres, "UPDATE jobs SET status=... WHERE id=?", "PostgreSQL protocol")
    Rel(workerService, volume, "Lê vídeo, escreve ZIP de frames", "Filesystem (volume compartilhado)")
```

---

## Elementos

| Elemento | Tipo | Tecnologia | Responsabilidade |
|----------|------|-----------|-----------------|
| Upload API | Container | FastAPI | Endpoints REST de upload, listagem e download |
| JWT Guard | Container | python-jose | Validação local de JWT sem chamada ao auth-service |
| File Storage | Container | aiofiles | Persistência assíncrona de binários em volume Docker |
| Job Service | Container | Python | Lógica de negócio de jobs: criação, publicação, listagem |
| Metrics Middleware | Container | prometheus-fastapi-instrumentator | `/metrics` porta 8000 |
| PostgreSQL | ContainerDb | PostgreSQL 15 | Fonte de verdade para estado dos jobs |
| Volume Storage | ContainerDb | Docker Volume | Binários de vídeo e ZIPs (compartilhado com worker) |
| RabbitMQ | ContainerQueue | RabbitMQ 3 | Fila `video_processing` durable |

## Decisões de design

- Retorna `202 Accepted` imediatamente — processamento assíncrono via Worker Service (Princípio II da constituição)
- Isolamento de dados: `SELECT WHERE user_id = current_user.id` em todas as queries (Princípio III)
- Download só disponível para jobs `DONE` — Worker atualiza status diretamente no PostgreSQL compartilhado
