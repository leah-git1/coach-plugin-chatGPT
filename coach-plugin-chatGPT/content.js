// content.js — STEP 2: read only.
//
// This file logs. It does not intercept. There is no preventDefault and no
// stopImmediatePropagation anywhere below, which means every message you
// type still reaches ChatGPT exactly as before.
//
// Its only job is to answer one question: does my selector find the
// composer, and is the text there when I read it?

// Tried in order, first match wins. This list is the only thing that will
// break when OpenAI redesigns their page, which is why it sits alone at the
// top. In step 3 it moves into its own selectors.js file.
const COMPOSER_SELECTORS = [
  '#prompt-textarea',
  'div[contenteditable="true"]',
  'textarea[data-id]',
];

function findComposer() {
  for (const selector of COMPOSER_SELECTORS) {
    const el = document.querySelector(selector);
    if (el) return { el, selector };
  }
  return null;
}

function readComposer() {
  const found = findComposer();
  if (!found) return null;
  const { el, selector } = found;
  // A contenteditable div holds text in innerText; a textarea holds it in
  // value. ChatGPT currently uses the former, but the fallback costs one
  // line and saves a confusing empty string later.
  const raw = el.tagName === 'TEXTAREA' ? el.value : el.innerText;
  return { text: raw.trim(), selector };
}

function onSend(source) {
  const result = readComposer();

  if (result === null) {
    console.warn('[coach] composer NOT FOUND — none of these matched:', COMPOSER_SELECTORS);
    return;
  }

  // JSON.stringify so trailing spaces and newlines are visible rather than
  // invisible. An empty string looks like "" instead of nothing at all.
  console.log(
    `[coach] ${source} | selector: ${result.selector} | text: ${JSON.stringify(result.text)}`
  );
}

// capture: true — the third argument. Even though this step intercepts
// nothing, reading in the capture phase matters: the event has not reached
// ChatGPT's code yet, so the composer still holds your text. Read in the
// bubble phase and it may already have been cleared.
window.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter') return;   // any other key is not a send
  if (event.shiftKey) return;          // shift+enter inserts a newline
  if (event.isComposing) return;       // an IME is mid-word, not a send
  onSend('enter');
}, true);

// Clicking send is the same event as far as we care. Included now so the
// gap does not surprise you in step 3.
window.addEventListener('click', (event) => {
  const button = event.target.closest?.('button');
  if (!button) return;
  onSend('click');
}, true);

// A startup line, so an empty console tells you the script never ran rather
// than leaving you guessing.
const atLoad = findComposer();
console.log(
  '[coach] step 2 ready.',
  atLoad ? `composer found via ${atLoad.selector}` : 'composer not found at load (may appear later)'
);