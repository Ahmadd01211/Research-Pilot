# Workspace flow and editor state design

12 November 2026

This repair covers sign-in continuation and Writing Studio state. FastAPI remains authoritative for ownership, project lifecycle, citation validation, revision conflicts and immutable saved versions. React owns the current editor buffer and navigation intent.

## Sign-in continuation

A protected route with no session redirects to sign-in with the pathname, search and fragment in router state. Successful authentication clears account-specific query data, seeds the authenticated session and replaces sign-in with the intended workspace destination. Direct sign-in defaults to the dashboard. Only workspace route prefixes are accepted; absolute destinations, protocol-relative destinations, backslashes and control characters are rejected.

The intent stays in browser history state rather than application storage. Recovery and registration still use their existing sign-in destinations; this slice does not preserve the original destination through those separate flows.

## Writing module

The editor interface accepts a project ID, a server draft and the archived flag. Its implementation owns both the editable title/body and the last acknowledged server draft. The route keys it by project/draft identity, never by revision. This concentrates revision and buffer rules in one module instead of requiring callers to coordinate remounts and query invalidation.

| Event | Editor buffer | Saved revision | Presentation |
| --- | --- | --- | --- |
| Open draft | Copy initial server text | Initial revision | Saved version |
| Type or insert a citation | Update local text | Unchanged | Unsaved changes |
| Submit | Snapshot title, body and expected revision | Unchanged | Saving |
| Save succeeds | Normalize only fields still matching submitted text; retain subsequent typing | Adopt returned server revision | Saved or unsaved according to current buffer |
| Save fails or conflicts | Preserve text | Unchanged | Server error and recovery guidance |
| Newer draft arrives | Preserve text | Unchanged | Offer latest-version review |
| Copy latest reviewed version | Explicitly replace buffer | Adopt that latest revision | Saved version |
| Refresh fails with cached draft | Preserve mounted editor | Unchanged | Refresh error and retry |
| Open another draft | Initialize that draft's buffer | Its revision | Separate editor |

The successful mutation response updates the draft cache directly. List and version-history queries are then invalidated. A second save uses the acknowledged revision even if a separate read would be stale. FastAPI still rejects an outdated expected revision; refreshing does not silently permit overwriting another researcher's edits.

## Presentation rules

Reuse existing foundations from `frontend/src/styles/globals.css`. No new theme is introduced by this repair.

| Role | Existing token or pattern |
| --- | --- |
| Page and surface | `--canvas`, `--surface`, `.card` |
| Primary and secondary text | `--navy`, `--muted` |
| Primary action | `--blue`, `--blue-hover`, `.btn.primary` |
| Error | `--danger`, `.alert`, `role="alert"` |
| Positive status | `--teal`, `.notice`, `role="status"` |
| Field outline | `--border-strong`, `.field` |
| Typography | `--font` for body, `--heading` for headings |
| Surfaces and spacing | `--radius`, existing 16/24 px spacing utilities |

Saved, unsaved, saving and error states must use text, not color alone. Use labelled controls and native buttons. A failed refresh offers retry without replacing the editor. Version review displays the saved text and warns that copying replaces unsaved work. Archived state disables editing; the server independently enforces it.

This is a state-pattern specification for the repaired flows, not a complete design-system audit. Existing global colors, sizing, responsiveness and focus appearance require the user's manual visual review. Dark mode and a wholesale token migration are outside this slice.

## Validation and remaining limits

Regression tests exercise return navigation, rejected destinations, concurrent draft refresh, refresh failure, explicit latest-version adoption and typing during an in-flight save. Existing backend tests cover ownership, revisions and saved versions. Tests use only the disposable `rp_greenfield_test` database.

Unsaved buffers remain memory-only. Leaving the editor or reloading the page can still lose unsaved work; route-leave protection and local draft persistence remain follow-up work. The rest of the application's flows have not been certified by these two focused repairs. No external AI-provider quality or email-delivery verification is claimed.
