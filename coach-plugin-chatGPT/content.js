// content.js — STEP 3: intercept.
//
// New since step 2:
//   1. a regex gate, so only a bare /coach:<name> is acted on
//   2. the kill, so ChatGPT never receives the command
//   3. a bubble rendered into the thread
//
// Still no network and no Python. The responses below are literal strings.

// ^ and $ anchor to the whole message. This is deliberate: "I ran
// /coach:status today" is a genuine prompt about the tool and belongs to
// the model, not to us. \S* captures the command name.
const COMMAND_RE = /^\/coach:(\S*)$/;

// Hardcoded for this step. In step 4 these come from the Python service.
const RESPONSES = {
  status: 'Your request to status was received.',
  feedback: 'Your request to feedback was received.',
  dashboard: 'Your request to dashboard was received.',
};

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
    return;
  }
  wrapper.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function answer(commandName) {
  const body = RESPONSES[commandName];

  if (body === undefined) {
    // A near miss is still swallowed. Letting it through would send a
    // confusing message to the model. But it must always produce a bubble,
    // or the message would appear to vanish.
    const available = Object.keys(RESPONSES).map((n) => `/coach:${n}`).join(', ');
    renderBubble(`/coach:${commandName || '?'}`, `Unknown command.\nAvailable: ${available}`, true);
    return;
  }

  renderBubble(`/coach:${commandName}`, body, false);
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
  `[coach] ready — ${Object.keys(RESPONSES).map((n) => `/coach:${n}`).join(' ')}`
);