# ResearchPilot / Scholarly Blue

## Design intent

A research workspace should lower cognitive load while making the boundary between evidence and interpretation unmistakable. The design uses a restrained white/navy/blue vocabulary, quiet borders, generous spacing around work areas, and higher density within structured tables. It avoids decorative dashboards, invented academic impact scores, generic agents and automation canvases.

Marketing introduces a research journey rather than unsupported promises. It shows the actual interface language and a synthetic evidence example. Pricing cards are explicitly plan concepts with pricing unestablished. No testimonials, customer logos, outcomes, or claims of completed product functionality have been invented.

## Tokens

`design-tokens.json` is the portable source for implementation mapping; `styles.css` defines the working CSS variables.

| Token | Value | Use |
|---|---|---|
| Canvas | `#F8FAFC` | Workspace background |
| Surface | `#FFFFFF` | Panels, editor, navigation |
| Primary text | `#14213D` | Headings and document hierarchy |
| Accent | `#3457D5` | Primary actions, active navigation, citation links |
| Secondary text | `#62718A` | Supporting context |
| Subtle text | `#68758C` | Tertiary text where applicable |
| Teal | `#24736C` | Source-supported/ready states |
| Amber | `#946315` | Uncertainty and incomplete metadata |
| Red | `#AC3747` | Errors and failed processing |
| Border | `#E5E9F0` | Noninteractive separators |
| Strong border | `#CBD3E0` | Inputs and stronger boundaries |

Calculated color contrast against white: primary 6.05:1, navy 15.97:1, secondary text 4.94:1, subtle text 4.65:1, teal 5.61:1, amber 5.18:1, red 6.19:1. These calculations cover the named solid-color pairs, not every rendered combination. Low-contrast borders are decorative; focus outlines and labels identify active controls. Perform a full accessibility audit when integrating the production components.

Fonts: Manrope headings, DM Sans interface, Georgia long-form document text. The first two are bundled variable fonts; no remote font request is required. System fonts provide fallbacks. Core manuscript text is 14px with 2.0 line-height; matrix fields are 12px with 1.85 line-height. Small labels identify hierarchy rather than replacing substantive reading text. Browser zoom remains enabled.

Spacing uses a 4px base: 4, 8, 12, 16, 20, 24, 32, 40, 48. Core panel radii are 12px, dialogs 14px, controls 7–8px. Shadows separate layers sparingly. Motion is limited to feedback, sidebar transitions and loading shimmer; reduced-motion preferences disable animation.

## Layout patterns

- Desktop: persistent 234px navigation, 73px topbar, restrained preview strip, 36px content gutters, capped content width. Dashboard uses a main research column and a supporting actions/activity column.
- Wide desktop: greater reading space and supporting panels; content does not expand indefinitely.
- Tablet: supporting columns stack; chat evidence remains reachable through citations instead of keeping a cramped third column; writing assistance stacks below the editor.
- Mobile at 760px and below: navigation becomes an overlay drawer, project cards stack, research tables scroll, editor and assistant stack, dialogs expand to available width. Main controls use larger touch targets.
- The literature matrix is a real semantic table, with study row headers kept sticky during horizontal scrolling. It does not collapse evidence into disconnected cards.
- Evidence drawers are modal, right-aligned, and retain the source identity, page, excerpt and methodological limitation together.

## Reusable component patterns

| Component | Content / behavior | Production mapping |
|---|---|---|
| AppShell | Main/secondary navigation, active route, project context | Shared layout; route-aware, no business logic |
| PageHeading | One task title, explanation, limited primary actions | Reusable feature header |
| ProjectCard | Research title, purpose, source count | Count from authorized project resources |
| DocumentTable / DocumentCard | Metadata, textual status, selection, open action | Same typed document data, two layouts |
| UploadPanel | File selection/drop, constraints and honest processing state | Upload API + durable job polling/events |
| StatusBadge | Text label plus semantic tone | Backend state union, never color-only |
| CitationChip | Source identifier with drawer action | Stable citation ID and evidence resolver |
| EvidenceDrawer | Source, location, quoted excerpt, limits, document link | Authorized exact retrieval evidence |
| ScopeSelector | Explicit ready-source selection | Project ownership validation before retrieval |
| ConversationPane | History, user text, labeled model output, composer | Persisted scope and typed stream lifecycle |
| EvidenceMatrix | Editable fields, row headers, linked evidence | Revision checks, original extraction retained |
| CandidateGapCard | Interpretation, supporting limitations, uncertainty, next question | Corpus-bounded analysis; no unverified novelty claim |
| ManuscriptEditor | Outline, content, save state, version actions | Structured rich-text editor and immutable revisions |
| AISuggestion | Separate proposal, evidence, accept/dismiss | Never silently overwrites authored content |
| ReferenceRecord | Bibliography, missing metadata, linked paper | Validated import and style processor |
| ExportDialog | Format, snapshot/provenance options, availability | Real format capability list and durable jobs |
| StatePanel | Empty/loading/processing/failure/success | Actual lifecycle, action appropriate to state |

## Interaction states

All workspace routes expose the design-state selector for review. This selector is prototype tooling and should not ship in the actual product. Production renders states from typed server data instead.

- Empty: explains what belongs here and provides one next action.
- Loading: preserves panel geometry with skeletons and an announced status; do not show invented progress percentages.
- Processing: named stages, current work, preserved source identity; production needs durable job status and safe cancellation semantics.
- Failure: safe explanation, recovery route, request/reference ID, no sensitive technical detail. Existing work stays accessible.
- Success: states what completed and offers a next step; success must reflect durable completion, not a mere HTTP acceptance response.
- Save state: visible local saving/saved text; production adds revision conflict and failed-save recovery without destroying edits.

## Evidence and authorship semantics

Source findings are presented with citation chips. Interpretations use explicit wording and uncertainty labels. Gap analysis never equates absence from selected papers with absence from the whole literature. Source links validate provenance, not entailment.

Writing suggestions are a distinct panel and require acceptance. Accepting the sample proposal saves the previous local draft as a named revision first. Accepted illustrative content is labeled in the text. Production should retain authorship/provenance metadata at claim or node level even after further editing, rather than relying only on background color.

Matrix edits change the reviewed field value while keeping the original sample excerpt accessible. Production must preserve original extraction and edit history separately. The prototype keeps editable values and a synthetic corpus, not a production provenance model.

## Accessibility contract

Use semantic headings, landmarks, tables, form labels and buttons. Main content has a skip link and route focus target. Named native dialogs trap modal focus in supporting browsers; Escape closes them and the prior trigger regains focus. The mobile navigation has a keyboard focus loop and Escape recovery. Visible focus outlines and text labels complement icons.

Save states and notifications use polite live announcements. Inputs use browser validation and suitable autocomplete values. Password visibility is explicitly toggled. Reduced motion is honored. Source tables retain evidence fields on small screens through horizontal scrolling. Production should include screen-reader and keyboard testing, zoom/reflow at 200–400%, contrast testing, error associations, editor accessibility and real-device testing.

The prototype uses browser `execCommand` for a few rich-text demonstrations; it is deprecated and is **not** the proposed production editor engine. Evaluate a structured editor such as Tiptap with citation nodes, schema validation and export conversion before production integration.
