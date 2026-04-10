import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LanguageProvider } from "./context/LanguageContext";
import { Toaster } from "./components/ui/sonner";
import BottomNav from "./components/BottomNav";
import HomePage from "./pages/HomePage";
import HistoryPage from "./pages/HistoryPage";
import ProfilePage from "./pages/ProfilePage";

function App() {
  return (
    <LanguageProvider>
      <div className="App min-h-screen bg-[#0A0F1E]">
        <BrowserRouter>
          <main className="safe-area-bottom">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Routes>
          </main>
          <BottomNav />
        </BrowserRouter>
        <Toaster 
          position="top-center"
          toastOptions={{
            style: {
              background: '#111827',
              color: '#F8FAFC',
              border: '1px solid rgba(255,255,255,0.08)',
            },
          }}
        />
      </div>
    </LanguageProvider>
  );
}

export default App;
