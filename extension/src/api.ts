// Typed wrappers around the Courtside backend. Mirrors backend/app/models.py.

export const API_BASE = "http://localhost:8000";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

export interface Team {
  id: string;
  name: string;
  short_name: string;
  abbreviation: string;
  logo: string | null;
  score: number;
  home: boolean;
}

export interface GameStatus {
  state: "pre" | "in" | "post";
  period: number;
  clock: string;
  detail: string;
}

export interface GameListing {
  id: string;
  name: string;
  start: string;
  status: GameStatus;
  home: Team;
  away: Team;
}

export interface TeamStat { name: string; label: string; value: string }
export interface PlayerLine { team_id: string; name: string; starter: boolean; stats: Record<string, string> }
export interface Play {
  id: string; period: number; clock: string; text: string; team_id: string | null;
  scoring: boolean; score_value: number; home_score: number; away_score: number;
}

export interface GameDetail {
  game: GameListing;
  team_stats: Record<string, TeamStat[]>;
  players: PlayerLine[];
  plays: Play[];
}

export interface Run { team_id: string; points: number; period: number }
export interface Analysis {
  game_id: string;
  lead_changes: number;
  ties: number;
  largest_lead: Record<string, number>;
  runs: Run[];
  shooting: Record<string, { fg_pct: number | null; three_pct: number | null; ft_pct: number | null }>;
  top_scorers: PlayerLine[];
  summary: string;
}

export type ServerMessage =
  | { type: "chat"; user: string; text: string; ts: number }
  | { type: "presence"; users: string[] }
  | { type: "history"; messages: { user: string; text: string; ts: number }[] }
  | { type: "error"; message: string };

async function get<T>(path: string): Promise<T> {
  const r = await fetch(API_BASE + path);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const api = {
  games: (date?: string) => get<GameListing[]>(`/games${date ? `?date=${date}` : ""}`),
  match: (q: string) => get<GameListing | null>(`/games/match?q=${encodeURIComponent(q)}`),
  game: (id: string) => get<GameDetail>(`/games/${id}`),
  analysis: (id: string) => get<Analysis>(`/games/${id}/analysis`),
  async createRoom(gameId: string | null): Promise<{ id: string }> {
    const r = await fetch(`${API_BASE}/rooms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ game_id: gameId }),
    });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  },
  roomSocket: (roomId: string, name: string) =>
    new WebSocket(`${WS_BASE}/rooms/${roomId}/ws?name=${encodeURIComponent(name)}`),
};
