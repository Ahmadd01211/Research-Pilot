# 18 — Password change and recovery

## What the user sees

- **Account settings → Password.** Enter the current password and a new one twice. On success this device stays signed in and every other device is signed out.
- **Sign in → Forgot password?** Enter an email. The page always says "If an account exists for …", so it never reveals whether an address is registered.
- **Email link → Choose a new password.** The link works once and expires after 30 minutes. After the reset, every session is signed out and the sign-in page confirms the change.

## Code path

| Layer | File | Responsibility |
|---|---|---|
| Config | `backend/app/core/config.py` | `RP_SMTP_*`, `RP_MAIL_FROM`, `RP_PASSWORD_RESET_MINUTES`; production requires encrypted SMTP |
| Mail | `backend/app/infrastructure/mail.py` | `MailSender` protocol and the stdlib `SmtpSender`; `app.state.mail` is `None` without a host |
| Model | `backend/app/modules/identity/models.py` | `PasswordResetToken` (hash only, expiry, `consumed_at`) |
| Migration | `backend/alembic/versions/0018_password_reset.py` | Additive table and index |
| Service | `backend/app/modules/identity/service.py` | `change_password`, `request_password_reset`, `send_reset_email`, `reset_password` |
| Routes | `backend/app/modules/identity/router.py` | `POST /me/password`, `/auth/password/forgot`, `/auth/password/reset` |
| UI | `frontend/src/features/auth/password-forms.tsx` | Forgot, reset and change forms; `password-field.tsx` is the shared show/hide input |

## Decisions and tradeoffs

**Same answer for every email.** Forgot-password returns 204 whether or not the account exists, and the email is sent in a FastAPI background task after the response, so slow SMTP does not reveal an account through timing. Tradeoff: a delivery failure is only logged (by error category, never the address or token). There's no retry; the user can request another link. A durable outbox in Celery would add retries, but it would put a live token in the broker.

**Only the token hash is stored.** As with sessions, the database holds SHA-256 of a 256-bit random token. A database leak does not yield working links.

**Single use without races.** `reset_password` consumes the token with one conditional `UPDATE … WHERE consumed_at IS NULL AND expires_at > now RETURNING user_id`. Two simultaneous submissions cannot both succeed, because PostgreSQL re-checks the condition after the first commit.

**One live link per user.** Requesting a new link, changing the password or completing a reset sets `consumed_at` on all outstanding links. An old email in an inbox stops working.

**Token in the URL fragment.** The link is `/reset-password#token=…`. Browsers never send fragments to servers, so Nginx and API logs and the Referer header never contain it. The reset page reads the token into memory and immediately removes it from the address bar.

**Session handling.** Changing the password keeps the current session, so the person isn't thrown out mid-task, and revokes the others. A reset revokes all sessions, because whoever holds an old session might be the reason for the reset.

**No fake email.** Without `RP_SMTP_HOST` the endpoint returns 503 "not configured", so the UI never claims an email was sent. Development compose runs Mailpit (`http://localhost:8025`), a real SMTP server that keeps every message in a local inbox instead of delivering it.

## Testing it yourself

1. `docker compose up -d --build`, then open http://localhost:3100/login and choose **Forgot password?**
2. Open http://localhost:8025 to read the email, then follow the link.
3. For real delivery, set `RP_SMTP_HOST`, `RP_SMTP_PORT=587`, `RP_SMTP_SECURITY=starttls`, `RP_SMTP_USERNAME`, `RP_SMTP_PASSWORD` and `RP_MAIL_FROM` in `.env` for a provider whose domain has SPF/DKIM configured.

Automated coverage: `backend/tests/test_passwords.py` (session revocation, generic answers, hashing, supersession, expiry, reuse, rate limit, missing configuration, secret-free failure logs, production config) and `frontend/tests/passwords.test.tsx`.

## Not included

Email-address verification at sign-up, changing the account email, a durable mail outbox and per-end-user IP limits behind the proxy. See `docs/SECURITY.md`.
