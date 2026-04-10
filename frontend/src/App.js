import React, { useState, useEffect } from "react";
import "@/App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function App() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/health`)
      .then(res => res.json())
      .then(data => {
        setHealth(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="min-h-screen bg-[#0A0F1E] text-white flex flex-col items-center justify-center p-8">
      <div className="max-w-2xl w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-[#6C63FF] to-[#00D4FF] bg-clip-text text-transparent mb-2">
            ✈️ Travelio
          </h1>
          <p className="text-[#94A3B8] text-lg">WhatsApp Travel Booking Agent</p>
        </div>

        {/* Status Card */}
        <div className="bg-[#111827] rounded-2xl p-6 border border-[rgba(255,255,255,0.08)] mb-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${health?.status === 'healthy' ? 'bg-[#00E5A0]' : 'bg-[#FF4D6D]'}`}></span>
            Agent Status
          </h2>
          {loading ? (
            <p className="text-[#94A3B8]">Checking...</p>
          ) : health ? (
            <div className="space-y-2 text-[#94A3B8]">
              <p>✅ Backend: <span className="text-[#00E5A0]">Online</span></p>
              <p>📱 Type: <span className="text-white">{health.type || 'WhatsApp Agent'}</span></p>
              <p>🔄 Version: <span className="text-white">3.0.0</span></p>
            </div>
          ) : (
            <p className="text-[#FF4D6D]">❌ Backend offline</p>
          )}
        </div>

        {/* How it works */}
        <div className="bg-[#111827] rounded-2xl p-6 border border-[rgba(255,255,255,0.08)] mb-6">
          <h2 className="text-xl font-semibold mb-4">💬 How It Works</h2>
          <p className="text-[#94A3B8] mb-4">
            Travelio is a <span className="text-white">WhatsApp-only</span> travel booking agent. 
            The entire journey happens inside your WhatsApp chat:
          </p>
          <ol className="space-y-3 text-[#94A3B8]">
            <li className="flex gap-3">
              <span className="text-[#6C63FF] font-bold">1.</span>
              <span>Send a voice or text message with your travel plans</span>
            </li>
            <li className="flex gap-3">
              <span className="text-[#6C63FF] font-bold">2.</span>
              <span>AI parses your intent and searches for flights</span>
            </li>
            <li className="flex gap-3">
              <span className="text-[#6C63FF] font-bold">3.</span>
              <span>Choose from 3 flight options (ECO / FAST / PREMIUM)</span>
            </li>
            <li className="flex gap-3">
              <span className="text-[#6C63FF] font-bold">4.</span>
              <span>Pay instantly via MTN MoMo</span>
            </li>
            <li className="flex gap-3">
              <span className="text-[#6C63FF] font-bold">5.</span>
              <span>Receive your PDF ticket with QR code in the same chat</span>
            </li>
          </ol>
        </div>

        {/* Webhook Info */}
        <div className="bg-[#111827] rounded-2xl p-6 border border-[rgba(255,255,255,0.08)] mb-6">
          <h2 className="text-xl font-semibold mb-4">🔗 WhatsApp Webhook Setup</h2>
          <div className="space-y-3">
            <div>
              <p className="text-[#94A3B8] text-sm mb-1">Webhook URL:</p>
              <code className="block bg-[#0A0F1E] p-3 rounded-lg text-[#00D4FF] text-sm break-all">
                {BACKEND_URL}/api/webhook
              </code>
            </div>
            <div>
              <p className="text-[#94A3B8] text-sm mb-1">Verify Token:</p>
              <code className="block bg-[#0A0F1E] p-3 rounded-lg text-[#00D4FF] text-sm">
                travelio_verify_2024
              </code>
            </div>
            <p className="text-[#94A3B8] text-xs mt-2">
              Configure these in your Meta Developer Console → WhatsApp → Configuration
            </p>
          </div>
        </div>

        {/* Destinations */}
        <div className="bg-[#111827] rounded-2xl p-6 border border-[rgba(255,255,255,0.08)]">
          <h2 className="text-xl font-semibold mb-4">🌍 Supported Destinations</h2>
          <div className="grid grid-cols-2 gap-2 text-[#94A3B8]">
            <span>🇸🇳 Dakar</span>
            <span>🇳🇬 Lagos</span>
            <span>🇬🇭 Accra</span>
            <span>🇨🇮 Abidjan</span>
            <span>🇧🇫 Ouagadougou</span>
            <span>🇲🇱 Bamako</span>
            <span>🇬🇳 Conakry</span>
            <span>🇳🇪 Niamey</span>
            <span>🇧🇯 Cotonou</span>
            <span>🇹🇬 Lomé</span>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-8 text-[#94A3B8] text-sm">
          <p>Built for West African travelers 🌍</p>
          <p className="mt-1">Voice-first • Bilingual (FR/EN) • MoMo payments</p>
        </div>
      </div>
    </div>
  );
}

export default App;
