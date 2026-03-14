# Sequence Diagrams — Upload Job Service

**Serviço**: `upload-job-service`  
**Cobertura**: Happy path (US1 + US2) + erros críticos  
**Atualizado**: 2026-03-13

---

## Fluxo 1 — Happy Path: Upload de vídeo (US1)

```mermaid
sequenceDiagram
    autonumber
    participant Client as Cliente HTTP
    participant API as Upload API (FastAPI)
    participant JWTGuard as JWT Guard
    participant JobSvc as Job Service
    participant FileSvc as File Storage
    participant DB as PostgreSQL
    participant MQ as RabbitMQ

    Client->>API: POST /jobs [multipart/form-data: file=video.mp4, Bearer JWT]
    API->>JWTGuard: validate_token(Bearer)
    JWTGuard-->>API: user_id (válido)
    API->>API: Valida MIME type e tamanho (≤ MAX_UPLOAD_SIZE_MB)
    API->>FileSvc: save_file(video.mp4)
    FileSvc-->>API: file_path (/data/uploads/{uuid}.mp4)
    API->>JobSvc: create_job(user_id, filename, file_path)
    JobSvc->>DB: INSERT jobs (id, user_id, filename, status=PENDING, file_path)
    DB-->>JobSvc: job inserido {job_id}
    JobSvc->>MQ: publish(queue=video_processing, {job_id, file_path, user_id})
    MQ-->>JobSvc: confirmed
    JobSvc-->>API: {job_id, status: "PENDING"}
    API-->>Client: 202 Accepted {job_id, status: "PENDING"}
```

---

## Fluxo 2 — Erro: Arquivo com formato inválido

```mermaid
sequenceDiagram
    autonumber
    participant Client as Cliente HTTP
    participant API as Upload API (FastAPI)
    participant JWTGuard as JWT Guard

    Client->>API: POST /jobs [multipart/form-data: file=document.pdf, Bearer JWT]
    API->>JWTGuard: validate_token(Bearer)
    JWTGuard-->>API: user_id (válido)
    API->>API: Valida MIME type
    Note over API: MIME type "application/pdf" não está em ALLOWED_MIME_TYPES
    API-->>Client: 422 Unprocessable Entity {"detail": "Tipo de arquivo não permitido"}
    Note over API: Arquivo não salvo em disco<br/>Nenhum job criado no banco
```

---

## Fluxo 3 — Happy Path: Listagem de jobs do usuário (US2)

```mermaid
sequenceDiagram
    autonumber
    participant Client as Cliente HTTP
    participant API as Upload API (FastAPI)
    participant JWTGuard as JWT Guard
    participant JobSvc as Job Service
    participant DB as PostgreSQL

    Client->>API: GET /jobs?page=1&limit=20 [Bearer JWT]
    API->>JWTGuard: validate_token(Bearer)
    JWTGuard-->>API: user_id (válido)
    API->>JobSvc: list_jobs(user_id, page=1, limit=20)
    JobSvc->>DB: SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 20 OFFSET 0
    DB-->>JobSvc: [lista de jobs]
    JobSvc-->>API: {jobs: [...], total: N}
    API-->>Client: 200 OK {jobs: [...], total: N}
    Note over DB: Isolamento garantido: WHERE user_id filtra<br/>jobs de outros usuários
```

---

## Resumo dos fluxos

| Fluxo | Trigger | Resultado final |
|-------|---------|----------------|
| Upload bem-sucedido | POST /jobs com vídeo válido + JWT | 202 + job_id criado |
| Formato inválido | Arquivo não suportado (PDF, imagem, etc.) | 422 sem criação de job |
| Listagem | GET /jobs com JWT válido | 200 + jobs do usuário (isolados por user_id) |
