import React, { useEffect, useState, useMemo, useCallback } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Input } from "../components/ui/input";
import { Trophy, Swords, Crown, Users, Inbox, Send, Sparkles, ArrowLeft, Award, Bot } from "lucide-react";
import { useAuth } from "../lib/auth";
import { toast } from "sonner";
import ChessGame from "../components/ChessGame";
import SoloArcade from "../components/arcade/SoloArcade";

const TIER_BADGE = {
  Rookie: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  Contender: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  Champion: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  Legend: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30",
};

export default function Arcade() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "dispatcher";
  const [tab, setTab] = useState("lobby");
  const [games, setGames] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [tournaments, setTournaments] = useState([]);
  const [challenges, setChallenges] = useState({ inbox: [], outbox: [], pending_count: 0 });
  const [users, setUsers] = useState([]);
  const [activeGame, setActiveGame] = useState(null);
  const [newOpen, setNewOpen] = useState(false);
  const [challengeOpen, setChallengeOpen] = useState(false);
  const [chForm, setChForm] = useState({ opponent_user_id: "", message: "" });
  const [tournamentOpen, setTournamentOpen] = useState(false);
  const [tForm, setTForm] = useState({ name: "", participants: [] });

  const refresh = useCallback(async () => {
    const [g, lb, t, ch, u] = await Promise.all([
      api.get("/arcade/connect4/games"),
      api.get("/arcade/leaderboard"),
      api.get("/arcade/tournaments"),
      api.get("/arcade/challenges"),
      api.get("/arcade/users"),
    ]);
    setGames(g.data); setLeaderboard(lb.data.rows || []); setTournaments(t.data);
    setChallenges(ch.data); setUsers(u.data);
  }, []);
  useEffect(() => { refresh(); const id = setInterval(refresh, 5000); return () => clearInterval(id); }, [refresh]);

  // Active game polling
  useEffect(() => {
    if (!activeGame) return;
    const tick = async () => {
      try {
        const { data } = await api.get(`/arcade/connect4/games/${activeGame.game_id}`);
        setActiveGame(data);
      } catch {}
    };
    const id = setInterval(tick, 1500);
    return () => clearInterval(id);
  }, [activeGame?.game_id]);

  const createOpenGame = async () => {
    try {
      const { data } = await api.post("/arcade/connect4/games", { opponent_email: null });
      toast.success("Created open game — waiting for opponent");
      setNewOpen(false);
      refresh();
      setActiveGame(data);
    } catch (e) { toast.error("Failed"); }
  };

  const sendChallenge = async () => {
    if (!chForm.opponent_user_id) return toast.error("Pick an opponent");
    try {
      await api.post("/arcade/challenges", chForm);
      toast.success("Challenge sent");
      setChallengeOpen(false);
      setChForm({ opponent_user_id: "", message: "" });
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const acceptChallenge = async (cid) => {
    try {
      const { data } = await api.post(`/arcade/challenges/${cid}/accept`);
      toast.success("Accepted — game on!");
      const { data: g } = await api.get(`/arcade/connect4/games/${data.game_id}`);
      setActiveGame(g);
      refresh();
    } catch (e) { toast.error("Failed"); }
  };
  const declineChallenge = async (cid) => {
    try { await api.post(`/arcade/challenges/${cid}/decline`); toast.info("Declined"); refresh(); }
    catch { toast.error("Failed"); }
  };
  const joinGame = async (gid) => {
    try {
      const { data } = await api.post(`/arcade/connect4/games/${gid}/join`);
      toast.success("Joined!");
      setActiveGame(data);
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const dropPiece = async (col) => {
    if (!activeGame) return;
    try {
      const { data } = await api.post(`/arcade/connect4/games/${activeGame.game_id}/move`, { column: col });
      setActiveGame(data);
      if (data.status === "finished") {
        toast.success(`${data.winner_name} wins! 🏆`);
      } else if (data.status === "draw") {
        toast.info("It's a draw");
      }
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Move failed"); }
  };

  const createTournament = async () => {
    if (![4, 8, 16].includes(tForm.participants.length)) {
      return toast.error("Need 4, 8, or 16 participants");
    }
    try {
      await api.post("/arcade/tournaments", { name: tForm.name, participant_user_ids: tForm.participants });
      toast.success("Tournament created");
      setTournamentOpen(false);
      setTForm({ name: "", participants: [] });
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const isMyTurn = useMemo(() => {
    if (!activeGame || activeGame.status !== "active") return false;
    return (activeGame.turn === 1 && activeGame.player1_id === user?.user_id) ||
           (activeGame.turn === 2 && activeGame.player2_id === user?.user_id);
  }, [activeGame, user]);

  // Hero banner stats — must be declared BEFORE the early `activeGame` return
  // so React's hooks rule (consistent call order) is honored.
  const heroStats = useMemo(() => {
    const activeGames = games.filter((g) => g.status === "active").length;
    const liveTourneys = tournaments.filter((t) => t.status !== "completed").length;
    const myRow = leaderboard.find((r) => r.user_id === user?.user_id);
    return {
      activeGames,
      liveTourneys,
      myTrophies: myRow?.trophies || 0,
      myTier: myRow?.tier || "Rookie",
      myRank: myRow ? (leaderboard.findIndex((r) => r.user_id === user?.user_id) + 1) : null,
      totalPlayers: leaderboard.length,
    };
  }, [games, tournaments, leaderboard, user]);

  // --------- Active game view ---------
  if (activeGame) {
    return (
      <>
        <Topbar title={`Connect 4 · ${activeGame.game_id}`} subtitle={`${activeGame.player1_name} vs ${activeGame.player2_name || "(waiting)"} · ${activeGame.status.toUpperCase()}`} />
        <div className="p-4 md:p-6 max-w-5xl mx-auto">
          <button onClick={() => setActiveGame(null)} className="text-cyan-300 hover:text-cyan-200 text-sm font-mono flex items-center gap-1.5 mb-4" data-testid="back-to-arcade">
            <ArrowLeft size={14} /> Back to Arcade
          </button>
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4">
            <Card className="hud-surface p-6">
              <div className="flex items-center justify-between mb-4">
                <PlayerBadge color="red" name={activeGame.player1_name} active={activeGame.turn === 1 && activeGame.status === "active"} />
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{activeGame.status === "active" ? (isMyTurn ? <span className="text-emerald-400">YOUR TURN</span> : "OPPONENT'S TURN") : activeGame.status.toUpperCase()}</div>
                <PlayerBadge color="yellow" name={activeGame.player2_name || "—"} active={activeGame.turn === 2 && activeGame.status === "active"} />
              </div>

              {/* Board */}
              <div className="bg-blue-900/40 p-3 rounded-lg border-4 border-blue-700 max-w-2xl mx-auto" data-testid="c4-board">
                {/* Column buttons */}
                <div className="grid grid-cols-7 gap-2 mb-2">
                  {Array.from({ length: 7 }).map((_, c) => (
                    <button
                      key={c}
                      onClick={() => dropPiece(c)}
                      disabled={!isMyTurn || activeGame.board[0][c] !== 0}
                      data-testid={`c4-drop-${c}`}
                      className="h-6 rounded bg-cyan-500/0 hover:bg-cyan-500/30 transition disabled:opacity-30 disabled:cursor-not-allowed text-cyan-300 text-xs font-mono"
                    >▼</button>
                  ))}
                </div>
                <div className="grid grid-cols-7 gap-2">
                  {activeGame.board.flat().map((cell, idx) => (
                    <div key={idx} className="aspect-square rounded-full bg-blue-950 border-2 border-blue-700 flex items-center justify-center">
                      {cell === 1 && <div className="w-[80%] h-[80%] rounded-full bg-red-500 border-2 border-red-700 shadow-[0_0_8px_rgba(255,59,48,0.5)]" />}
                      {cell === 2 && <div className="w-[80%] h-[80%] rounded-full bg-yellow-400 border-2 border-yellow-600 shadow-[0_0_8px_rgba(255,204,0,0.5)]" />}
                    </div>
                  ))}
                </div>
              </div>

              {activeGame.status === "finished" && (
                <div className="text-center mt-5 p-4 rounded bg-yellow-500/[0.06] border border-yellow-500/30">
                  <Trophy size={32} className="text-yellow-300 mx-auto" />
                  <div className="font-display text-2xl font-bold text-yellow-300 mt-2">{activeGame.winner_name} wins!</div>
                  <div className="text-[10px] font-mono text-emerald-400 mt-1">+1 trophy added to leaderboard</div>
                </div>
              )}
            </Card>

            <Card className="hud-surface p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Match Log</div>
              <div className="space-y-1 max-h-96 overflow-y-auto">
                {(activeGame.moves || []).map((m, i) => (
                  <div key={i} className="text-xs font-mono text-slate-400">
                    <span className={m.player === 1 ? "text-red-400" : "text-yellow-400"}>P{m.player}</span> col {m.col + 1} <span className="text-slate-600">@ {(m.at || "").slice(11, 16)}</span>
                  </div>
                ))}
                {!activeGame.moves?.length && <div className="text-slate-500 text-xs">No moves yet.</div>}
              </div>
            </Card>
          </div>
        </div>
      </>
    );
  }

  // --------- Main lobby/arcade view ---------
  return (
    <>
      <Topbar title="Arcade · Tournaments" subtitle="Play Connect 4 against teammates · earn trophies · climb the leaderboard" />
      <div className="p-4 md:p-6 space-y-4 relative">

        {/* Animated arcade background — subtle gradient orbs */}
        <div aria-hidden className="absolute inset-0 pointer-events-none overflow-hidden -z-0">
          <div className="absolute top-10 -left-20 w-96 h-96 rounded-full bg-cyan-500/[0.06] blur-3xl animate-pulse" style={{ animationDuration: "8s" }} />
          <div className="absolute bottom-10 -right-20 w-96 h-96 rounded-full bg-fuchsia-500/[0.05] blur-3xl animate-pulse" style={{ animationDuration: "10s", animationDelay: "2s" }} />
        </div>

        {/* Hero banner */}
        <Card className="hud-surface relative overflow-hidden border-cyan-500/30" data-testid="arcade-hero">
          <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/[0.08] via-transparent to-fuchsia-500/[0.06]" />
          {/* Pixel-grid background */}
          <div
            className="absolute inset-0 opacity-[0.07]"
            style={{
              backgroundImage: "linear-gradient(rgba(34,211,238,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.4) 1px, transparent 1px)",
              backgroundSize: "24px 24px",
            }}
          />
          <div className="relative p-6 md:p-7 flex flex-col md:flex-row md:items-end gap-5 md:gap-8">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.3em] text-cyan-400 mb-2">
                <Sparkles size={11} /> ARCADE · v2.2 · LIVE
              </div>
              <h1 className="font-display text-3xl md:text-5xl font-black tracking-tighter leading-none">
                <span className="bg-gradient-to-r from-cyan-300 via-cyan-100 to-fuchsia-300 bg-clip-text text-transparent">Lunch-Break</span><br/>
                <span className="text-white">Tournaments</span>
              </h1>
              <p className="mt-3 text-sm text-slate-300 max-w-xl">
                Challenge a teammate · climb the leaderboard · win a trophy · talk a little trash. The dispatcher's break room, on the inside of your TMS.
              </p>
            </div>
            {/* My stats card */}
            <div className="grid grid-cols-3 gap-2 md:gap-3 shrink-0">
              <HeroStat label="My Trophies" value={`${heroStats.myTrophies}`} accent="text-yellow-300" suffix={<Trophy size={11} className="inline ml-1 -mt-0.5 text-yellow-400" />} />
              <HeroStat label="Rank" value={heroStats.myRank ? `#${heroStats.myRank}` : "—"} accent="text-cyan-300" suffix={heroStats.myRank ? <span className="text-[10px] text-slate-500"> / {heroStats.totalPlayers}</span> : null} />
              <HeroStat label="Tier" value={heroStats.myTier} accent="text-fuchsia-300" />
              <HeroStat label="Active Games" value={heroStats.activeGames} accent="text-emerald-300" />
              <HeroStat label="Live Tournaments" value={heroStats.liveTourneys} accent="text-orange-300" />
              <HeroStat label="Total Players" value={heroStats.totalPlayers} accent="text-slate-300" />
            </div>
          </div>
        </Card>

        {/* Top action bar */}
        <Card className="hud-surface p-3 flex flex-wrap items-center gap-2 relative">
          {[
            { id: "lobby", label: "Lobby", Icon: Swords },
            { id: "solo", label: "Solo Arcade", Icon: Sparkles },
            { id: "chess", label: "Chess · Solo", Icon: Bot },
            { id: "challenges", label: `Challenges${challenges.pending_count ? ` (${challenges.pending_count})` : ""}`, Icon: Inbox },
            { id: "leaderboard", label: "Leaderboard", Icon: Trophy },
            { id: "tournaments", label: "Tournaments", Icon: Crown },
          ].map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`arcade-tab-${t.id}`}
              className={`px-3 py-1.5 rounded text-xs font-mono uppercase border flex items-center gap-1.5 ${tab === t.id ? "bg-cyan-500 text-black border-cyan-400" : "border-white/10 text-slate-300 hover:border-cyan-400/40"}`}>
              <t.Icon size={12} /> {t.label}
            </button>
          ))}
          <div className="ml-auto flex gap-2">
            <Button onClick={() => setChallengeOpen(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="new-challenge-btn">
              <Send size={14} className="mr-2" /> Challenge a Teammate
            </Button>
            <Button variant="outline" onClick={() => setNewOpen(true)} data-testid="new-open-game-btn">
              <Swords size={14} className="mr-2" /> Open Lobby Game
            </Button>
            {isAdmin && (
              <Button variant="outline" onClick={() => setTournamentOpen(true)} data-testid="new-tournament-btn">
                <Crown size={14} className="mr-2" /> New Tournament
              </Button>
            )}
          </div>
        </Card>

        {/* Solo arcade tab */}
        {tab === "solo" && <SoloArcade />}

        {/* Chess tab */}
        {tab === "chess" && <ChessGame />}

        {/* Lobby tab */}
        {tab === "lobby" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {games.length === 0 && <Card className="hud-surface p-8 text-center text-slate-500 md:col-span-2">No games. Click "Open Lobby Game" or "Challenge a Teammate" to start.</Card>}
            {games.map((g) => (
              <Card key={g.game_id} className="hud-surface p-4 hover:border-cyan-500/30" data-testid={`game-row-${g.game_id}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-mono text-cyan-300 text-sm">{g.game_id}</div>
                    <div className="text-xs text-slate-400 mt-1">
                      <span className="text-red-400">{g.player1_name}</span> vs <span className="text-yellow-400">{g.player2_name || <span className="text-slate-500 italic">waiting...</span>}</span>
                    </div>
                  </div>
                  <div>
                    {g.status === "open" && g.player1_id !== user?.user_id && (
                      <Button onClick={() => joinGame(g.game_id)} className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold" data-testid={`join-game-${g.game_id}`}>Join</Button>
                    )}
                    {(g.status === "active" || g.status === "open") && (g.player1_id === user?.user_id || g.player2_id === user?.user_id) && (
                      <Button onClick={() => setActiveGame(g)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid={`open-game-${g.game_id}`}>Open</Button>
                    )}
                    {(g.status === "finished" || g.status === "draw") && (
                      <span className="text-xs font-mono text-yellow-400 flex items-center gap-1"><Trophy size={12} /> {g.winner_name || "Draw"}</span>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Challenges tab */}
        {tab === "challenges" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="hud-surface p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-1.5"><Inbox size={11} /> Inbox · Sent to You</div>
              <div className="space-y-2 mt-3">
                {challenges.inbox.length === 0 && <div className="text-slate-500 text-xs">No incoming challenges.</div>}
                {challenges.inbox.map((c) => (
                  <div key={c.challenge_id} className="p-3 rounded border border-white/5 flex items-center justify-between" data-testid={`inbox-${c.challenge_id}`}>
                    <div>
                      <div className="text-sm text-slate-200"><span className="text-cyan-300 font-mono">{c.from_user_name}</span> challenges you to <span className="text-yellow-300">{c.kind}</span></div>
                      {c.message && <div className="text-[11px] text-slate-400 italic mt-0.5">"{c.message}"</div>}
                      <div className="text-[10px] font-mono text-slate-500 mt-0.5">{(c.created_at || "").slice(0, 16)} · {c.status}</div>
                    </div>
                    {c.status === "pending" && (
                      <div className="flex gap-1">
                        <Button size="sm" onClick={() => acceptChallenge(c.challenge_id)} className="h-8 bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-[10px]" data-testid={`accept-${c.challenge_id}`}>Accept</Button>
                        <Button size="sm" variant="outline" onClick={() => declineChallenge(c.challenge_id)} className="h-8 border-red-500/40 text-red-400 text-[10px]" data-testid={`decline-${c.challenge_id}`}>Decline</Button>
                      </div>
                    )}
                    {c.status === "accepted" && c.game_id && (
                      <Button size="sm" onClick={() => api.get(`/arcade/connect4/games/${c.game_id}`).then(({ data }) => setActiveGame(data))} className="h-8 bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-[10px]">Open</Button>
                    )}
                  </div>
                ))}
              </div>
            </Card>
            <Card className="hud-surface p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-1.5"><Send size={11} /> Outbox · Sent by You</div>
              <div className="space-y-2 mt-3">
                {challenges.outbox.length === 0 && <div className="text-slate-500 text-xs">No outgoing challenges yet.</div>}
                {challenges.outbox.map((c) => (
                  <div key={c.challenge_id} className="p-3 rounded border border-white/5 flex items-center justify-between">
                    <div>
                      <div className="text-sm text-slate-200">To <span className="text-cyan-300 font-mono">{c.to_user_name}</span> · {c.kind}</div>
                      <div className="text-[10px] font-mono text-slate-500 mt-0.5">{(c.created_at || "").slice(0, 16)}</div>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${c.status === "pending" ? "bg-yellow-500/10 text-yellow-300 border-yellow-500/30" : c.status === "accepted" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30" : "bg-slate-500/10 text-slate-400 border-slate-500/30"}`}>{c.status}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {/* Leaderboard tab */}
        {tab === "leaderboard" && (
          <Card className="hud-surface overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[#0B0E14] text-[10px] font-mono text-cyan-400 uppercase tracking-wider">
                <tr>
                  <th className="text-left py-3 px-4">Rank</th>
                  <th className="text-left py-3 px-4">Player</th>
                  <th className="text-center py-3 px-4">Tier</th>
                  <th className="text-right py-3 px-4">Trophies</th>
                  <th className="text-right py-3 px-4">Tournaments</th>
                  <th className="text-right py-3 px-4">Wins</th>
                  <th className="text-right py-3 px-4">Losses</th>
                  <th className="text-right py-3 px-4">Draws</th>
                  <th className="text-right py-3 px-4">Win %</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {leaderboard.map((r, i) => (
                  <tr key={r.user_id}
                    className={`border-t border-white/5 hover:bg-white/[0.02] transition ${
                      r.user_id === user?.user_id ? "bg-cyan-500/[0.06] ring-1 ring-inset ring-cyan-500/30" : ""
                    } ${i === 0 ? "bg-gradient-to-r from-yellow-500/[0.06] to-transparent" : ""}`}
                    data-testid={`leaderboard-row-${r.user_id}`}>
                    <td className="py-2.5 px-4">
                      {i === 0 ? <span className="text-2xl drop-shadow-[0_0_8px_rgba(234,179,8,0.6)]">🥇</span> : i === 1 ? <span className="text-2xl">🥈</span> : i === 2 ? <span className="text-2xl">🥉</span> : <span className="text-slate-400">{i + 1}</span>}
                    </td>
                    <td className="py-2.5 px-4 text-cyan-300">{r.name} {r.user_id === user?.user_id && <span className="text-[9px] text-emerald-400 ml-1">(you)</span>}</td>
                    <td className="py-2.5 px-4 text-center"><span className={`px-2 py-0.5 rounded border text-[10px] font-mono uppercase ${TIER_BADGE[r.tier]}`}>{r.tier}</span></td>
                    <td className="py-2.5 px-4 text-right text-yellow-400 font-bold">{r.trophies || 0} 🏆</td>
                    <td className="py-2.5 px-4 text-right text-fuchsia-300">{r.tournaments_won || 0}</td>
                    <td className="py-2.5 px-4 text-right text-emerald-400">{r.wins}</td>
                    <td className="py-2.5 px-4 text-right text-red-400">{r.losses}</td>
                    <td className="py-2.5 px-4 text-right text-slate-300">{r.draws || 0}</td>
                    <td className="py-2.5 px-4 text-right text-cyan-300">{r.games ? Math.round((r.wins / r.games) * 100) : 0}%</td>
                  </tr>
                ))}
                {leaderboard.length === 0 && (<tr><td colSpan={9} className="text-center py-12 text-slate-500">No matches played yet. Start a game!</td></tr>)}
              </tbody>
            </table>
          </Card>
        )}

        {/* Tournaments tab */}
        {tab === "tournaments" && (
          <div className="space-y-3">
            {tournaments.length === 0 && <Card className="hud-surface p-8 text-center text-slate-500">No tournaments. {isAdmin && "Click 'New Tournament' to create one."}</Card>}
            {tournaments.map((t) => (
              <Card key={t.tournament_id} className="hud-surface p-4" data-testid={`tournament-${t.tournament_id}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-display text-lg font-bold flex items-center gap-2">
                      {t.status === "completed" && <Crown size={16} className="text-yellow-400" />}
                      {t.name}
                    </div>
                    <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{t.tournament_id} · {t.participants.length} players · {t.status}</div>
                  </div>
                  {t.champion_name && (
                    <div className="text-right">
                      <div className="text-[10px] font-mono uppercase text-yellow-400">Champion</div>
                      <div className="text-lg text-yellow-300 font-bold">{t.champion_name} 👑</div>
                    </div>
                  )}
                </div>
                <div className="grid gap-3 mt-3" style={{ gridTemplateColumns: `repeat(${t.bracket.length}, minmax(0, 1fr))` }}>
                  {t.bracket.map((rnd, ri) => (
                    <div key={ri}>
                      <div className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 mb-2">Round {rnd.round}</div>
                      <div className="space-y-2">
                        {rnd.matches.map((m) => (
                          <button key={m.match_id} onClick={() => m.game_id && api.get(`/arcade/connect4/games/${m.game_id}`).then(({ data }) => setActiveGame(data)).catch(() => {})}
                            className="w-full text-left p-2 rounded border border-white/5 bg-white/[0.02] hover:border-cyan-500/30 text-xs">
                            <div className={`flex items-center justify-between ${m.winner_id === m.p1_id ? "text-emerald-400" : "text-slate-300"}`}>
                              <span>{m.p1_name || "TBD"}</span>
                              {m.winner_id === m.p1_id && <Award size={10} />}
                            </div>
                            <div className="text-[9px] text-slate-600">vs</div>
                            <div className={`flex items-center justify-between ${m.winner_id === m.p2_id ? "text-emerald-400" : "text-slate-300"}`}>
                              <span>{m.p2_name || "TBD"}</span>
                              {m.winner_id === m.p2_id && <Award size={10} />}
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* New game */}
      <Dialog open={newOpen} onOpenChange={setNewOpen}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-md" data-testid="new-game-dialog">
          <DialogHeader><DialogTitle className="font-display text-cyan-300 flex items-center gap-2"><Swords size={16} /> Open Lobby Game</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-300">Creates an open game any teammate can join from the lobby.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNewOpen(false)}>Cancel</Button>
            <Button onClick={createOpenGame} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="confirm-open-game">Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Challenge */}
      <Dialog open={challengeOpen} onOpenChange={setChallengeOpen}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-md" data-testid="challenge-dialog">
          <DialogHeader><DialogTitle className="font-display text-cyan-300 flex items-center gap-2"><Send size={16} /> Challenge a Teammate</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-mono uppercase text-cyan-400">Opponent</label>
              <Select value={chForm.opponent_user_id} onValueChange={(v) => setChForm({ ...chForm, opponent_user_id: v })}>
                <SelectTrigger className="mt-1 bg-[#0B0E14] border-white/10" data-testid="challenge-opponent"><SelectValue placeholder="Select user..." /></SelectTrigger>
                <SelectContent className="max-h-64">
                  {users.filter((u) => u.user_id !== user?.user_id).map((u) => (
                    <SelectItem key={u.user_id} value={u.user_id}>{u.name} <span className="text-slate-500 ml-1">· {u.role}</span></SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase text-cyan-400">Trash Talk (optional)</label>
              <Input value={chForm.message} onChange={(e) => setChForm({ ...chForm, message: e.target.value })} placeholder="Bet you can't beat me 😎" className="mt-1 bg-[#0B0E14] border-white/10" data-testid="challenge-message" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setChallengeOpen(false)}>Cancel</Button>
            <Button onClick={sendChallenge} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="send-challenge-btn">Send Challenge</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Tournament */}
      <Dialog open={tournamentOpen} onOpenChange={setTournamentOpen}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-md" data-testid="tournament-dialog">
          <DialogHeader><DialogTitle className="font-display text-cyan-300 flex items-center gap-2"><Crown size={16} /> Create Tournament</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-mono uppercase text-cyan-400">Name</label>
              <Input value={tForm.name} onChange={(e) => setTForm({ ...tForm, name: e.target.value })} placeholder="Q2 2026 Logistics Cup" className="mt-1 bg-[#0B0E14] border-white/10" data-testid="tournament-name" />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase text-cyan-400">Participants ({tForm.participants.length} — pick 4 / 8 / 16)</label>
              <div className="max-h-64 overflow-y-auto mt-1 border border-white/10 rounded p-2 bg-[#0B0E14] space-y-1">
                {users.map((u) => {
                  const selected = tForm.participants.includes(u.user_id);
                  return (
                    <label key={u.user_id} className="flex items-center gap-2 p-1.5 rounded hover:bg-white/[0.04] cursor-pointer">
                      <input type="checkbox" checked={selected} onChange={() => setTForm({ ...tForm, participants: selected ? tForm.participants.filter((x) => x !== u.user_id) : [...tForm.participants, u.user_id] })} className="accent-cyan-500" />
                      <span className="text-sm text-slate-200">{u.name}</span>
                      <span className="text-[10px] text-slate-500">· {u.role}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTournamentOpen(false)}>Cancel</Button>
            <Button onClick={createTournament} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="create-tournament-btn">Create Bracket</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function PlayerBadge({ color, name, active }) {
  const dot = color === "red" ? "bg-red-500" : "bg-yellow-400";
  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded border ${active ? "border-cyan-400 bg-cyan-500/[0.06]" : "border-white/10"}`}>
      <span className={`w-3 h-3 rounded-full ${dot} ${active ? "animate-pulse" : ""}`} />
      <span className="text-sm font-mono">{name}</span>
    </div>
  );
}

function HeroStat({ label, value, accent = "text-cyan-300", suffix = null }) {
  return (
    <div className="px-3 py-2 rounded bg-black/40 border border-white/5 backdrop-blur min-w-[100px]">
      <div className="text-[9px] font-mono uppercase tracking-[0.18em] text-slate-500 mb-0.5">{label}</div>
      <div className={`font-display text-xl md:text-2xl font-black tabular-nums leading-none ${accent}`}>
        {value}{suffix}
      </div>
    </div>
  );
}
