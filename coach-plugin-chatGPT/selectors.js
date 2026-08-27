// selectors.js
//
// Everything that assumes something about ChatGPT's HTML lives here and
// nowhere else. When OpenAI redesigns their page, this is the only file you
// edit. That is the whole reason it is separate.
//
// It defines one global, `Page`. content.js uses it and never calls
// querySelector itself.

const SELECTORS = {
  // Where you type. Tried in order, first match wins.
  composer: [
    '#prompt-textarea',
    'div[contenteditable="true"]',
    'textarea[data-id]',
  ],
  // The send button, so a click can be intercepted the same way as Enter.
  sendButton: [
    'button[data-testid="send-button"]',
    'button[aria-label*="Send" i]',
  ],
  // Existing messages, used to work out where to put the bubble.
  message: [
    '[data-message-author-role]',
    'article',
  ],
  // If no messages exist yet (empty chat), fall back to this container.
  threadFallback: [
    'main',
  ],
};

function firstMatch(selectorList) {
  for (const selector of selectorList) {
    const el = document.querySelector(selector);
    if (el) return el;
  }
  return null;
}

function lastMatch(selectorList) {
  for (const selector of selectorList) {
    const all = document.querySelectorAll(selector);
    if (all.length) return all[all.length - 1];
  }
  return null;
}

const Page = {
  composer() {
    return firstMatch(SELECTORS.composer);
  },

  sendButton() {
    return firstMatch(SELECTORS.sendButton);
  },

  composerText() {
    const el = this.composer();
    if (!el) return '';
    const raw = el.tagName === 'TEXTAREA' ? el.value : el.innerText;
    return raw.trim();
  },

  // Emptying the DOM is not enough on its own. React keeps its own copy of
  // what it believes is in the field, and will happily put the old text
  // back. Dispatching an input event is what tells React to look again.
  clearComposer() {
    const el = this.composer();
    if (!el) return;
    if (el.tagName === 'TEXTAREA') {
      el.value = '';
    } else {
      el.innerText = '';
    }
    el.dispatchEvent(new InputEvent('input', { bubbles: true }));
  },

  // Put a node at the end of the thread. Returns false if it could not
  // find anywhere sensible, so the caller can warn instead of failing
  // silently.
  mount(node) {
    const last = lastMatch(SELECTORS.message);
    if (last) {
      const block = last.closest('article') || last;
      block.parentElement.insertBefore(node, block.nextSibling);
      return true;
    }
    const fallback = firstMatch(SELECTORS.threadFallback);
    if (fallback) {
      fallback.appendChild(node);
      return true;
    }
    return false;
  },
};