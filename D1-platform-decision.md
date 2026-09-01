# D1 — Platform decision

**Decision: ChatGPT on the web, instrumented by a browser extension** — not by
the vendor's compliance API.

## Why

The feasibility matrix ranks surfaces by their *sanctioned* capture path, and on
that basis M365 Copilot wins: three `NATIVE`s and verbatim prompt/response text
from Graph. But the matrix's own two implications overturn that ranking:

1. No pure chat UI can interject mid-session — feedback needs an out-of-band
   channel.
2. Content capture on every chat surface is plan-gated.

A coach that cannot reach the user is a dashboard. Once an out-of-band channel
is required anyway, the question becomes *which surface can be both read and
spoken into, without a licence upgrade*. In the browser, both jobs are done by
one mechanism: a content script.

---

## 1. Capture path

A Manifest V3 browser extension. A content script on `chatgpt.com` reads the
composer and the rendered thread from the DOM; a background service worker
relays to a local service, which keeps conversation content off the network.

This is a row the matrix does not carry, because it is not a vendor path:

| | Prompts | Responses | Metadata | Model detail | Interject |
|---|---|---|---|---|---|
| ChatGPT — compliance API | ENTERPRISE-ONLY | ENTERPRISE-ONLY | ENTERPRISE-ONLY | PARTIAL | PLUGIN |
| **ChatGPT — extension** | **NATIVE** | **PLUGIN** | **PLUGIN** | **PARTIAL** | **NATIVE** |

It moves the gate from *plan tier* to *installed*.

**Reliability.** The capture depends on OpenAI's HTML, so a redesign will break
it. Two design rules keep that a contained cost: every selector is isolated in
one module, so a redesign is a single-file repair; and each selector is an
ordered fallback list, so one renamed id does not take the feature down. The
interception itself depends only on DOM event ordering — a capture-phase
listener runs before the page's own — which is browser behaviour, not OpenAI's,
and does not drift.

| Residual risk | Mitigation |
|---|---|
| DOM redesign | selectors isolated to one module; fallback lists |
| Streaming, virtualised thread | commit response text only at stream-end |
| Mobile/desktop apps invisible | out of scope; measure and report web coverage |
| Per-browser install; user can disable | force-install by enterprise browser policy |

The property this gives up is **completeness**: an admin export is authoritative
over every session in the org, an extension only over instrumented browsers.
Coaching needs a representative corpus from consenting users, not a complete
one. Compliance reporting would need the reverse — a different product.

---

## 2. Data available

| Requirement | Verdict | Source |
|---|---|---|
| 1 Prompts | NATIVE | composer read before submit |
| 2 Responses | PLUGIN | observer over rendered message nodes |
| 3 Metadata | PLUGIN (partial) | timestamps, turn index, thread id, latency, regenerate/stop events. **No token counts, no cost.** |
| 4 Model detail | PARTIAL | model-picker display label only — no version, no reasoning-effort. Same verdict the compliance API earns. |
| 5 Interject | NATIVE | render into the live thread |

**Measurable** — anything evidenced by the text of the exchange and its shape
over turns: specificity and context provision; task decomposition; iteration and
refinement (the follow-up turn after an unsatisfying answer); constraint and
format setting; verification behaviour; session hygiene; recovery from failure.

**Not measurable** — anything priced in tokens (context efficiency, cost
awareness); model-selection judgement (a label says which model, never whether
it was the right call); feature breadth beyond text (uploads, canvas, custom
GPTs); outcome quality, which no surface in the matrix provides and which needs
self-report; and cross-surface work in an IDE, a mobile app, or a second
assistant.

In short: this platform measures **how someone works a conversation**, not what
it cost or what it was worth. That is the right half for prompt-craft atoms and
the wrong half for an efficiency or ROI score.

---

## 3. Feedback delivery

No vendor lets a third party speak unprompted in its thread — the matrix reads
`NONE` or reactive-only across every chat UI. The extension does not ask,
because it does not speak through the vendor: it writes to the DOM of a page the
user is already looking at. That is the out-of-band channel implication 1
demands, while staying visually where the work is.

Two modes: **pull**, where a slash command typed in the composer is intercepted
before submit and answered in place — no request, no stored message, no billing;
and **push**, where the same rendering path is triggered by an observed pattern
rather than a command. Push needs a rate limit and a mute designed in from the
start; an interjection nobody asked for is how the channel gets lost.

Two constraints on the rendering, both non-negotiable: coaching output is
visibly labelled and styled so it can never be mistaken for a model turn — text
that reads as ChatGPT's own would make this a misinformation channel — and it is
inserted as inert text, never as markup. Anything too long for an in-thread
interjection belongs in a separate dashboard; the in-thread channel is for the
short, timely nudge.

---

## 4. Terms of service

The mechanism is: a user-installed extension reads the DOM of a page rendered in
that user's own browser, for their own signed-in session, and cancels a
keystroke before the page handles it. No conversation content leaves the
machine.

**Defensible because** it does not automate the service (an intercepted command
is a request that never happens), does not circumvent rate limits or paywalls,
does not scrape or reach other users' data, and does not train a competing
model. Client-side modification of a rendered page by the person viewing it is
the ordinary operation of an extension.

**But permitted by absence, not by documentation.** OpenAI publishes a
sanctioned capture path and this is not it; provider terms generally restrict
programmatic access outside the published API, and composer interception can be
read as modifying the service rather than the browser. There is no ruling to
cite and no support commitment.

So the position is conditional:

| Condition | Why |
|---|---|
| Org-level sign-off from the vendor-relationship owner | the contract at risk is the org's |
| Force-install by policy, plus visible per-user consent | a sanctioned corporate tool, not a covert one |
| Capture stays local-first; no third-party transfer without a stated retention policy | separates the privacy question from the ToS one |
| Never mask, alter or suppress a model response | reading a page is defensible; rewriting the vendor's output is not |
| Where Enterprise/Edu exists, mirror archival capture to the compliance API | the sanctioned path becomes system of record; the extension keeps only the job it uniquely does |

That last row is the fallback if an objection lands: capture moves to the
documented API and the extension is reduced to a delivery channel. The design
survives it without rework, because capture and delivery are separate halves.

---

## 5. Reach

The coach exists for people who do not write code, which rules out the surfaces
easiest to instrument.

| Platform | Reach | Verdict |
|---|---|---|
| **ChatGPT** | **Highest** — for most non-technical staff it is what "AI" means; already in use across marketing, HR, sales, ops, legal, with no licence needed to start | **chosen** |
| Claude Cowork | Low — developer-adjacent | strong telemetry, but instrumenting engineers is the opposite of the brief |
| Claude chat | Moderate | `ENTERPRISE-ONLY` capture, `NONE` on interject — nowhere for feedback to land |
| M365 Copilot | High, best capture in the matrix | `NONE` on both model detail and interject; gated on an M365 tier and app-only Graph permission. Telemetry with no delivery channel is a dashboard |
| Gemini app | Moderate | `EXPORT-ONLY` batch dump, metadata-only reporting — near-real-time coaching is structurally impossible |

Copilot is the real contender and loses on one axis: it tells you everything
about what happened and gives you no way to answer. ChatGPT plus an extension
inverts that — a capture path to build, and a delivery path already there.

Reach here means the *web* UI. Mobile and desktop app users are invisible, so
web-session coverage must be measured and reported rather than assumed.

---

## Assumptions to verify before build

1. **Plan tier.** Enterprise/Edu makes the compliance API available as a
   fallback system of record and lowers the ToS risk sharply. Without it, the
   extension is the only path and §4's conditions are mandatory.
2. **Browser policy.** Force-install must be available for the pilot cohort;
   otherwise coverage is voluntary and unrepresentative.
3. **Atom scope.** Any micro-skill requiring token counts or outcome quality is
   out of scope on this platform and must be excluded from the mapping rather
   than measured partially.
