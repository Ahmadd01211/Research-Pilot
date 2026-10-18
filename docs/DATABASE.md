# Implemented database foundation

Migration chain: `0001` creates the vector extension and identity tables; `0002` adds research_projects and project_activities. Other future research tables remain conceptual.

```mermaid
erDiagram
  USER ||--o{ SESSION : has
  USER {
    uuid id PK
    string email UK
    string display_name
    string password_hash
    timestamptz created_at
    timestamptz updated_at
  }
  SESSION {
    uuid id PK
    uuid user_id FK
    string token_hash UK
    string csrf_hash
    timestamptz created_at
    timestamptz last_seen_at
    timestamptz expires_at
    timestamptz revoked_at
  }
```

Application-generated UUIDs; UTC timestamps; owner foreign key; normalized email uniqueness; session hash uniqueness; indexes on owner/expiry. Passwords use Argon2id; bearer session secrets are never stored raw. A session has absolute and idle expiry and explicit revocation.

Tests run only with environment=test and a database ending in `rp_greenfield_test`. They migrate to head, compare model/migration metadata and use synthetic accounts. These checks are not a production backup/restore or concurrency certification. Application volumes use the independent `researchpilot_greenfield` Compose project name and must not be reset to fix migrations.


## Project model

```mermaid
erDiagram
  USER ||--o{ RESEARCH_PROJECT : owns
  RESEARCH_PROJECT ||--o{ PROJECT_ACTIVITY : records
  RESEARCH_PROJECT {
    uuid id PK
    uuid owner_id FK
    string title
    text description
    jsonb research_questions
    jsonb objectives
    int revision
    uuid create_request_id
    string create_payload_hash
    timestamptz created_at
    timestamptz updated_at
    timestamptz archived_at
    timestamptz deleted_at
  }
  PROJECT_ACTIVITY {
    uuid id PK
    uuid project_id FK
    string action
    string summary
    jsonb changed_fields
    timestamptz created_at
  }
```

Unique owner/request ID, positive-revision check, owner/created/id and project/created/id indexes, RESTRICT foreign keys. A project deletion is a timestamped state transition, not a cascade. Read/update queries enforce owner and nondeleted state. JSONB arrays are replaced as complete bounded values when edited; they are not independent question entities yet.

The disposable test suite verifies model/migration parity, simultaneous creation, competing stale edits, transaction rollback, and soft-delete retention. Local application migration to 0002 is additive; existing users/sessions remain intact.
