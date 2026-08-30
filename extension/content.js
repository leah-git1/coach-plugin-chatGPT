// content.js — STEP 3: intercept.
//
// New since step 2:
//   1. a regex gate, so only a bare /coach:<name> is acted on
//   2. the kill, so ChatGPT never receives the command
//   3. a bubble rendered into the thread
//
// Since step 4 the answers come from the local Python service. The command
// list stays here so a typo never needs a round trip, and so the extension
// still behaves sanely with the service switched off.

// ^ and $ anchor to the whole message. This is deliberate: "I ran
// /coach:status today" is a genuine prompt about the tool and belongs to
// the model, not to us. \S* captures the command name.
const COMMAND_RE = /^\/coach:(\S*)$/;

// The service URL and the fetch live in background.js, not here — a request
// to 127.0.0.1 made from this file would carry chatgpt.com's origin and be
// blocked. This file asks the background worker and renders what comes back.

// Which names are real. Kept client-side on purpose: a near miss like
// /coach:staus should not need the network, and should still be caught when
// the service isn't running.
const COMMANDS = ['status', 'feedback', 'dashboard'];

function killEvent(event) {
  // Cancels the browser's default reaction to the key.
  event.preventDefault();
  // Ends the event's journey entirely, so ChatGPT's own listener is never
  // called. Without this, preventDefault alone would not stop their code.
  event.stopImmediatePropagation();
}

// Built with createElement rather than innerHTML. Assigning a string to
// innerHTML would treat it as markup, so any < or & in a response could
// break the page or inject something. textContent is inert by design.
function renderBubble(title, body, isWarning) {
  const wrapper = document.createElement('div');
  wrapper.className = isWarning ? 'coach-bubble coach-bubble--warn' : 'coach-bubble';
  wrapper.setAttribute('role', 'status');

  const head = document.createElement('div');
  head.className = 'coach-bubble__head';

  const name = document.createElement('span');
  name.className = 'coach-bubble__title';
  name.textContent = title;

  // So a locally-rendered bubble is never mistaken for something the model
  // said. This distinction matters more than the styling does.
  const tag = document.createElement('span');
  tag.className = 'coach-bubble__tag';
  tag.textContent = 'coach · local';

  const dismiss = document.createElement('button');
  dismiss.className = 'coach-bubble__dismiss';
  dismiss.type = 'button';
  dismiss.setAttribute('aria-label', 'Dismiss');
  dismiss.textContent = '×';
  dismiss.addEventListener('click', () => wrapper.remove());

  head.append(name, tag, dismiss);

  const text = document.createElement('pre');
  text.className = 'coach-bubble__body';
  text.textContent = body;

  wrapper.append(head, text);

  if (!Page.mount(wrapper)) {
    console.warn('[coach] nowhere to mount the bubble — selectors need repair');
    return null;
  }
  wrapper.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

  // Handles rather than a re-query. The bubble is mounted before the answer
  // exists, so the reply — or the failure — is written into it later. Holding
  // the nodes keeps the no-querySelector-in-content.js rule intact.
  return {
    setTitle(value) { name.textContent = value; },
    setBody(value) { text.textContent = value; },
    setWarning(on) { wrapper.classList.toggle('coach-bubble--warn', on); },
  };
}

function answer(commandName) {
  if (!COMMANDS.includes(commandName)) {
    // A near miss is still swallowed. Letting it through would send a
    // confusing message to the model. But it must always produce a bubble,
    // or the message would appear to vanish.
    const available = COMMANDS.map((n) => `/coach:${n}`).join(', ');
    renderBubble(`/coach:${commandName || '?'}`, `Unknown command.\nAvailable: ${available}`, true);
    return;
  }

  // The bubble goes up first, filled in when the service replies. The user
  // has already lost their typed text by this point, so something must be on
  // screen immediately whatever the network does next.
  const bubble = renderBubble(`/coach:${commandName}`, '…', false);
  if (!bubble) return;
  ask(commandName, bubble);
}

// Every path through this ends in the bubble saying something. A swallowed
// message with no visible answer is the one failure this must never produce.
async function ask(commandName, bubble) {
  let reply;

  try {
    reply = await chrome.runtime.sendMessage({ type: 'coach:ask', command: commandName });
  } catch (error) {
    // The background worker didn't answer at all. Nearly always means the
    // extension was reloaded while this tab kept running the old content
    // script, which is now orphaned from its worker.
    reply = { ok: false, error: `${error.message} — reload the ChatGPT tab` };
  }

  if (reply && reply.ok) {
    bubble.setTitle(reply.data.title || `/coach:${commandName}`);
    bubble.setBody(reply.data.body || '(the service returned an empty body)');
    return;
  }

  bubble.setWarning(true);
  bubble.setBody(
    `Could not reach the coach service at ${(reply && reply.service) || 'the local service'}\n` +
    `${(reply && reply.error) || 'the extension background sent no reply'}\n\n` +
    'Start it with:\n' +
    '  uvicorn server:app --host 127.0.0.1 --port 8765'
  );
}

// Entirely synchronous. The event either dies here or passes through
// untouched. Nothing in this function may await — once control returns to
// the browser, propagation has finished and preventDefault does nothing.
function intercept(event) {
  const match = Page.composerText().match(COMMAND_RE);
  if (!match) return;   // not a command: pass through to React and the model

  killEvent(event);
  Page.clearComposer();
  answer(match[1]);
}

window.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter') return;
  if (event.shiftKey) return;
  if (event.isComposing) return;
  intercept(event);
}, true);

// Step 2 listened on any button. Now it must be the send button
// specifically, or clicking Dismiss on a bubble would re-trigger the whole
// path while a command sits in the composer.
window.addEventListener('click', (event) => {
  const button = event.target.closest?.('button');
  if (!button || button !== Page.sendButton()) return;
  intercept(event);
}, true);

console.log(
  `[coach] ready — ${COMMANDS.map((n) => `/coach:${n}`).join(' ')}`
);