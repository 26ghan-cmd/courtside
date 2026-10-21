import { api, getApiBase, loadApiBase, LOCAL_API, ONLINE_API, setApiBase, type Analysis, type GameDetail, type GameListing, type ServerMessage } from "./api.js";

const POLL_MS = 15_000;

// ---------------------------------------------------------------- tiny DOM helper
// Always set text via textContent (never innerHTML) — chat messages are untrusted.
type Child = Node | string | null | undefined | false;
function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Partial<HTMLElementTagNameMap[K]> & { class?: string } = {},
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  const { class: cls, ...rest } = props;
  if (cls) node.className = cls;
  Object.assign(node, rest);
  for (const c of children) if (c) node.append(c);
  return node;
}
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

// ---------------------------------------------------------------- state
let gameId: string | null = null;
let pollTimer: number | undefined;
let socket: WebSocket | null = null;

// Replay mode: step through a finished game as if it were live.
let replayAt: number | null = null; // null = normal (live/final) view
let replayTimer: number | undefined;
let totalPlays = 0;
let inFlight = false;
let pendingRefresh = false;

// ---------------------------------------------------------------- tabs
document.querySelectorAll<HTMLButtonElement>(".tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll<HTMLButtonElement>(".tabs button").forEach((b) =>
      b.setAttribute("aria-selected", String(b === btn)),
    );
    document.querySelectorAll<HTMLElement>(".tab").forEach((t) => {
      t.hidden = t.id !== `tab-${btn.dataset.tab}`;
    });
  });
});

// ---------------------------------------------------------------- connection banner
// A free Render server sleeps after 15 idle minutes and takes about a minute
// to wake, so a failed request usually means "wait", not "broken".
const RETRY_MS = 10_000;
const MAX_RETRIES = 12; // ~2 minutes
let bannerRetries = 0;
let bannerTimer: number | undefined;

function serverDown(): void {
  window.clearTimeout(bannerTimer);
  const waking = bannerRetries < MAX_RETRIES;
  $("banner-text").textContent = waking
    ? "Waking up the Courtside server. This can take about a minute…"
    : "Can't reach the Courtside server. Check your connection, or the server address in Settings.";
  $("banner").hidden = false;
  if (waking) {
    bannerRetries += 1;
    bannerTimer = window.setTimeout(retryNow, RETRY_MS);
  }
}

function serverUp(): void {
  window.clearTimeout(bannerTimer);
  bannerRetries = 0;
  $("banner").hidden = true;
}

function retryNow(): void {
  loadPicker().then(() => refresh());
}

$("banner-retry").addEventListener("click", () => { bannerRetries = 0; retryNow(); });

// ---------------------------------------------------------------- game selection
// The date picker lets you browse past games, e.g. last season's while it's the offseason.
function localISODate(d = new Date()): string {
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

async function loadPicker(): Promise<void> {
  const select = $<HTMLSelectElement>("game-select");
  const dateInput = $<HTMLInputElement>("date-input");
  const iso = dateInput.value || localISODate();
  const isToday = iso === localISODate();
  select.replaceChildren(el("option", { value: "", textContent: "Loading games…" }));
  try {
    const games = await api.games(iso.replaceAll("-", ""));
    const empty = isToday ? "No games today. Pick another date above." : "No games on this date";
    select.replaceChildren(
      el("option", { value: "", textContent: games.length ? `Choose a game (${games.length})…` : empty }),
      ...games.map((g) =>
        el("option", {
          value: g.id,
          textContent: `${g.away.short_name} @ ${g.home.short_name} — ${g.status.detail}`,
        }),
      ),
    );
    serverUp();
  } catch {
    select.replaceChildren(el("option", { value: "", textContent: "Waiting for the server…" }));
    serverDown();
  }
  // Keep the current game selected if it's in this date's list.
  if (gameId && Array.from(select.options).some((o) => o.value === gameId)) select.value = gameId;
}

$<HTMLSelectElement>("game-select").addEventListener("change", (ev) => {
  const value = (ev.target as HTMLSelectElement).value;
  if (value) selectGame(value);
});
$<HTMLInputElement>("date-input").addEventListener("change", () => loadPicker());

async function detectFromActiveTab(): Promise<void> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id === undefined) return;
  const k = `tab:${tab.id}`;
  const stored = (await chrome.storage.session.get(k))[k];
  if (stored?.gameId) selectGame(stored.gameId);
}

function selectGame(id: string): void {
  if (id === gameId) return;
  exitReplay(false);
  gameId = id;
  $<HTMLSelectElement>("game-select").value = id;
  window.clearInterval(pollTimer);
  refresh();
  pollTimer = window.setInterval(refresh, POLL_MS);
}

async function refresh(): Promise<void> {
  if (!gameId) return;
  // Replay ticks and slider drags can outpace the network; never stack requests.
  if (inFlight) { pendingRefresh = true; return; }
  inFlight = true;
  const at = replayAt ?? undefined;
  try {
    const [detail, analysis] = await Promise.all([api.game(gameId, at), api.analysis(gameId, at)]);
    totalPlays = detail.total_plays;
    renderScorebug(detail.game);
    renderStats(detail);
    renderAnalysis(detail, analysis);
    renderReplay(detail.game.status.state);
    if (detail.game.status.state === "post" && replayAt === null) window.clearInterval(pollTimer);
    serverUp();
  } catch (e) {
    if (e instanceof TypeError) serverDown(); // network failure, not a bad response
    else $("status-text")?.replaceChildren(`Couldn't load this game: ${(e as Error).message}`);
  } finally {
    inFlight = false;
    if (pendingRefresh) { pendingRefresh = false; refresh(); }
  }
}

// ---------------------------------------------------------------- replay
function renderReplay(state: string): void {
  // Offer replay for finished games; keep the controls while replaying.
  $("replay").hidden = state !== "post" && replayAt === null;
  $("replay-start").hidden = replayAt !== null;
  $("replay-controls").hidden = replayAt === null;
  if (replayAt === null) return;
  const slider = $<HTMLInputElement>("replay-slider");
  slider.max = String(totalPlays);
  slider.value = String(replayAt);
  $("replay-label").textContent = `Play ${replayAt} of ${totalPlays}`;
  $("replay-play").textContent = replayTimer === undefined ? "▶" : "❚❚";
  $("replay-play").setAttribute("aria-label", replayTimer === undefined ? "Play" : "Pause");
}

function pauseReplay(): void {
  window.clearInterval(replayTimer);
  replayTimer = undefined;
}

function playReplay(): void {
  if (replayAt !== null && replayAt >= totalPlays) replayAt = 0; // restart from tip-off
  replayTimer = window.setInterval(() => {
    if (replayAt === null) return pauseReplay();
    const speed = Number($<HTMLSelectElement>("replay-speed").value);
    replayAt = Math.min(totalPlays, replayAt + speed);
    if (replayAt >= totalPlays) pauseReplay();
    refresh();
  }, 1000);
  refresh();
}

function exitReplay(reload = true): void {
  pauseReplay();
  if (replayAt === null) return;
  replayAt = null;
  if (reload) refresh();
}

$("replay-start").addEventListener("click", () => {
  window.clearInterval(pollTimer);
  replayAt = 0;
  playReplay();
});
$("replay-play").addEventListener("click", () => {
  if (replayTimer === undefined) playReplay();
  else { pauseReplay(); refresh(); }
});
$<HTMLInputElement>("replay-slider").addEventListener("input", (ev) => {
  replayAt = Number((ev.target as HTMLInputElement).value);
  refresh();
});
$("replay-exit").addEventListener("click", () => exitReplay());

// ---------------------------------------------------------------- rendering
function teamCell(t: GameListing["home"], side: "home" | "away"): HTMLElement {
  return el("div", { class: `team ${side}` },
    side === "away" && t.logo ? el("img", { src: t.logo, alt: "" }) : null,
    el("span", { textContent: t.abbreviation || t.short_name }),
    el("span", { class: "score", textContent: String(t.score) }),
    side === "home" && t.logo ? el("img", { src: t.logo, alt: "" }) : null,
  );
}

function renderScorebug(g: GameListing): void {
  const bug = $("scorebug");
  bug.classList.remove("empty");
  bug.replaceChildren(
    teamCell(g.away, "away"),
    el("div", { class: "clock", textContent: g.status.detail }),
    teamCell(g.home, "home"),
  );
}

function renderStats(d: GameDetail): void {
  const { home, away } = d.game;
  // Replay snapshots only rebuild shooting and points, so show just those.
  const replaying = d.replay_at != null;
  const labels = replaying ? ["FG", "3PT", "FT"] : ["FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK"];
  const statOf = (tid: string, label: string) =>
    d.team_stats[tid]?.find((s) => s.abbreviation === label || s.label === label)?.value ?? "–";

  const teamTable = el("table", {},
    el("tr", {}, el("th"), el("th", { textContent: away.abbreviation }), el("th", { textContent: home.abbreviation })),
    ...labels.map((l) =>
      el("tr", {}, el("td", { textContent: l }), el("td", { textContent: statOf(away.id, l) }), el("td", { textContent: statOf(home.id, l) })),
    ),
  );

  const playerTable = (teamId: string) => {
    const cols = replaying ? ["PTS"] : ["MIN", "PTS", "REB", "AST"];
    return el("table", {},
      el("tr", {}, el("th", { textContent: "Player" }), ...cols.map((c) => el("th", { textContent: c }))),
      ...d.players
        .filter((p) => p.team_id === teamId)
        .map((p) => el("tr", {}, el("td", { textContent: p.name }), ...cols.map((c) => el("td", { textContent: p.stats[c] ?? "–" })))),
    );
  };

  const recent = d.plays.slice(-25).reverse();
  $("tab-stats").replaceChildren(
    el("h3", { textContent: "Team" }), teamTable,
    el("h3", { textContent: away.short_name }), playerTable(away.id),
    el("h3", { textContent: home.short_name }), playerTable(home.id),
    el("h3", { textContent: "Play-by-play" }),
    el("ul", { class: "plays" },
      ...recent.map((p) =>
        el("li", { class: p.scoring ? "scoring" : "" },
          el("span", { class: "muted", textContent: `${p.clock} ` }),
          p.text,
          p.scoring ? el("span", { class: "muted", textContent: `  (${p.away_score}-${p.home_score})` }) : null,
        ),
      ),
    ),
  );
}

function renderAnalysis(d: GameDetail, a: Analysis): void {
  const { home, away } = d.game;
  const names: Record<string, string> = { [home.id]: home.short_name, [away.id]: away.short_name };
  const pct = (v: number | null | undefined) => (v == null ? "–" : `${(v * 100).toFixed(1)}%`);

  $("tab-analysis").replaceChildren(
    el("div", { class: "card", textContent: a.summary }),
    el("h3", { textContent: "Flow" }),
    el("p", { textContent: `${a.lead_changes} lead changes · ${a.ties} ties` }),
    el("p", {
      textContent: `Largest lead — ${away.short_name}: ${a.largest_lead[away.id] ?? 0}, ${home.short_name}: ${a.largest_lead[home.id] ?? 0}`,
    }),
    el("h3", { textContent: "Scoring runs" }),
    a.runs.length
      ? el("ul", {}, ...a.runs.slice(0, 5).map((r) =>
          el("li", { textContent: `${names[r.team_id] ?? "?"} ${r.points}-0 (period ${r.period})` })))
      : el("p", { class: "muted", textContent: d.game.status.state === "post" ? "No one scored 7+ unanswered points." : "No runs of 7+ yet." }),
    el("h3", { textContent: "Shooting" }),
    el("table", {},
      el("tr", {}, el("th"), el("th", { textContent: "FG%" }), el("th", { textContent: "3P%" }), el("th", { textContent: "FT%" })),
      ...[away, home].map((t) => {
        const s = a.shooting[t.id];
        return el("tr", {}, el("td", { textContent: t.short_name }),
          el("td", { textContent: pct(s?.fg_pct) }), el("td", { textContent: pct(s?.three_pct) }), el("td", { textContent: pct(s?.ft_pct) }));
      }),
    ),
  );
}

// ---------------------------------------------------------------- chat
// Rooms survive brief drops: the socket reconnects with backoff, a ping every
// 4 minutes keeps a free Render server from sleeping mid-game, and the last
// room is remembered so reopening the panel rejoins it.
const PING_MS = 4 * 60_000;
let roomId: string | null = null;
let retries = 0;
let reconnectTimer: number | undefined;
let pingTimer: number | undefined;

function addMessage(user: string, text: string): void {
  const list = $("messages");
  list.append(el("li", {}, el("b", { textContent: `${user}: ` }), text));
  list.scrollTop = list.scrollHeight;
}

function system(text: string): void {
  const list = $("messages");
  list.append(el("li", { class: "muted", textContent: text }));
  list.scrollTop = list.scrollHeight;
}

const inviteLink = (id: string) => `${getApiBase()}/join/${encodeURIComponent(id)}`;

async function copy(text: string, button: HTMLButtonElement): Promise<void> {
  const label = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
  } catch {
    button.textContent = "Copy failed";
  }
  window.setTimeout(() => { button.textContent = label; }, 1500);
}

function renderRoomInfo(users: string[] = []): void {
  if (!roomId) return;
  const id = roomId;
  const copyLink = el("button", { type: "button", textContent: "Copy invite link" });
  copyLink.addEventListener("click", () => copy(inviteLink(id), copyLink));
  const copyCode = el("button", { type: "button", textContent: "Copy code" });
  copyCode.addEventListener("click", () => copy(id, copyCode));
  const leave = el("button", { type: "button", textContent: "Leave" });
  leave.addEventListener("click", () => leaveRoom());
  $("room-info").replaceChildren(
    el("div", {}, "Room ", el("code", { textContent: id }), users.length ? ` · ${users.join(", ")}` : ""),
    el("div", { class: "room-actions" }, copyLink, copyCode, leave),
  );
  $("room-info").hidden = false;
}

function stopSocket(): void {
  window.clearTimeout(reconnectTimer);
  window.clearInterval(pingTimer);
  if (socket) {
    socket.onclose = null; // intentional: don't trigger a reconnect
    socket.close();
    socket = null;
  }
}

function leaveRoom(): void {
  stopSocket();
  roomId = null;
  chrome.storage.local.remove("lastRoom");
  $("room-info").hidden = true;
  $("chat-form").hidden = true;
  system("You left the room.");
}

async function connect(id: string, fresh = true): Promise<void> {
  const name = $<HTMLInputElement>("name-input").value.trim() || "guest";
  await chrome.storage.local.set({ name, lastRoom: id });
  stopSocket();
  if (fresh) { $("messages").replaceChildren(); retries = 0; }
  roomId = id;
  renderRoomInfo();
  $("chat-form").hidden = false;

  const ws = api.roomSocket(id, name);
  socket = ws;
  ws.onopen = () => {
    if (retries > 0) system("Reconnected.");
    retries = 0;
    pingTimer = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
    }, PING_MS);
  };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data) as ServerMessage;
    switch (msg.type) {
      case "history":
        $("messages").replaceChildren(); // avoid duplicates after a reconnect
        msg.messages.forEach((m) => addMessage(m.user, m.text));
        break;
      case "chat": addMessage(msg.user, msg.text); break;
      case "presence": renderRoomInfo(msg.users); break;
      case "error": system(msg.message); break;
    }
  };
  ws.onclose = (ev) => {
    window.clearInterval(pingTimer);
    if (ev.code === 4404) {
      // The server restarted (rooms live in memory) or the code is wrong.
      roomId = null;
      chrome.storage.local.remove("lastRoom");
      $("chat-form").hidden = true;
      $("room-info").hidden = true;
      system("That room no longer exists. Rooms close when the server restarts, so start a new one.");
      return;
    }
    const delay = Math.min(30_000, 1000 * 2 ** retries);
    retries += 1;
    system(`Connection lost. Reconnecting in ${Math.round(delay / 1000)}s…`);
    reconnectTimer = window.setTimeout(() => connect(id, false), delay);
  };
}

async function joinIfOpen(id: string): Promise<boolean> {
  try {
    const r = await fetch(`${getApiBase()}/rooms/${encodeURIComponent(id)}`);
    if (!r.ok) return false;
  } catch {
    return false;
  }
  await connect(id);
  return true;
}

function showChatTab(): void {
  document.querySelector<HTMLButtonElement>('.tabs button[data-tab="chat"]')?.click();
}

// An invite link (…/join/<code>) opened in a tab hands its code to the panel.
async function takePendingInvite(): Promise<void> {
  const { pendingRoom } = await chrome.storage.local.get("pendingRoom");
  if (!pendingRoom || typeof pendingRoom !== "object") return;
  await chrome.storage.local.remove("pendingRoom");
  const { id, server } = pendingRoom as { id: string; server: string };
  if (server && server !== getApiBase()) await switchServer(server);
  showChatTab();
  $<HTMLInputElement>("room-input").value = id;
  if (!(await joinIfOpen(id))) system(`Couldn't join room ${id}. It may have closed.`);
}

$("create-room").addEventListener("click", async () => {
  try {
    const room = await api.createRoom(gameId);
    $<HTMLInputElement>("room-input").value = room.id;
    await connect(room.id);
    system("Room created. Use \"Copy invite link\" to bring friends in.");
  } catch (e) {
    system(`Couldn't create a room: ${(e as Error).message}. Is the server awake?`);
  }
});

$("join-room").addEventListener("click", () => {
  const code = $<HTMLInputElement>("room-input").value.trim();
  if (code) connect(code);
});

$("chat-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const input = $<HTMLInputElement>("chat-input");
  if (socket?.readyState === WebSocket.OPEN && input.value.trim()) {
    socket.send(JSON.stringify({ type: "chat", text: input.value }));
    input.value = "";
  } else if (input.value.trim()) {
    system("Not connected yet. Your message wasn't sent.");
  }
});

// ---------------------------------------------------------------- settings
function showServer(): void {
  $<HTMLInputElement>("server-input").value = getApiBase();
  $("server-status").textContent = `Connected to ${getApiBase()}`;
}

async function switchServer(url: string): Promise<void> {
  await setApiBase(url);
  showServer();
  stopSocket();
  exitReplay(false);
  const current = gameId;
  gameId = null; // force selectGame to reload from the new server
  await loadPicker();
  if (current) selectGame(current);
  try {
    const r = await fetch(`${getApiBase()}/health`);
    $("server-status").textContent = r.ok ? `Connected to ${getApiBase()}` : `Server answered ${r.status}`;
  } catch {
    $("server-status").textContent =
      "Can't reach that server. A free Render server can take about a minute to wake up.";
  }
}

$("server-save").addEventListener("click", () => switchServer($<HTMLInputElement>("server-input").value));
$("server-local").addEventListener("click", () => switchServer(LOCAL_API));
$("server-online").addEventListener("click", () => switchServer(ONLINE_API));

// ---------------------------------------------------------------- boot
chrome.storage.local.get("name").then(({ name }) => {
  if (typeof name === "string") $<HTMLInputElement>("name-input").value = name;
});
chrome.storage.local.onChanged.addListener((changes) => {
  if (changes.pendingRoom?.newValue) takePendingInvite();
});
chrome.storage.session.onChanged.addListener(() => detectFromActiveTab());
chrome.tabs.onActivated.addListener(() => detectFromActiveTab());
$<HTMLInputElement>("date-input").value = localISODate();
loadApiBase()
  .then(() => { showServer(); return loadPicker(); })
  .then(detectFromActiveTab)
  .then(async () => {
    const { pendingRoom, lastRoom } = await chrome.storage.local.get(["pendingRoom", "lastRoom"]);
    if (pendingRoom) return takePendingInvite();
    if (typeof lastRoom === "string" && (await joinIfOpen(lastRoom))) system("Rejoined your last room.");
  });
