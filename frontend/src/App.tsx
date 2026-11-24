import { useEffect, useState } from 'react';
import {
  Activity,
  MessageSquareCode,
  PhoneCall,
  PhoneOutgoing,
  Radio,
  Save,
  Server,
  Sparkles,
} from 'lucide-react';

type ChannelMode = 'whatsapp_cloud' | 'sip_trunk' | 'webrtc_web';

interface AgentConfig {
  model: string;
  voice: string;
  active_channel: ChannelMode;
  system_prompt: string;
  enable_crm_tool: boolean;
  enable_booking_tool: boolean;
  enable_human_handoff: boolean;
}

interface CallRecord {
  call_id: string;
  channel: ChannelMode;
  peer: string;
  status: string;
  started_at: number;
}

interface TranscriptEvent {
  call_id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: number;
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws/telemetry';

export function App() {
  const [config, setConfig] = useState<AgentConfig>({
    model: 'gemini-3.8-live',
    voice: 'Aoede',
    active_channel: 'whatsapp_cloud',
    system_prompt:
      'You are Aureum Voice AI, a sharp, natural, low-latency AI voice agent. Speak concisely and handle interruptions naturally.',
    enable_crm_tool: true,
    enable_booking_tool: true,
    enable_human_handoff: true,
  });

  const [wsConnected, setWsConnected] = useState(false);
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [transcripts, setTranscripts] = useState<TranscriptEvent[]>([]);
  const [targetNumber, setTargetNumber] = useState('+15551234567');
  const [statusBanner, setStatusBanner] = useState<string | null>(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'snapshot') {
          if (msg.data?.config) setConfig(msg.data.config);
          if (msg.data?.active_calls) setCalls(msg.data.active_calls);
        } else if (msg.type === 'config_updated') {
          setConfig(msg.data);
        } else if (msg.type === 'call_started') {
          setCalls((prev) => [msg.data, ...prev.filter((c) => c.call_id !== msg.data.call_id)]);
        } else if (msg.type === 'call_ended') {
          setCalls((prev) =>
            prev.map((c) => (c.call_id === msg.data.call_id ? { ...c, status: 'terminated' } : c))
          );
        } else if (msg.type === 'transcript') {
          setTranscripts((prev) => [...prev.slice(-49), { ...msg.data, timestamp: msg.timestamp }]);
        }
      } catch {
        // Ignore malformed telemetry packets
      }
    };
    return () => ws.close();
  }, []);

  const saveConfig = async () => {
    const res = await fetch(`${API_URL}/api/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (res.ok) {
      setStatusBanner('Live agent configuration synced to workers.');
      setTimeout(() => setStatusBanner(null), 3000);
    }
  };

  const triggerOutbound = async () => {
    const channel = config.active_channel === 'webrtc_web' ? 'sip_trunk' : config.active_channel;
    const res = await fetch(`${API_URL}/api/calls/outbound`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_number: targetNumber, channel }),
    });
    if (res.ok) {
      setStatusBanner(`Dispatched outbound ${channel} session to ${targetNumber}`);
      setTimeout(() => setStatusBanner(null), 3500);
    }
  };

  return (
    <div style={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column', background: '#050811' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 28px',
          borderBottom: '1px solid #1e293b',
          background: '#0b1120',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Radio size={22} color="#38bdf8" />
          <div>
            <strong style={{ fontSize: 17 }}>Aureum Voice AI</strong>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>
              Native Speech-to-Speech Engine · Gemini Live + WhatsApp Cloud + SIP Trunk
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {statusBanner && (
            <span style={{ fontSize: 12, color: '#34d399', background: '#064e3b', padding: '6px 12px', borderRadius: 8 }}>
              {statusBanner}
            </span>
          )}
          <span
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              padding: '6px 12px',
              borderRadius: 999,
              background: wsConnected ? 'rgba(52, 211, 153, 0.14)' : 'rgba(248, 113, 113, 0.14)',
              color: wsConnected ? '#34d399' : '#f87171',
            }}
          >
            <Activity size={14} />
            {wsConnected ? 'TELEMETRY LIVE' : 'DISCONNECTED'}
          </span>
        </div>
      </header>

      <main
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: 20,
          padding: 24,
          maxWidth: 1360,
          width: '100%',
          margin: '0 auto',
          boxSizing: 'border-box',
        }}
      >
        {/* Left Column: Channel & Gemini Live Config */}
        <section style={{ background: '#0b1120', border: '1px solid #1e293b', borderRadius: 16, padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700 }}>
            <Sparkles size={16} color="#38bdf8" />
            <span>Voice Engine &amp; Transport Mode</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
            {(
              [
                { id: 'whatsapp_cloud', label: 'WhatsApp Cloud' },
                { id: 'sip_trunk', label: 'Native SIP Trunk' },
                { id: 'webrtc_web', label: 'WebRTC Test' },
              ] as const
            ).map((ch) => (
              <button
                key={ch.id}
                onClick={() => setConfig({ ...config, active_channel: ch.id })}
                style={{
                  padding: '10px 8px',
                  borderRadius: 10,
                  cursor: 'pointer',
                  fontSize: 12,
                  fontWeight: 600,
                  border: config.active_channel === ch.id ? '1px solid #38bdf8' : '1px solid #1e293b',
                  background: config.active_channel === ch.id ? 'rgba(56, 189, 248, 0.15)' : '#0f172a',
                  color: config.active_channel === ch.id ? '#38bdf8' : '#94a3b8',
                }}
              >
                {ch.label}
              </button>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ fontSize: 12, color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: 6 }}>
              Gemini Live Model
              <select
                value={config.model}
                onChange={(e) => setConfig({ ...config, model: e.target.value })}
                style={{ background: '#0f172a', color: '#f8fafc', border: '1px solid #334155', borderRadius: 8, padding: 8 }}
              >
                <option value="gemini-3.8-live">gemini-3.8-live</option>
                <option value="gemini-3.8-live-extended-thinking">gemini-3.8-live-extended-thinking</option>
                <option value="gemini-2.5-flash-native-audio-preview-12-2025">gemini-2.5-flash-native-audio</option>
              </select>
            </label>

            <label style={{ fontSize: 12, color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: 6 }}>
              Native Voice
              <select
                value={config.voice}
                onChange={(e) => setConfig({ ...config, voice: e.target.value })}
                style={{ background: '#0f172a', color: '#f8fafc', border: '1px solid #334155', borderRadius: 8, padding: 8 }}
              >
                {['Aoede', 'Kore', 'Charon', 'Fenrir', 'Puck', 'Callirrhoe'].map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label style={{ fontSize: 12, color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: 6 }}>
            Agent System Instructions
            <textarea
              rows={5}
              value={config.system_prompt}
              onChange={(e) => setConfig({ ...config, system_prompt: e.target.value })}
              style={{ background: '#0f172a', color: '#f8fafc', border: '1px solid #334155', borderRadius: 10, padding: 10, fontFamily: 'inherit', resize: 'vertical' }}
            />
          </label>

          <button
            onClick={() => void saveConfig()}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              padding: '10px 16px',
              borderRadius: 10,
              border: 'none',
              background: '#38bdf8',
              color: '#020617',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            <Save size={16} />
            Sync Live Configuration
          </button>
        </section>

        {/* Middle Column: Outbound Dialer & Active Calls */}
        <section style={{ background: '#0b1120', border: '1px solid #1e293b', borderRadius: 16, padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700 }}>
            <PhoneOutgoing size={16} color="#34d399" />
            <span>Outbound Dialer &amp; Active Sessions</span>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={targetNumber}
              onChange={(e) => setTargetNumber(e.target.value)}
              placeholder="+15551234567"
              style={{ flex: 1, padding: '10px 12px', borderRadius: 10, border: '1px solid #334155', background: '#0f172a', color: '#f8fafc' }}
            />
            <button
              onClick={() => void triggerOutbound()}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '10px 16px',
                borderRadius: 10,
                border: 'none',
                background: '#34d399',
                color: '#020617',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              <PhoneCall size={15} />
              Dial
            </button>
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto', maxHeight: 320 }}>
            {calls.length === 0 ? (
              <div style={{ color: '#64748b', fontSize: 13 }}>
                No active calls yet. Trigger an outbound call or connect via WhatsApp / SIP webhook.
              </div>
            ) : (
              calls.map((c) => (
                <div
                  key={c.call_id}
                  style={{
                    padding: 12,
                    borderRadius: 10,
                    background: '#0f172a',
                    border: '1px solid #1e293b',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: 13,
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{c.peer}</div>
                    <div style={{ fontSize: 11, color: '#94a3b8' }}>
                      {c.channel} · {c.call_id}
                    </div>
                  </div>
                  <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 999, background: '#1e293b', color: '#38bdf8' }}>
                    {c.status.toUpperCase()}
                  </span>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Right Column: Real-Time Transcripts */}
        <section style={{ background: '#0b1120', border: '1px solid #1e293b', borderRadius: 16, padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700 }}>
            <MessageSquareCode size={16} color="#818cf8" />
            <span>Live Audio Transcripts</span>
          </div>

          <div
            style={{
              flex: 1,
              minHeight: 280,
              maxHeight: 380,
              overflowY: 'auto',
              background: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: 12,
              padding: 14,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            {transcripts.length === 0 ? (
              <span style={{ color: '#64748b', fontSize: 13 }}>
                Waiting for live Gemini Audio events over WebSocket...
              </span>
            ) : (
              transcripts.map((t, i) => (
                <div key={i} style={{ fontSize: 13, lineHeight: 1.5 }}>
                  <strong style={{ color: t.role === 'user' ? '#38bdf8' : '#34d399' }}>
                    {t.role === 'user' ? 'Caller' : 'Aureum AI'}:
                  </strong>{' '}
                  <span>{t.text}</span>
                </div>
              ))
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#64748b' }}>
            <Server size={14} />
            <span>Powered by FastAPI + LiveKit SFU/SIP + Gemini Live Native Audio</span>
          </div>
        </section>
      </main>
    </div>
  );
}
