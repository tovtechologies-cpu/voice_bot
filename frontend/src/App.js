import React, { useState, useEffect } from "react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const STATUS_CONFIG = {
  configured: { icon: "check-circle", color: "#00E5A0", bg: "rgba(0,229,160,0.08)", label: "Active" },
  sandbox: { icon: "flask", color: "#FBBF24", bg: "rgba(251,191,36,0.08)", label: "Sandbox" },
  missing: { icon: "times-circle", color: "#FF4D6D", bg: "rgba(255,77,109,0.08)", label: "Missing" },
};

const OPERATOR_META = {
  mtn_momo: { name: "MTN MoMo", icon: "mobile-alt", desc: "Mobile Money" },
  moov_money: { name: "Moov Money", icon: "money-bill-wave", desc: "Flooz" },
  google_pay: { name: "Google Pay", icon: "credit-card", desc: "via Stripe" },
  apple_pay: { name: "Apple Pay", icon: "apple-alt", desc: "via Stripe" },
};

const INTEGRATION_META = {
  claude_ai: { name: "Claude AI", icon: "brain", desc: "Intent parsing" },
  amadeus: { name: "Amadeus", icon: "plane", desc: "Flight search" },
  whatsapp: { name: "WhatsApp", icon: "comment-dots", desc: "Messaging" },
  whisper: { name: "Whisper", icon: "microphone", desc: "Voice transcription" },
};

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.missing;
  return (
    <span
      data-testid={`status-badge-${status}`}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
      style={{ background: cfg.bg, color: cfg.color }}
    >
      <i className={`fas fa-${cfg.icon} text-[10px]`}></i>
      {cfg.label}
    </span>
  );
}

function OperatorCard({ id, operator, status }) {
  const meta = OPERATOR_META[id] || { name: id, icon: "question", desc: "" };
  const statusCfg = STATUS_CONFIG[status?.status] || STATUS_CONFIG.missing;

  return (
    <div
      data-testid={`operator-card-${id}`}
      className="flex items-center justify-between p-3.5 rounded-xl border transition-colors"
      style={{
        background: "rgba(255,255,255,0.02)",
        borderColor: `${statusCfg.color}22`,
      }}
    >
      <div className="flex items-center gap-3">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center text-sm"
          style={{ background: statusCfg.bg, color: statusCfg.color }}
        >
          <i className={`fas fa-${meta.icon}`}></i>
        </div>
        <div>
          <p className="text-sm font-medium text-white">{meta.name}</p>
          <p className="text-xs text-[#64748B]">{meta.desc}</p>
        </div>
      </div>
      <StatusBadge status={status?.status || "missing"} />
    </div>
  );
}

function IntegrationRow({ id, status }) {
  const meta = INTEGRATION_META[id] || { name: id, icon: "plug", desc: "" };
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.missing;

  return (
    <div
      data-testid={`integration-${id}`}
      className="flex items-center justify-between py-2.5"
    >
      <div className="flex items-center gap-2.5">
        <i className={`fas fa-${meta.icon} text-xs`} style={{ color: cfg.color }}></i>
        <span className="text-sm text-[#CBD5E1]">{meta.name}</span>
        <span className="text-xs text-[#475569]">{meta.desc}</span>
      </div>
      <StatusBadge status={status} />
    </div>
  );
}

function App() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/health`)
      .then((res) => res.json())
      .then((data) => {
        setHealth(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  const operators = health?.payment_operators || {};
  const integrations = health?.integrations || {};

  return (
    <div className="min-h-screen bg-[#060A14] text-white">
      <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"
      />

      <div className="max-w-lg mx-auto px-5 py-10 space-y-6">
        {/* Header */}
        <header className="text-left" data-testid="app-header">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-2xl">✈️</span>
            <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-[#6C63FF] to-[#00D4FF] bg-clip-text text-transparent">
              Travelio
            </h1>
          </div>
          <p className="text-[#64748B] text-sm">
            WhatsApp Travel Booking Agent
          </p>
        </header>

        {/* Agent Status */}
        <section
          data-testid="agent-status-card"
          className="rounded-2xl p-5 border border-[rgba(255,255,255,0.06)]"
          style={{ background: "linear-gradient(135deg, #0F172A 0%, #0C1220 100%)" }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`w-2.5 h-2.5 rounded-full ${
                  loading
                    ? "bg-[#FBBF24] animate-pulse"
                    : health?.status === "healthy"
                    ? "bg-[#00E5A0]"
                    : "bg-[#FF4D6D]"
                }`}
              ></div>
              <div>
                <p className="text-sm font-semibold">
                  {loading
                    ? "Checking..."
                    : error
                    ? "Agent Offline"
                    : "Agent Online"}
                </p>
                {health && (
                  <p className="text-xs text-[#64748B]">v{health.version}</p>
                )}
              </div>
            </div>
            {health && (
              <span className="text-xs text-[#64748B] bg-[rgba(255,255,255,0.04)] px-2.5 py-1 rounded-md">
                {health.type}
              </span>
            )}
          </div>
        </section>

        {/* Payment Operators */}
        {!loading && health && (
          <section data-testid="payment-operators-section">
            <h2 className="text-sm font-semibold text-[#94A3B8] uppercase tracking-wider mb-3">
              Payment Methods
            </h2>
            <div className="space-y-2">
              {Object.entries(operators).map(([id, status]) => (
                <OperatorCard key={id} id={id} status={status} />
              ))}
            </div>
          </section>
        )}

        {/* Integrations */}
        {!loading && health && (
          <section
            data-testid="integrations-section"
            className="rounded-2xl p-5 border border-[rgba(255,255,255,0.06)]"
            style={{ background: "#0F172A" }}
          >
            <h2 className="text-sm font-semibold text-[#94A3B8] uppercase tracking-wider mb-3">
              Integrations
            </h2>
            <div className="divide-y divide-[rgba(255,255,255,0.04)]">
              {Object.entries(integrations).map(([id, status]) => (
                <IntegrationRow key={id} id={id} status={status} />
              ))}
            </div>
          </section>
        )}

        {/* How it works */}
        <section
          data-testid="how-it-works-section"
          className="rounded-2xl p-5 border border-[rgba(255,255,255,0.06)]"
          style={{ background: "#0F172A" }}
        >
          <h2 className="text-sm font-semibold text-[#94A3B8] uppercase tracking-wider mb-3">
            How It Works
          </h2>
          <div className="space-y-3">
            {[
              { step: "1", icon: "comment-dots", text: "Send a voice or text message with your travel plans" },
              { step: "2", icon: "search", text: "AI parses your intent and searches Amadeus flights" },
              { step: "3", icon: "list-ol", text: "3 curated options: Cheapest, Fastest, Premium" },
              { step: "4", icon: "hand-pointer", text: "Reply 1, 2, or 3 to select your flight" },
              { step: "5", icon: "wallet", text: "Pay via MoMo, Moov, Google Pay, or Apple Pay" },
              { step: "6", icon: "ticket-alt", text: "Receive your PDF ticket with QR code" },
            ].map((item) => (
              <div key={item.step} className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-md bg-[rgba(108,99,255,0.1)] flex items-center justify-center flex-shrink-0 mt-0.5">
                  <i className={`fas fa-${item.icon} text-[11px] text-[#6C63FF]`}></i>
                </div>
                <p className="text-sm text-[#CBD5E1] leading-relaxed">{item.text}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Webhook Info */}
        <section
          data-testid="webhook-section"
          className="rounded-2xl p-5 border border-[rgba(255,255,255,0.06)]"
          style={{ background: "#0F172A" }}
        >
          <h2 className="text-sm font-semibold text-[#94A3B8] uppercase tracking-wider mb-3">
            Webhook Configuration
          </h2>
          <div className="space-y-2.5 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-[#64748B]">Endpoint</span>
              <code className="text-[#00D4FF] text-xs bg-[rgba(0,212,255,0.06)] px-2 py-0.5 rounded">
                {BACKEND_URL}/api/webhook
              </code>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#64748B]">Verify Token</span>
              <code className="text-[#00D4FF] text-xs bg-[rgba(0,212,255,0.06)] px-2 py-0.5 rounded">
                travelio_verify_2024
              </code>
            </div>
          </div>
        </section>

        {/* Pricing */}
        <section
          data-testid="pricing-section"
          className="rounded-2xl p-5 border border-[rgba(255,255,255,0.06)]"
          style={{ background: "#0F172A" }}
        >
          <h2 className="text-sm font-semibold text-[#94A3B8] uppercase tracking-wider mb-3">
            Pricing Rule
          </h2>
          <div className="bg-[rgba(108,99,255,0.06)] rounded-lg p-3">
            <code className="text-xs text-[#A78BFA] block">
              final_price = amadeus_price + 15€ + 5%
            </code>
            <p className="text-xs text-[#64748B] mt-1.5">
              Displayed in EUR and XOF (1€ = 655.957 XOF)
            </p>
          </div>
        </section>

        {/* Footer */}
        <footer className="text-center pt-2 pb-4">
          <p className="text-[#334155] text-xs">
            Amadeus · Claude AI · Stripe · WhatsApp Cloud API
          </p>
        </footer>
      </div>
    </div>
  );
}

export default App;
