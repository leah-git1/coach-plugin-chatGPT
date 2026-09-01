# Coach for ChatGPT

A Chrome extension that adds `/coach:` slash commands to chatgpt.com.

Commands typed into ChatGPT's composer are caught by the extension and answered
locally, in a bubble in the thread. The model is never asked. This is the
ChatGPT counterpart to the Coach plugin for Claude Code, which gets the same
effect from a hook system that a web page doesn't have.

## Commands

| Command | Answers with |
|---|---|
| `/coach:status` | your progress toward the next AI profile |
| `/coach:feedback` | feedback on your last prompt |
| `/coach:dashboard` | a link to the management dashboard |

Anything else beginning with `/coach:` gets an amber bubble listing the three
real commands. It is not passed to the model either — a near miss like
`/coach:staus` would only produce a confused reply about a plugin ChatGPT
doesn't have.

## Why the model never sees the command

The model isn't in the browser. Text in the composer exists only on your
machine until ChatGPT's own JavaScript builds an HTTPS request and sends it.
The extension prevents that function from ever being called, so there is no
request, no stored message, and no model invocation — nothing to filter and
nothing to bill.

It can do that because of the order in which the browser delivers a keystroke:
the event travels down through the page before it reaches the elements that
registered interest. Listening on the way down means being called first, while
ChatGPT's listener is still waiting its turn. Two calls then end it:

| Call | Does |
|---|---|
| `preventDefault()` | cancels the browser's default reaction to the key |
| `stopImmediatePropagation()` | ends the event's journey and skips every remaining listener |

Both are needed. `preventDefault` alone leaves ChatGPT's listener free to run;
`stopImmediatePropagation` alone can leave a browser default in place.

Because Enter isn't the only way to submit, the same path runs for a click on
the send button.

## What counts as a command

```js
const COMMAND_RE = /^\/coach:(\S*)$/;
```

`^` anchors to the start of the message and `$` to the end, so the command must
be the entire message. This is deliberate, and it's the rule most worth
protecting:

| Typed | Result |
|---|---|
| `/coach:status` | intercepted — bubble, nothing sent |
| `/coach:status` then click send | intercepted — same bubble |
| `/coach:staus` | intercepted — amber bubble, nothing sent |
| `/coach:` | intercepted — amber bubble, empty name isn't a command |
| `I ran /coach:status today` | **sent to the model** — a genuine prompt about the tool |
| `/coach:status now` | **sent to the model** — trailing text means it isn't a bare command |
| `hello` | sent to the model |

The two rows that send are the ones to be fussy about. If the anchoring breaks
and they get swallowed, you lose the ability to ever discuss your own tool
inside ChatGPT.

## Install

There's no build step for the extension. Two processes, then Chrome.

`pip` puts `uvicorn.exe` in a Scripts directory that is not on PATH here, so **always start it as
`python -m uvicorn`** — a bare `uvicorn` gives `CommandNotFoundException`.

### Once

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Installing into the venv rather than `pip install fastapi uvicorn` globally keeps this off the
user-wide site-packages, where a newer FastAPI arriving for some other project can break this one
without touching it.

### Every run — terminal 1, the backend on 8788

It defaults to 8787, the same port as the extension's service, and the extension's port is baked
into `manifest.json`. So the backend is the one that moves:

```powershell
$env:PORT = "8788"; bun run dev      # in evolve-coach/projects/backend
```

No Bun installed? This serves fixed stand-in data on 8788:

```powershell
.venv\Scripts\python.exe dev_backend_stub.py
```

The stub imports nothing outside the standard library, so the venv is not needed for its
dependencies — it is needed to avoid the interpreter. This machine's **system** Python has
`pip_system_certs` in its site-packages, which runs on every startup and imports the whole of pip's
vendored `requests` before your script gets a line in: measured, `python -c pass` takes 1.5 s there
against 0.10 s in the venv, and it has crashed startup outright with
`Fatal Python error: init_import_site`. A venv disables user-site, so that hook never fires. Use
`.venv\Scripts\python.exe` for anything in this project.

### Every run — terminal 2, the service on 8787

PowerShell has no inline `VAR=value cmd` form; set them first, on their own lines:

```powershell
.venv\Scripts\Activate.ps1
$env:COACH_BACKEND_URL = "http://127.0.0.1:8788"
$env:COACH_USER_ID = "you@example.com"
python -m uvicorn server:app --host 127.0.0.1 --port 8787 --reload
```

`$env:` values last only for that window. A new terminal starts without them, and `/coach:status`
then reports that no user is configured — which is the symptom to recognise, not a bug.

Check both halves before touching Chrome:

```powershell
curl.exe -s http://127.0.0.1:8787/health
```

`"reachable": true` means terminal 1 is up; `"user_configured": true` means `COACH_USER_ID` is set.
If `reachable` is false, nothing in the extension is at fault.

### Every run — Chrome

1. `chrome://extensions` → enable Developer mode
2. **Load unpacked** → pick the `extension/` folder, not the repo root
3. Reload the chatgpt.com tab

The console logs
`[coach] ready — /coach:status /coach:feedback /coach:dashboard`
when the content script has attached.

The commands are still caught with the service down — you just get an amber
bubble saying it couldn't be reached, rather than an answer.

### A note on ports on Windows

Windows lets a second process bind a port another process already holds, without an error. If two
copies of the service are running, requests are split between them and edits appear to have no
effect. `netstat -ano | findstr ":8787"` showing two LISTENING lines is the tell.


## The files

Two halves that ship together and run apart. The browser half is everything
under `extension/`; the machine half is `server.py` at the root.

| File | Owns |
|---|---|
| `extension/manifest.json` | which pages the extension runs on, what it injects, and which host it may reach |
| `extension/background.js` | the only code that talks to the service |
| `extension/selectors.js` | every assumption about ChatGPT's HTML — defines the `Page` global |
| `extension/content.js` | the command gate, the interception, and bubble rendering |
| `extension/coach.css` | bubble styling |
| `requirements.txt` | the service's three pinned dependencies |
| `dev_backend_stub.py` | a stand-in for the Evolve Coach backend, for when Bun isn't available |
| `server.py` | the surface adapter: turns each command into its Evolve Coach backend call and renders the reply |

The split is not tidiness. Chrome refuses to load an unpacked extension whose
folder contains any name beginning with an underscore, and the moment Python
imports `server.py` it writes a `__pycache__` directory beside it. With both
halves in one folder, running the server broke the extension. A root that
Python may litter and an `extension/` that it never touches is the fix.

The split between `selectors.js` and `content.js` is the point of the layout:
`content.js` never calls `querySelector` itself. When OpenAI redesigns their
page, `selectors.js` is the only file that needs repairing.

Bubbles are labelled `coach · local` so a locally rendered answer is never
mistaken for something the model said. That distinction matters more than the
styling does.

## Invariants

Four things that break quietly if changed.

**The kill must be synchronous.** `intercept()` contains no `await` and must
never contain one before `killEvent`. Once your listener hands control back to
the browser, propagation has already finished and `preventDefault()` silently
does nothing — no error, the message just sends.

**Clearing the composer needs an input event.** `Page.clearComposer()` empties
the element *and* dispatches `new InputEvent('input')`. React keeps its own
record of what it believes is in the field and will put the old text back
without that nudge.

**Bubbles are built with `createElement` and `textContent`, never
`innerHTML`.** Assigning a string to `innerHTML` treats it as markup, so a `<`
or `&` in a response could break the page or inject something. `textContent` is
inert by design.

**The click listener checks for the send button specifically.** Not any button
— otherwise clicking × on a bubble would re-run `intercept()` while a command
still sat in the composer.

**The fetch must stay in `background.js`.** Moving it into `content.js` looks
like a simplification and fails in a way that is hard to read: a content
script's requests carry the *page's* origin, so a call to `127.0.0.1` becomes a
public HTTPS page reaching into the local network. Chrome preflights it and
gates it behind Local Network Access, and the request hangs until the timeout
rather than returning an error that names the cause. No header on the Python
side fixes it. The background worker runs as the extension under
`host_permissions` and is subject to neither rule.

**`onMessage` must return `true`.** It signals that a reply is coming later.
Return nothing and the channel closes the moment the listener does, the reply
is silently dropped, and the bubble waits on its placeholder forever.

## Troubleshooting

**A command reaches the model anyway.** `Page.composerText()` returned
something the regex didn't match. Type a command, then in the console run:

```js
Page.composerText()
```

`""` means the composer selector in `selectors.js` needs fixing. Text with
something extra appended means the selector matched too large a container.

**No bubble, and a console warning about mounting.** The `message` selectors are
stale. Inspect an existing message in the Elements panel and add its selector.

**The composer keeps the text after a command.** The input event isn't reaching
React. Try dispatching a `beforeinput` event as well in `clearComposer`.

**Two bubbles per command.** Another build of this extension is also loaded, or
both the keydown and click listeners are firing for one submit.

**Every command says the service is unreachable.** Open
`http://127.0.0.1:8787/health` in a tab first. If it doesn't answer, the service
isn't running and nothing in the extension is at fault. If it does answer, the
worker is the place to look: `chrome://extensions` → **service worker** opens
its own console, separate from the page's, and the failing fetch appears there.

**"Receiving end does not exist."** The extension was reloaded while a ChatGPT
tab stayed open, leaving a content script with no worker to talk to. Reload the
tab.

## Scope today

`server.py` on `127.0.0.1:8787` is a surface adapter, not a source of answers: it calls the Evolve
Coach backend and renders the reply in the same words the CLI uses, so this surface and Claude Code
read identically. `/coach:status` and `/coach:dashboard` are wired end to end.

`/coach:feedback` is not, and cannot be without a decision: judging a prompt requires sending the
prompt, and the extension deliberately sends only the command name. The endpoint already accepts
`?prompt=`, so the wiring is one change away — but that change means capturing conversation
content, which is a product decision rather than a missing line of code.

Nothing is stored. Apart from the configured `COACH_USER_ID`, nothing that leaves the page goes
anywhere but your own machine, and no conversation content is captured. The extension reads the
composer, and only the composer.

The command names live in `COMMANDS` in `content.js` rather than being fetched,
so a typo is caught without a round trip and still gets its amber bubble when
the service is off.
