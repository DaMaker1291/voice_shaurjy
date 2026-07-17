'use client';

import React, { useState, useEffect, useCallback } from 'react';

async function safeJson(res: Response): Promise<any> {
  if (!res.ok) return null;
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return null; }
}

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || '';

interface OrgStatus {
  tenant: Record<string, any>;
  organization: { org_id: string; tier: string; limits: Record<string, any> };
  usage: Record<string, any>;
}

interface Seat {
  seat_id: string;
  user_id: string;
  display_name: string;
  email: string;
  role: string;
  team_id: string;
  is_active: boolean;
  last_active_at: number;
}

interface OrgNode {
  node_id: string;
  node_type: string;
  status: string;
  platform: string;
  capabilities: string[];
  last_heartbeat: number;
}

interface PolicyVerdict {
  verdict: string;
  rule_id: string | null;
  description: string | null;
  reason: string;
}

const ROLE_COLORS: Record<string, string> = {
  GLOBAL_ADMIN: '#ff3b3b',
  ORG_ADMIN: '#ff6b35',
  TEAM_LEAD: '#ffd700',
  SYSTEM_ENGINEER: '#00ccff',
  DEVOPS: '#00ff88',
  STANDARD_USER: '#a0a0c0',
  VIEWER: '#666',
  GUEST: '#444',
};

const STATUS_COLORS: Record<string, string> = {
  active: '#00ff88',
  standby: '#ffd700',
  error: '#ff3b3b',
  offline: '#444',
};

const TIER_LABELS: Record<string, string> = {
  free: 'Free',
  pro: 'Pro',
  group: 'Group',
  enterprise: 'Enterprise',
  sovereign: 'Sovereign',
};

export default function EnterpriseCockpit() {
  const [org, setOrg] = useState<OrgStatus | null>(null);
  const [seats, setSeats] = useState<Seat[]>([]);
  const [nodes, setNodes] = useState<OrgNode[]>([]);
  const [policyVerdict, setPolicyVerdict] = useState<PolicyVerdict | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'seats' | 'nodes' | 'policy'>('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('STANDARD_USER');

  const fetchOrg = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/org/status`);
      const data = await safeJson(res);
      if (data.ok) setOrg(data);
    } catch {}
  }, []);

  const fetchSeats = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/org/seats`);
      const data = await safeJson(res);
      if (data.ok) setSeats(data.seats || []);
    } catch {}
  }, []);

  const fetchNodes = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/org/nodes`);
      const data = await safeJson(res);
      if (data.ok) setNodes(data.nodes || []);
    } catch {}
  }, []);

  const evaluatePolicy = useCallback(async (toolName: string, agentDomain: string = 'CORE_AGENT') => {
    try {
      const res = await fetch(`${BACKEND}/api/org/policy/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_domain: agentDomain, tool_name: toolName }),
      });
      const data = await safeJson(res);
      if (data.ok) setPolicyVerdict(data);
    } catch {}
  }, []);

  const inviteSeat = useCallback(async () => {
    if (!inviteEmail) return;
    try {
      const res = await fetch(`${BACKEND}/api/org/seats/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      });
      const data = await safeJson(res);
      if (data.ok) {
        setInviteEmail('');
        fetchSeats();
      }
    } catch {}
  }, [inviteEmail, inviteRole, fetchSeats]);

  useEffect(() => {
    const load = async () => {
      await Promise.all([fetchOrg(), fetchSeats(), fetchNodes()]);
      setLoading(false);
    };
    load();
    const iv = setInterval(load, 15000);
    return () => clearInterval(iv);
  }, [fetchOrg, fetchSeats, fetchNodes]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#0a0a1a', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#00ff88', fontFamily: 'JetBrains Mono, monospace' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⬡</div>
          <div style={{ fontSize: 14 }}>INITIALIZING ENTERPRISE MATRIX...</div>
        </div>
      </div>
    );
  }

  const usage = org?.usage || {};
  const limits = org?.organization?.limits || {};
  const tenant = org?.tenant || {};
  const tier = tenant.org_tier || 'free';

  return (
    <div style={{ minHeight: '100vh', background: '#0a0a1a', color: '#e0e0ff', fontFamily: 'JetBrains Mono, monospace', padding: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32, borderBottom: '1px solid #1a1a3a', paddingBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ fontSize: 32, color: '#00ff88' }}>⬡</div>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#fff' }}>SOVEREIGN ENTERPRISE MATRIX</div>
            <div style={{ fontSize: 12, color: '#666' }}>
              ORG: {tenant.org_id || 'N/A'} • TIER: {TIER_LABELS[tier] || tier} • ROLE: {tenant.role || 'N/A'}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div style={{ padding: '6px 14px', background: '#1a1a3a', borderRadius: 6, fontSize: 11, color: '#00ff88' }}>
            {tenant.identity_hash || 'local'}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24 }}>
        {(['overview', 'seats', 'nodes', 'policy'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 20px', border: 'none', borderRadius: 6, cursor: 'pointer',
              background: activeTab === tab ? '#00ff8822' : '#1a1a2a',
              color: activeTab === tab ? '#00ff88' : '#666',
              fontSize: 12, fontWeight: 600, textTransform: 'uppercase',
              borderBottom: activeTab === tab ? '2px solid #00ff88' : '2px solid transparent',
            }}
          >
            {tab === 'overview' ? '⬡ OVERVIEW' : tab === 'seats' ? '👤 SEATS' : tab === 'nodes' ? '🖥️ NODES' : '🛡️ POLICY'}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
          {/* Tier Card */}
          <div style={{ background: '#12122a', borderRadius: 12, padding: 24, border: '1px solid #1a1a3a' }}>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 8 }}>ORGANIZATION TIER</div>
            <div style={{ fontSize: 36, fontWeight: 700, color: '#00ff88', marginBottom: 4 }}>{TIER_LABELS[tier]}</div>
            <div style={{ fontSize: 11, color: '#666' }}>{tenant.org_name || 'Local Workspace'}</div>
          </div>

          {/* Seats Usage */}
          <div style={{ background: '#12122a', borderRadius: 12, padding: 24, border: '1px solid #1a1a3a' }}>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 8 }}>SEATS</div>
            <div style={{ fontSize: 36, fontWeight: 700, color: '#ffd700' }}>
              {usage.seats?.used || 0}
              <span style={{ fontSize: 16, color: '#666' }}> / {usage.seats?.limit === -1 ? '∞' : usage.seats?.limit || 0}</span>
            </div>
            <div style={{ fontSize: 11, color: '#666' }}>Active seats</div>
          </div>

          {/* Nodes Usage */}
          <div style={{ background: '#12122a', borderRadius: 12, padding: 24, border: '1px solid #1a1a3a' }}>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 8 }}>NODES</div>
            <div style={{ fontSize: 36, fontWeight: 700, color: '#00ccff' }}>
              {usage.nodes?.used || 0}
              <span style={{ fontSize: 16, color: '#666' }}> / {usage.nodes?.limit === -1 ? '∞' : usage.nodes?.limit || 0}</span>
            </div>
            <div style={{ fontSize: 11, color: '#666' }}>Registered nodes</div>
          </div>

          {/* Transactions */}
          <div style={{ background: '#12122a', borderRadius: 12, padding: 24, border: '1px solid #1a1a3a' }}>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 8 }}>TRANSACTIONS</div>
            <div style={{ fontSize: 36, fontWeight: 700, color: '#ff6b35' }}>
              {usage.transactions?.total || 0}
            </div>
            <div style={{ fontSize: 11, color: '#666' }}>
              Daily limit: {usage.transactions?.daily_limit === -1 ? '∞' : usage.transactions?.daily_limit || 0}
            </div>
          </div>

          {/* Storage */}
          <div style={{ background: '#12122a', borderRadius: 12, padding: 24, border: '1px solid #1a1a3a' }}>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 8 }}>STORAGE</div>
            <div style={{ fontSize: 36, fontWeight: 700, color: '#a0a0ff' }}>
              {((usage.storage?.bytes_used || 0) / 1048576).toFixed(1)}
              <span style={{ fontSize: 16, color: '#666' }}> MB / {usage.storage?.mb_limit === -1 ? '∞' : `${usage.storage?.mb_limit || 0} MB`}</span>
            </div>
          </div>

          {/* Scopes */}
          <div style={{ background: '#12122a', borderRadius: 12, padding: 24, border: '1px solid #1a1a3a' }}>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 8 }}>YOUR SCOPES</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
              {(tenant.scopes || []).slice(0, 12).map((s: string, i: number) => (
                <span key={i} style={{ padding: '3px 8px', background: '#00ff8822', borderRadius: 4, fontSize: 10, color: '#00ff88' }}>{s}</span>
              ))}
              {(tenant.scopes || []).length > 12 && (
                <span style={{ padding: '3px 8px', background: '#1a1a3a', borderRadius: 4, fontSize: 10, color: '#666' }}>
                  +{(tenant.scopes || []).length - 12} more
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Seats Tab */}
      {activeTab === 'seats' && (
        <div>
          {/* Invite Form */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
            <input
              value={inviteEmail}
              onChange={e => setInviteEmail(e.target.value)}
              placeholder="user@company.com"
              style={{ flex: 1, padding: '8px 12px', background: '#1a1a2a', border: '1px solid #2a2a4a', borderRadius: 6, color: '#e0e0ff', fontSize: 12, fontFamily: 'inherit' }}
            />
            <select
              value={inviteRole}
              onChange={e => setInviteRole(e.target.value)}
              style={{ padding: '8px 12px', background: '#1a1a2a', border: '1px solid #2a2a4a', borderRadius: 6, color: '#e0e0ff', fontSize: 12, fontFamily: 'inherit' }}
            >
              <option value="STANDARD_USER">Standard User</option>
              <option value="TEAM_LEAD">Team Lead</option>
              <option value="SYSTEM_ENGINEER">System Engineer</option>
              <option value="DEVOPS">DevOps</option>
              <option value="VIEWER">Viewer</option>
            </select>
            <button
              onClick={inviteSeat}
              style={{ padding: '8px 20px', background: '#00ff8822', border: '1px solid #00ff88', borderRadius: 6, color: '#00ff88', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              + INVITE
            </button>
          </div>

          {/* Seats Table */}
          <div style={{ background: '#12122a', borderRadius: 12, overflow: 'hidden', border: '1px solid #1a1a3a' }}>
            {seats.length === 0 ? (
              <div style={{ padding: 40, textAlign: 'center', color: '#666', fontSize: 12 }}>No seats yet</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #1a1a3a' }}>
                    {['SEAT', 'USER', 'ROLE', 'TEAM', 'STATUS', 'LAST ACTIVE'].map(h => (
                      <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: 10, color: '#666', fontWeight: 600 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {seats.map(s => (
                    <tr key={s.seat_id} style={{ borderBottom: '1px solid #0a0a2a' }}>
                      <td style={{ padding: '10px 16px', fontSize: 11, color: '#00ccff' }}>{s.seat_id.slice(0, 16)}...</td>
                      <td style={{ padding: '10px 16px', fontSize: 12, color: '#e0e0ff' }}>{s.display_name || s.user_id}</td>
                      <td style={{ padding: '10px 16px' }}>
                        <span style={{ padding: '3px 8px', background: `${ROLE_COLORS[s.role] || '#666'}22`, borderRadius: 4, fontSize: 10, color: ROLE_COLORS[s.role] || '#666', fontWeight: 600 }}>{s.role}</span>
                      </td>
                      <td style={{ padding: '10px 16px', fontSize: 11, color: '#666' }}>{s.team_id || '—'}</td>
                      <td style={{ padding: '10px 16px' }}>
                        <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: s.is_active ? '#00ff88' : '#ff3b3b', marginRight: 6 }} />
                        <span style={{ fontSize: 11, color: s.is_active ? '#00ff88' : '#ff3b3b' }}>{s.is_active ? 'Active' : 'Inactive'}</span>
                      </td>
                      <td style={{ padding: '10px 16px', fontSize: 11, color: '#666' }}>
                        {s.last_active_at ? new Date(s.last_active_at * 1000).toLocaleString() : 'Never'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Nodes Tab */}
      {activeTab === 'nodes' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
          {nodes.length === 0 ? (
            <div style={{ gridColumn: '1 / -1', padding: 40, textAlign: 'center', color: '#666', fontSize: 12, background: '#12122a', borderRadius: 12 }}>No nodes registered</div>
          ) : (
            nodes.map(n => (
              <div key={n.node_id} style={{ background: '#12122a', borderRadius: 12, padding: 20, border: '1px solid #1a1a3a' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div style={{ fontSize: 12, color: '#00ccff' }}>{n.node_id.slice(0, 16)}...</div>
                  <span style={{ padding: '3px 8px', background: `${STATUS_COLORS[n.status] || '#666'}22`, borderRadius: 4, fontSize: 10, color: STATUS_COLORS[n.status] || '#666' }}>{n.status}</span>
                </div>
                <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>TYPE: {n.node_type} • PLATFORM: {n.platform || 'unknown'}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                  {(n.capabilities || []).map((c, i) => (
                    <span key={i} style={{ padding: '2px 6px', background: '#00ccff22', borderRadius: 3, fontSize: 9, color: '#00ccff' }}>{c}</span>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Policy Tab */}
      {activeTab === 'policy' && (
        <div>
          {/* Quick Evaluate */}
          <div style={{ background: '#12122a', borderRadius: 12, padding: 20, border: '1px solid #1a1a3a', marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#fff', marginBottom: 12 }}>POLICY EVALUATOR</div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <input
                id="policy-tool-input"
                placeholder="Tool name (e.g., DROP TABLE users)"
                style={{ flex: 1, padding: '8px 12px', background: '#1a1a2a', border: '1px solid #2a2a4a', borderRadius: 6, color: '#e0e0ff', fontSize: 12, fontFamily: 'inherit' }}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    const val = (e.target as HTMLInputElement).value;
                    if (val) evaluatePolicy(val);
                  }
                }}
              />
              <button
                onClick={() => {
                  const input = document.getElementById('policy-tool-input') as HTMLInputElement;
                  if (input?.value) evaluatePolicy(input.value);
                }}
                style={{ padding: '8px 20px', background: '#ff3b3b22', border: '1px solid #ff3b3b', borderRadius: 6, color: '#ff3b3b', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
              >
                EVALUATE
              </button>
            </div>
            {policyVerdict && (
              <div style={{
                padding: 12, borderRadius: 8,
                background: policyVerdict.verdict === 'allow' ? '#00ff8811' : '#ff3b3b11',
                border: `1px solid ${policyVerdict.verdict === 'allow' ? '#00ff8844' : '#ff3b3b44'}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 16 }}>{policyVerdict.verdict === 'allow' ? '✅' : '🚫'}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: policyVerdict.verdict === 'allow' ? '#00ff88' : '#ff3b3b' }}>
                    {policyVerdict.verdict.toUpperCase()}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: '#a0a0c0' }}>{policyVerdict.reason}</div>
                {policyVerdict.rule_id && (
                  <div style={{ fontSize: 10, color: '#666', marginTop: 4 }}>RULE: {policyVerdict.rule_id}</div>
                )}
              </div>
            )}
          </div>

          {/* Example Evaluations */}
          <div style={{ fontSize: 12, fontWeight: 600, color: '#fff', marginBottom: 12 }}>QUICK EVALUATIONS</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8 }}>
            {[
              { tool: 'read_file', domain: 'CORE_AGENT', label: 'Read File (Core)' },
              { tool: 'DROP TABLE users', domain: 'CORE_AGENT', label: 'DROP TABLE (Core)' },
              { tool: 'deploy_production', domain: 'INFRA_AGENT', label: 'Deploy (Infra)' },
              { tool: 'shell_exec rm -rf /', domain: 'OS_AGENT', label: 'Shell Exec (OS)' },
              { tool: 'aws_terminate_instance', domain: 'INFRA_AGENT', label: 'Terminate EC2' },
            ].map(ex => (
              <button
                key={ex.tool}
                onClick={() => evaluatePolicy(ex.tool, ex.domain)}
                style={{ padding: '10px 14px', background: '#1a1a2a', border: '1px solid #2a2a4a', borderRadius: 8, color: '#e0e0ff', fontSize: 11, cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit' }}
              >
                <div style={{ color: '#00ccff', marginBottom: 2 }}>{ex.label}</div>
                <div style={{ color: '#666', fontSize: 9 }}>{ex.tool}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
