# Writing Studio: authored text, citations, and versions

This slice provides explicit researcher-authored drafts. A project can hold up to 20 active drafts. Each draft has a Markdown title/body editor, headings extracted into an outline, and reference markers inserted from the project's verified bibliography. The marker `[@reference-uuid]` is a durable link to a reference record, **not** formatted citation text or proof that a sentence is supported. The source PDF remains available through the reference link and should be checked before making a claim.

The API validates citation markers and ensures every cited active reference belongs to the project. An update compares the submitted revision with the current draft and rejects stale saves. It writes the current draft and a separate immutable `WritingVersion` in one transaction, so the visible saved version cannot disagree with its historical snapshot. Version history is paged twenty at a time. Copying an older version into the editor does not rewrite history; saving creates a new version.

The editor uses plain Markdown text rather than rich-text HTML for this first phase. That avoids storing arbitrary HTML and makes versions easy to compare, but it lacks formatted editing and a full citation renderer. All draft text is currently user-authored; AI-generated writing is not mixed into this field. Future AI suggestions need separate provenance and explicit researcher acceptance. Saves are explicit, with a visible unsaved state. Route navigation, including Back and Forward, now requires an explicit discard choice while edits or a save are pending. Reload and close use the browser warning where supported. Draft text remains in memory; crash recovery and automatic local drafts are not implemented.

To review: create a draft from a project, add a `#` heading, insert a reference from the left panel, and save. The outline should update, the citation marker should appear in the body, and the new version should appear in history. Then edit again, inspect the earlier snapshot, and copy it into the editor. A stale revision is rejected without clearing the unsaved text. Archived projects allow reading but not saving.

## Draft protection -- 25 October 2026

The editor owns a stable saved baseline separate from refreshed query data. Its component identity follows the draft ID rather than revision, so background updates cannot remount it and erase edits. Successful saves adopt the returned revision while retaining text typed after submission. Failed saves preserve editor state. A conflict fetches the current server draft and shows both texts; choosing to keep local text updates only the baseline revision, and a separate explicit save remains required. Loading server text requires confirmation. Further concurrent saves are still rejected by the backend revision check. No automatic merge is performed.

The application entry point now uses React Router's data router around the existing route tree, enabling its supported navigation blocker without changing URLs. A writing-only guard handles internal navigation and browser history; reload/close warnings depend on browser support and user interaction. The comparison component presents plain text. No draft text is persisted in browser storage, and there are no backend, schema, migration or provider changes.

Verification: 80 frontend tests pass, including links and history blocking, reload warnings, conflict comparison, explicit replacement confirmation, refresh preservation and edits during saves. Lint, TypeScript and production build pass; the existing bundle-size warning remains. Visual acceptance belongs to the user.

## Named manuscript starters - 25 October 2026

New drafts now ask for a title and an explicit structure: blank, research article or literature review. Structures add headings only, never claims or study findings. The form retains its inputs after creation errors. Outline headings select their source position in the editor; word and character counts update locally. Draft saving, reference validation and immutable versions remain server-authoritative.
