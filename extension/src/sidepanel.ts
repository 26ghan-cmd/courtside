import { api, type Analysis, type GameDetail, type GameListing, type ServerMessage } from "./api.js";

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
  } catch {
    select.replaceChildren(el("option", { value: "", textContent: "Backend offline — is it running?" }));
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
  gameId = id;
  $<HTMLSelectElement>("game-select").value = id;
  window.clearInterval(pollTimer);
  refresh();
  pollTimer = window.setInterval(refresh, POLL_MS);
}

async function refresh(): Promise<void> {
  if (!gameId) return;
  try {
    const [detail, analysis] = await Promise.all([api.game(gameId), api.analysis(gameId)]);
    renderScorebug(detail.game);
    renderStats(detail);
    renderAnalysis(detail, analysis);
    if (detail.game.status.state === "post") window.clearInterval(pollTimer);
  } catch (e) {
    $("status-text")?.replaceChildren(`Couldn't load game: ${(e as Error).message}`);
  }
}

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
  const labels = ["FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK"];
  const statOf = (tid: string, label: string) =>
    d.team_stats[tid]?.find((s) => s.abbreviation === label || s.label === label)?.value ?? "–";

  const teamTable = el("table", {},
    el("tr", {}, el("th"), el("th", { textContent: away.abbreviation }), el("th", { textContent: home.abbreviation })),
    ...labels.map((l) =>
      el("tr", {}, el("td", { textContent: l }), el("td", { textContent: statOf(away.id, l) }), el("td", { textContent: statOf(home.id, l) })),
    ),
  );

  const playerTable = (teamId: string) => {
    const cols = ["MIN", "PTS", "REB", "AST"];
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
function addMessage(user: string, text: string): void {
  const list = $("messages");
  list.append(el("li", {}, el("b", { textContent: `${user}: ` }), text));
  list.scrollTop = list.scrollHeight;
}

function system(text: string): void {
  $("messages").append(el("li", { class: "muted", textContent: text }));
}

async function connect(roomId: string): Promise<void> {
  const nameInput = $<HTMLInputElement>("name-input");
  const name = nameInput.value.trim() || "guest";
  await chrome.storage.local.set({ name });

  socket?.close();
  $("messages").replaceChildren();
  socket = api.roomSocket(roomId, name);
  socket.onmessage = (ev) => {
    const msg = JSON.parse(ev.data) as ServerMessage;
    switch (msg.type) {
      case "history": msg.messages.forEach((m) => addMessage(m.user, m.text)); break;
      case "chat": addMessage(msg.user, msg.text); break;
      case "presence":
        $("room-info").replaceChildren("Room ", el("code", { textContent: roomId }), ` · ${msg.users.join(", ")}`);
        break;
      case "error": system(msg.message); break;
    }
  };
  socket.onclose = () => system("Disconnected.");
  $("room-info").hidden = false;
  $("chat-form").hidden = false;
}

$("create-room").addEventListener("click", async () => {
  try {
    const room = await api.createRoom(gameId);
    $<HTMLInputElement>("room-input").value = room.id;
    await connect(room.id);
    system(`Share this code with friends: ${room.id}`);
  } catch (e) {
    system(`Couldn't create room: ${(e as Error).message}`);
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
  }
});

// ---------------------------------------------------------------- boot
chrome.storage.local.get("name").then(({ name }) => {
  if (name) $<HTMLInputElement>("name-input").value = name;
});
chrome.storage.session.onChanged.addListener(() => detectFromActiveTab());
chrome.tabs.onActivated.addListener(() => detectFromActiveTab());
$<HTMLInputElement>("date-input").value = localISODate();
loadPicker().then(detectFromActiveTab);
