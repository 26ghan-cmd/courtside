# Courtside roadmap: Oct 7, 2026 → March Madness 2027

There are two milestones:

1. **v1.0 on Nov 1, 2026:** a working product with stats, analysis, and text chat.
2. **v2.0 by Selection Sunday (about Mar 14, 2027):** the fully built product, ready for the tournament.
   Code freeze is **Mar 10**. After that, ship only bug fixes until the title game on Apr 5.

Budget: about 5–10 hours a week. Every week or phase finishes with something that works end to end.

---

# Part 1: v1.0 (Oct 7 → Nov 1)

> **Heads-up:** the 2026–27 college basketball season tips off in **early November**, right after the deadline.
> There won't be any live games to test against while you build, so do your development against **finished games
> from last season** (ESPN's summary endpoint still serves them) and use the replay mode from Week 2 to fake a live game.

## Week 1 (Oct 7–11): get it running against real data
- [ ] Get the backend running locally (`uvicorn app.main:app --reload`) and open `/docs`
- [ ] Run `pytest` and fix anything that breaks on your machine
- [ ] Load the extension unpacked in Chrome and pick a game from the dropdown
- [ ] Save 2–3 real ESPN responses into `tests/fixtures/` (from a close game and a blowout) and add tests for them
- [ ] Fix the parsing in `espn.py` anywhere real data differs from the synthetic fixtures
- [ ] Create the GitHub repo and push

**Done when:** the side panel shows correct stats for a real game from last season.

## Week 2 (Oct 12–18): stats panel and stream detection
- [ ] **Replay mode:** add `?at=<play_index>` to `/games/{id}` so it returns the game as it stood at that moment, and add a dev slider to step through it
- [ ] Test stream detection on 2–3 real sites (ESPN, YouTube TV, Peacock) and collect the page titles they use
- [ ] Handle tricky matches: "UConn", "St. John's", "Miami (OH)", and nicknames (add an alias table)
- [ ] Show loading, error, and "backend offline" states
- [ ] Add an extension icon and badge

**Done when:** you open a stream page (or a stand-in page with a realistic title) and the panel picks the right game by itself.

## Week 3 (Oct 19–25): chat rooms for real
- [ ] Deploy the backend (Render, Railway, or Fly.io free tier) with HTTPS/WSS, and make `API_BASE` configurable
- [ ] Shareable room links and copy-to-clipboard for room codes
- [ ] Reconnect automatically after drops and keep the name across sessions
- [ ] Basic abuse limits: rate-limit messages and cap room size
- [ ] Test with 2–3 friends on different machines

**Done when:** you and a friend chat in the same room from two computers.

## Week 4 (Oct 26–Nov 1): analysis and polish
- [ ] Halftime and final recaps (auto-post a recap into the chat at halftime and final)
- [ ] More insights: points off turnovers, bench points, paint points, and per-half shooting splits
- [ ] README with screenshots or a GIF, plus setup instructions
- [ ] Clean up and tag `v1.0.0`
- [ ] **Nov 1: ship it**

---

# Part 2: v2.0 (Nov 2 → Mar 14)

Live games start in November. From then on, test against real games every week.

## Phase A (Nov 2–29): live-season hardening
- [ ] Use Courtside for at least 3 live games and keep a bug log
- [ ] Make polling smarter: poll faster in the last 2 minutes and during close games, and stop at halftime and after the final
- [ ] Add server logging and error reporting (for example Sentry's free tier)
- [ ] Watch for ESPN format changes: add a daily check that fails loudly if parsing breaks
- [ ] Private beta with 5–10 friends, plus a feedback form

**Done when:** a full Saturday of games runs without you touching the server.

## Phase B (Nov 30–Jan 3): voice and video rooms
*This phase covers finals and winter break, so the scope is kept small on purpose.*
- [ ] WebRTC voice in rooms: the backend relays `{"type": "signal"}` messages, with a mesh of up to 4–6 people
- [ ] TURN server for friends behind strict networks (Twilio, Metered, or self-hosted coturn)
- [ ] Mute, push-to-talk, and a speaking indicator
- [ ] Optional video tiles
- [ ] Reactions that fire on scoring plays and show for everyone in the room

**Done when:** you and 3 friends watch a full game together on voice.

## Phase C (Jan 4–31): deeper analysis
- [ ] Build a historical dataset: store play-by-play for every game you poll, and backfill last season
- [ ] **Win-probability model:** logistic regression on score margin, time left, and possession, trained on last season. Show it as a live chart
- [ ] Momentum and "key moment" detection (the biggest swings in win probability)
- [ ] Player trends: season averages compared with tonight, hot and cold streaks
- [ ] LLM-generated halftime and final recaps, with the template summary as the fallback

**Done when:** the Analysis tab shows something about a game that the broadcast didn't say.

## Phase D (Feb 1–28): accounts, social, and distribution
- [ ] Sign in (Google OAuth) with persistent friends and saved rooms
- [ ] "Close game" alerts: notify when a game is within 5 points with under 5 minutes left
- [ ] Move rooms from memory to Redis so the server can restart without losing them
- [ ] **Submit to the Chrome Web Store by Feb 15.** Review can take days or weeks, so leave a buffer
- [ ] Privacy policy page (required for the store listing)

**Done when:** a friend installs Courtside from the Chrome Web Store, not from a zip file.

## Phase E (Mar 1–13): March Madness mode
- [ ] **Bracket view for the new 76-team format:** 12 opening-round games on Tue/Wed, then the 64-team field
- [ ] Multi-game dashboard: every tournament game running at once, with upset alerts when a higher seed is losing late
- [ ] Bracket challenge inside rooms: friends make picks, and a leaderboard updates live
- [ ] Load test: simulate 100+ users in rooms during 16 games at once
- [ ] **Code freeze Mar 10**, then tag `v2.0.0`

**Done when:** you can follow all of opening weekend from the side panel.

## Tournament (Mar 14 → Apr 5)
- Selection Sunday, then the Opening Round (Tue/Wed), first round, ... Final Four in Detroit (Apr 3 and 5)
- Bug fixes only. Keep a list of ideas for next season.

## Ideas parking lot
- Firefox support
- Women's tournament support (the ESPN `womens-college-basketball` endpoints use the same format)
- Mobile companion web app
