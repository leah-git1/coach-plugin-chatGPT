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

There's no build step.

1. `chrome://extensions` → enable Developer mode
2. **Load unpacked** → pick this folder
3. Reload the chatgpt.com tab

The console logs `[coach] ready — /coach:status /coach:feedback /coach:dashboard`
when the content script has attached.

## The files

| File | Owns |
|---|---|
| `manifest.json` | which pages the extension runs on, and what it injects |
| `selectors.js` | every assumption about ChatGPT's HTML — defines the `Page` global |
| `content.js` | the command gate, the interception, and bubble rendering |
| `coach.css` | bubble styling |

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

## Scope today

Answers are literal strings in the `RESPONSES` object in `content.js`. Nothing
is fetched, nothing is stored, and no conversation content is captured or
transmitted. The extension reads the composer, and only the composer.
