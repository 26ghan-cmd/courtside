import { api, loadApiBase } from "./api.js";

// Clicking the toolbar icon opens the side panel.
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(console.error);

export interface DetectedGame {
  gameId: string;
  label: string;
  sourceText: string;
}

const key = (tabId: number) => `tab:${tabId}`;

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg?.type === "invite" && typeof msg.id === "string") {
    // The side panel picks this up (now if it's open, or when it next opens).
    chrome.storage.local.set({ pendingRoom: { id: msg.id, server: msg.server } });
    return;
  }
  if (msg?.type !== "stream-detected" || sender.tab?.id === undefined) return;
  const tabId = sender.tab.id;
  loadApiBase() // the service worker restarts often; re-read the saved server each time
    .then(() => api.match(msg.text))
    .then(async (game) => {
      if (!game) return;
      const detected: DetectedGame = {
        gameId: game.id,
        label: `${game.away.abbreviation} @ ${game.home.abbreviation}`,
        sourceText: msg.text,
      };
      await chrome.storage.session.set({ [key(tabId)]: detected });
      await chrome.action.setBadgeText({ tabId, text: "ON" });
      await chrome.action.setTitle({ tabId, title: `Courtside: ${detected.label}` });
    })
    .catch((e) => console.warn("Courtside match failed", e));
});

chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.session.remove(key(tabId));
});
