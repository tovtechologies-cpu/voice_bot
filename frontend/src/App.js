import React, { useState, useEffect } from "react";
import "@/App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function App() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/health`)
      .then(res => res.json())
      .then(data => { setHealth(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-[#0A0F1E] text-white flex flex-col items-center justify-center p-6">
      <div className="max-w-xl w-full space-y-6">
        {/* Logo */}
        <div className="text-center">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-[#6C63FF] to-[#00D4FF] bg-clip-text text-transparent mb-1">
            ✈️ Travelio
          </h1>
          <p className="text-[#94A3B8]">WhatsApp Travel Booking Agent v4.0</p>
        </div>

        {/* Status */}
        <div className="bg-[#111827] rounded-xl p-5 border border-[rgba(255,255,255,0.08)]">
          <div className="flex items-center gap-3 mb-3">
            <span className={`w-3 h-3 rounded-full ${health?.status === 'healthy' ? 'bg-[#00E5A0]' : 'bg-[#FF4D6D]'}`}></span>
            <span className="font-semibold">Agent Status</span>
          </div>
          {loading ? (
            <p className="text-[#94A3B8]">Checking...</p>
          ) : health ? (
            <p className="text-[#00E5A0]">✅ Online • {health.version}</p>
          ) : (
            <p className="text-[#FF4D6D]">❌ Offline</p>
          )}
        </div>

        {/* How it works */}
        <div className="bg-[#111827] rounded-xl p-5 border border-[rgba(255,255,255,0.08)]">
          <h2 className="font-semibold mb-3">💬 Comment ça marche</h2>
          <ol className="space-y-2 text-[#94A3B8] text-sm">
            <li>1️⃣ Envoyez un message vocal ou texte avec vos plans de voyage</li>
            <li>2️⃣ L'IA analyse et recherche les vols sur Amadeus</li>
            <li>3️⃣ 3 options: 💚 PLUS BAS • ⚡ PLUS RAPIDE • 👑 PREMIUM</li>
            <li>4️⃣ Répondez 1, 2 ou 3 pour sélectionner</li>
            <li>5️⃣ Payez via MTN MoMo</li>
            <li>6️⃣ Recevez votre billet PDF avec QR code</li>
          </ol>
        </div>

        {/* Pricing */}
        <div className="bg-[#111827] rounded-xl p-5 border border-[rgba(255,255,255,0.08)]">
          <h2 className="font-semibold mb-2">💰 Tarification Travelio</h2>
          <p className="text-[#94A3B8] text-sm">
            Prix final = Prix Amadeus + 15€ + 5%<br/>
            Affiché en EUR et XOF (1€ = 655,957 XOF)
          </p>
        </div>

        {/* Webhook */}
        <div className="bg-[#111827] rounded-xl p-5 border border-[rgba(255,255,255,0.08)]">
          <h2 className="font-semibold mb-3">🔗 WhatsApp Webhook</h2>
          <div className="space-y-2 text-sm">
            <div>
              <span className="text-[#94A3B8]">URL:</span>
              <code className="ml-2 text-[#00D4FF]">{BACKEND_URL}/api/webhook</code>
            </div>
            <div>
              <span className="text-[#94A3B8]">Verify Token:</span>
              <code className="ml-2 text-[#00D4FF]">travelio_verify_2024</code>
            </div>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-[#94A3B8] text-xs">
          🌍 Amadeus • Claude AI • MTN MoMo • WhatsApp
        </p>
      </div>
    </div>
  );
}

export default App;
