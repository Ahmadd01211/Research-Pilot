# Implemented database foundation

Migration `0001` creates the vector extension and two identity tables. Future conceptual research tables from the approved baseline are not prematurely created.

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
