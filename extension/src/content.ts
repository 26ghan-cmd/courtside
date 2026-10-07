// Runs on streaming sites. Collects text that might name the game being
// streamed and sends it to the background worker, which asks the backend to
// match it against today's scoreboard.
//
// Content scripts can't be ES modules, so this file must not import anything.

const KEYWORDS = /basketball|ncaa|college|\bvs\.?\b|\bat\b|@/i;

function pageHints(): string {
  const parts = [
    document.title,
    document.querySelector<HTMLMetaElement>('meta[property="og:title"]')?.content ?? "",
    document.querySelector("h1")?.textContent ?? "",
  ];
  return parts.map((s) => s.trim()).filter(Boolean).join(" | ").slice(0, 300);
}

let lastSent = "";

function report(): void {
  const text = pageHints();
  if (!text || text === lastSent || !KEYWORDS.test(text)) return;
  lastSent = text;
  chrome.runtime.sendMessage({ type: "stream-detected", text }).catch(() => {
    // Background worker may be restarting; we'll retry on the next title change.
    lastSent = "";
  });
}

report();
// Streaming sites are single-page apps: watch for title changes on navigation.
const titleEl = document.querySelector("title");
if (titleEl) new MutationObserver(report).observe(titleEl, { childList: true });
setInterval(report, 10_000);
