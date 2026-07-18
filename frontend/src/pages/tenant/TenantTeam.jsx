import React, { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useTenant } from "./TenantPortal";
import { errText } from "./tenantApi";

const EMPTY = { email: "", name: "", password: "", role: "dispatcher" };

export default function TenantTeam() {
  const { api, me, primary, accent } = useTenant();
  const [users, setUsers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);

  const load = useCallback(() => api.get("/users").then((r) => setUsers(r.data.users)).catch(() => {}), [api]);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    try { await api.post("/users", form); toast.success("User added"); setOpen(false); setForm(EMPTY); load(); }
    catch (e2) { toast.error(errText(e2)); }
  };
  const del = async (id) => { try { await api.delete(`/users/${id}`); load(); } catch (e2) { toast.error(errText(e2)); } };

  return (
    <div data-testid="tenant-team">
      <div className="flex items-center justify-between mb-5">
        <div><h1 className="text-2xl font-black tracking-tight">Team</h1><p className="text-slate-500 text-sm">Admins run everything · dispatchers book loads · viewers are read-only.</p></div>
        <button onClick={() => setOpen(true)} data-testid="tenant-new-user-btn"
                className="px-4 py-2.5 rounded-full font-bold text-black text-sm inline-flex items-center gap-2" style={{ background: primary }}><Plus size={15} /> Add User</button>
      </div>
      {open && (
        <form onSubmit={submit} className="mb-6 p-5 rounded-xl border border-white/10 bg-white/[0.03] grid sm:grid-cols-4 gap-3" data-testid="tenant-user-form">
          <input required placeholder="Name *" value={form.name} data-testid="tenant-user-name-input"
                 onChange={(e) => setForm({ ...form, name: e.target.value })}
                 className="h-10 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none" />
          <input required type="email" placeholder="Email *" value={form.email} data-testid="tenant-user-email-input"
                 onChange={(e) => setForm({ ...form, email: e.target.value })}
                 className="h-10 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none" />
          <input required type="password" placeholder="Password (8+ chars) *" value={form.password} data-testid="tenant-user-password-input"
                 onChange={(e) => setForm({ ...form, password: e.target.value })}
                 className="h-10 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none" />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} data-testid="tenant-user-role-select"
                  className="h-10 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm">
            <option value="admin">admin</option><option value="dispatcher">dispatcher</option><option value="viewer">viewer</option>
          </select>
          <div className="sm:col-span-4 flex gap-2">
            <button type="submit" data-testid="tenant-user-submit" className="px-5 py-2 rounded-full font-bold text-black text-sm" style={{ background: primary }}>Add</button>
            <button type="button" onClick={() => setOpen(false)} className="px-5 py-2 rounded-full border border-white/15 text-sm">Cancel</button>
          </div>
        </form>
      )}
      <div className="rounded-xl border border-white/10 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/10 bg-white/[0.02]">
            <th className="p-3">User</th><th className="p-3">Role</th><th className="p-3">Last login</th><th className="p-3" />
          </tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.user_id} className="border-b border-white/5" data-testid={`tenant-user-row-${u.user_id}`}>
                <td className="p-3"><div className="font-semibold text-slate-200">{u.name}</div><div className="text-[11px] text-slate-500 font-mono">{u.email}</div></td>
                <td className="p-3"><span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border border-white/10" style={{ color: accent }}>{u.role}</span></td>
                <td className="p-3 text-[11px] font-mono text-slate-500">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}</td>
                <td className="p-3">
                  {u.user_id !== me.user_id && (
                    <button onClick={() => del(u.user_id)} data-testid={`tenant-user-delete-${u.user_id}`}
                            className="text-slate-500 hover:text-red-400"><Trash2 size={15} /></button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
