// background.js — the only place that talks to the local service.
//
// content.js used to fetch this directly. It can't. A fetch from a content
// script carries the page's origin, so a request to 127.0.0.1 from
// chatgpt.com is a public HTTPS page reaching into the local network: Chrome
// preflights it, gates it behind Local Network Access, and the request hangs
// rather than failing. No server-side header fixes that from the page side.
//
// A fetch from here runs as the extension, under the host_permissions in
// manifest.json, and is subject to neither CORS nor that gate. This is the
// pattern MV3 intends for reaching localhost.

const SERVICE = 'http://127.0.0.1:8787';

// Matches the CLI's DEFAULT_HTTP_TIMEOUT_MS, which is the informed number: /coach:feedback runs a
// judge on the backend, and that is routinely slower than a few seconds. At the old 4000 the abort
// fired while the request was still working, and the bubble blamed the local service for a call
// that would have succeeded — the most misleading failure this can produce.
//
// The service answers a dead backend in about a second (it uses a short connect timeout), so a
// backend that is simply not running still reports quickly. This ceiling only governs the slow
// case, where waiting is correct.
const TIMEOUT_MS = 40000;

async function ask(commandName) {
  const response = await fetch(`${SERVICE}/${commandName}`, {
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) throw new Error(`service replied ${response.status}`);
  return response.json();
}

// Returning true is load-bearing: it keeps the message channel open for an
// async reply. Without it the channel closes the moment this listener
// returns, sendResponse becomes a no-op, and the bubble waits on '…' forever.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== 'coach:ask') return;

  ask(message.command)
    .then((data) => sendResponse({ ok: true, data }))
    .catch((error) => sendResponse({ ok: false, error: error.message, service: SERVICE }));

  return true;
});
