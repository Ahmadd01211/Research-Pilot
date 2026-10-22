# Persistent Research Chat

Research Chat saves conversations inside one research project. The thread routes are under `/api/v1/projects/{project_id}/evidence/threads`; creating or continuing a thread requires current project ownership. Archived projects remain readable but cannot start or extend a conversation.

Every successful answer turn stores its question, selected document IDs, answer statements, model name, cited source excerpts, page numbers, source hashes and reader versions. The snapshot remains unchanged after later reader updates. A follow-up sends at most the six most recent turns as untrusted context, retrieves fresh evidence from the papers selected for that turn, and accepts citations only from that fresh retrieval. Earlier answer text can resolve references but cannot act as evidence for new claims.

Threads are listed newest first, capped at 100 per project in the current response. Turns currently have no deletion or expiration workflow; a retention policy remains necessary before public release. Provider calls remain opt-in through the server-side Google key. Spending budgets and usage metering remain future work.
