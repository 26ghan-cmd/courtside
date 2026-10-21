// Runs on Courtside invite pages (<server>/join/<code>). Hands the room code to
// the extension so the side panel joins it the next time it opens.
// Content scripts can't be ES modules, so this file must not import anything.

const statusEl = document.getElementById("status");
const inviteCode = statusEl?.dataset.room;

if (statusEl && inviteCode && statusEl.dataset.open === "1") {
  chrome.runtime
    .sendMessage({ type: "invite", id: inviteCode, server: location.origin })
    .then(() => {
      statusEl.textContent =
        "Courtside is installed. Click its icon in Chrome's toolbar to open the side panel and join.";
    })
    .catch(() => {
      // Extension was reloaded mid-visit; the code above still works by hand.
    });
}
