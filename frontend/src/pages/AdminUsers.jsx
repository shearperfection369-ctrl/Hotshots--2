import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Shield, UserPlus, Users } from "lucide-react";
import { useAuth } from "../lib/auth";

const ROLE_BADGE = {
  admin: "bg-red-500/10 text-red-300 border-red-500/30",
  auditor: "bg-purple-500/10 text-purple-300 border-purple-500/30",
  dispatcher: "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
  driver: "bg-yellow-500/10 text-yellow-300 border-yellow-500/30",
};

const ROLES = ["admin", "auditor", "dispatcher", "driver"];

export default function AdminUsers() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/users");
      setUsers(data);
    } catch (e) {
      if (e.response?.status === 403) toast.error("Admin role required to view this page");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const changeRole = async (uid, role) => {
    try {
      await api.post(`/admin/users/${uid}/role`, { role });
      toast.success(`Role updated to ${role}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to change role");
    }
  };

  const seedTeam = async () => {
    try {
      const { data } = await api.post("/admin/seed-team");
      toast.success(`Seeded ${data.inserted} sample team members`);
      load();
    } catch { toast.error("Seed failed"); }
  };

  if (user?.role !== "admin") {
    return (
      <>
        <Topbar title="Admin · Users" subtitle="Access Denied" />
        <div className="p-6">
          <Card className="hud-surface p-8 text-center max-w-md mx-auto">
            <Shield className="w-12 h-12 text-red-400 mx-auto mb-3" />
            <h2 className="font-display text-xl font-bold mb-2">Admin Role Required</h2>
            <p className="text-slate-400 text-sm">This page is reserved for administrators. Your current role is <span className="font-mono text-cyan-400">{user?.role}</span>.</p>
          </Card>
        </div>
      </>
    );
  }

  const roleCounts = users.reduce((acc, u) => { acc[u.role] = (acc[u.role] || 0) + 1; return acc; }, {});

  return (
    <>
      <Topbar title="Admin · Users & Roles" subtitle={`${users.length} users · RBAC management`} />
      <div className="p-4 md:p-6 space-y-5">

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {ROLES.map((r) => (
            <Card key={r} className="hud-surface p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{r}s</div>
              <div className="mt-2 text-2xl font-mono font-bold tabular-nums text-cyan-400">{roleCounts[r] || 0}</div>
            </Card>
          ))}
          <Card className="hud-surface p-3 flex items-center justify-center">
            <Button data-testid="seed-team-btn" onClick={seedTeam} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
              <UserPlus size={14} className="mr-1" /> SEED TEAM
            </Button>
          </Card>
        </div>

        <Card className="hud-surface overflow-hidden">
          <div className="px-5 py-3 border-b border-white/5 flex items-center gap-2">
            <Users size={16} className="text-cyan-400" />
            <h3 className="font-display text-lg font-bold">All Users</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="text-left py-3 px-4">Name</th>
                <th className="text-left py-3 px-4">Email</th>
                <th className="text-left py-3 px-4">User ID</th>
                <th className="text-left py-3 px-4">Current Role</th>
                <th className="text-right py-3 px-4">Change Role</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {users.map((u) => (
                <tr key={u.user_id} className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`user-row-${u.user_id}`}>
                  <td className="py-2.5 px-4 text-white">{u.name}</td>
                  <td className="py-2.5 px-4 text-slate-400">{u.email}</td>
                  <td className="py-2.5 px-4 text-[10px] text-slate-500">{u.user_id}</td>
                  <td className="py-2.5 px-4"><Badge className={`${ROLE_BADGE[u.role] || ROLE_BADGE.dispatcher} font-mono text-[10px] uppercase`}>{u.role}</Badge></td>
                  <td className="py-2.5 px-4 text-right">
                    <Select value={u.role} onValueChange={(v) => changeRole(u.user_id, v)}>
                      <SelectTrigger data-testid={`role-select-${u.user_id}`} className="w-36 ml-auto bg-[#0B0E14] border-white/10 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </td>
                </tr>
              ))}
              {!loading && users.length === 0 && <tr><td colSpan={5} className="text-center py-10 text-slate-500">No users yet.</td></tr>}
            </tbody>
          </table>
        </Card>

        <Card className="hud-surface p-5">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3">RBAC Reference</div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <RoleCard role="admin" desc="Full access · manage users, integrations, all freight & onboarding decisions" color="text-red-300" />
            <RoleCard role="auditor" desc="Freight bills approve/pay/dispute · view all shipments & reports" color="text-purple-300" />
            <RoleCard role="dispatcher" desc="Book loads · manage shipments · generate documents · chat" color="text-cyan-300" />
            <RoleCard role="driver" desc="Mobile check-in only — no dashboard access" color="text-yellow-300" />
          </div>
        </Card>
      </div>
    </>
  );
}

function RoleCard({ role, desc, color }) {
  return (
    <div className="p-4 rounded-md border border-white/5 bg-white/[0.02]">
      <div className={`font-mono text-xs uppercase tracking-widest ${color}`}>{role}</div>
      <div className="text-xs text-slate-400 mt-2 leading-relaxed">{desc}</div>
    </div>
  );
}
