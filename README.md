# Step 3 — intercept

Four files. `/coach:status`, `/coach:feedback` and `/coach:dashboard` are now
caught before ChatGPT sees them, and answered with a bubble in the thread.

Still no network. Still no Python. The responses are literal strings in
`content.js`.

## Load it

Same as step 2, but this is a **different folder**, so load it as a new
extension — and remove or disable the step 2 card first, or both will fire on
every Enter.

1. `chrome://extensions` → turn off or remove "Coach — step 2"
2. Load unpacked → pick this folder
3. Reload the chatgpt.com tab
4. Console shows `[coach] step 3 ready — /coach:status /coach:feedback /coach:dashboard`

## Test it

| Type this | Expect |
|---|---|
| `/coach:status` | bubble appears, **nothing sent to the model** |
| `/coach:feedback` | its own bubble |
| `/coach:dashboard` | its own bubble |
| `/coach:staus` | amber bubble listing the three real commands |
| `/coach:` | amber bubble (empty name is not a command) |
| `I ran /coach:status today` | **sends to the model** as a normal prompt |
| `/coach:status now` | sends to the model — trailing text means it isn't a bare command |
| `hello` | sends normally |
| `/coach:status`, then click send instead of Enter | same bubble, still not sent |
| click × on a bubble | bubble disappears, nothing else happens |

Rows six and seven are the ones worth being fussy about. If those get
swallowed, the `^...$` anchoring isn't working and you'd lose the ability to
ever discuss your own tool in ChatGPT.

Row nine matters because people reach for the mouse without thinking.

## Done when

The three commands produce bubbles, normal prompts still reach the model, and
the composer empties after a command instead of keeping the text.

## What's new since step 2

**`selectors.js`** — the selectors moved out of `content.js` into their own
file, as planned. It defines one global, `Page`, and `content.js` never calls
`querySelector` itself. When OpenAI redesigns, you edit this file only.

**`coach.css`** — bubble styling, declared in the manifest so Chrome injects
it alongside the script.

**The gate** in `content.js`:

```js
const COMMAND_RE = /^\/coach:(\S*)$/;
```

`^` anchors to the start of the string, `$` to the end. Together they mean
the command must be the whole message. `\S*` captures the name.

**The kill** — two calls that do different jobs:

| Call | Does |
|---|---|
| `preventDefault()` | cancels the browser's default reaction to the key |
| `stopPropagation()` | stops the journey, but other listeners on this same element still run |
| `stopImmediatePropagation()` | stops the journey **and** skips every remaining listener here |

We use the first and the third. `preventDefault` alone would leave ChatGPT's
listener free to run; `stopImmediatePropagation` alone might leave a browser
default in place.

**The bubble** — built with `createElement` and `textContent`, never
`innerHTML`. Assigning a string to `innerHTML` treats it as markup, so a `<`
or `&` in a response could break the page or inject something.
`textContent` is inert.

## Three details that will bite if you change them

**The kill must be synchronous.** `intercept()` contains no `await`, and must
never contain one before `killEvent`. Once your listener hands control back
to the browser, propagation has already finished and `preventDefault()`
silently does nothing — no error, the message just sends. This doesn't matter
yet, but in step 4 a fetch appears and it matters completely. The shape is
set now so it never has to change.

**Clearing the composer needs an input event.** `Page.clearComposer()` empties
the element *and* dispatches `new InputEvent('input')`. React keeps its own
record of what it thinks is in the field and will put the old text back
without that nudge.

**Unknown commands are swallowed, not passed through.** `/coach:staus` gets a
bubble rather than being sent to the model. Letting it through would produce a
confused reply about a plugin ChatGPT doesn't have. This is only safe because
a bubble always appears — a silent swallow would look like the app froze.

## The send button changed

Step 2 listened for a click on any button. Step 3 requires it to be the send
button specifically:

```js
if (!button || button !== Page.sendButton()) return;
```

Without that, clicking the × on a bubble would re-run `intercept()` while a
command still sat in the composer.

## Troubleshooting

**Command sends to the model anyway.** `Page.composerText()` returned
something the regex didn't match. Check in the console:

```js
Page.composerText()
```

Type a command first, then run it. If it returns `""`, the composer selector
in `selectors.js` needs fixing. If it returns the text with something extra
appended, the selector matched too large a container.

**No bubble, and a console warning about mounting.** The `message` selectors
in `selectors.js` are stale. Inspect an existing message in the Elements
panel and add its selector.

**Composer keeps the text after a command.** The input event isn't reaching
React. Try dispatching a `beforeinput` event as well in `clearComposer`.

**Two bubbles per command.** Both step 2 and step 3 are loaded, or the click
and keydown listeners are both firing. Disable the step 2 extension.

## Next

Step 4 replaces the `RESPONSES` object with a call to your Python service.
That needs two new things: a `worker.js` service worker to make the fetch
(chatgpt.com's CSP blocks the content script from reaching `127.0.0.1`), and
a `host_permissions` entry in the manifest. `intercept()` itself barely
changes — `answer()` becomes async, and the kill above it stays exactly where
it is.