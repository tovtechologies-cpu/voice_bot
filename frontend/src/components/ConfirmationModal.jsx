import React, { useState, useEffect } from 'react';
import { Check, MessageCircle, Download, Sparkles, X } from 'lucide-react';
import { sendWhatsAppTicket } from '../api';

const ConfirmationModal = ({ isOpen, onClose, booking, userPhone, t }) => {
  const [showConfetti, setShowConfetti] = useState(false);
  const [whatsAppSent, setWhatsAppSent] = useState(false);
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setShowConfetti(true);
      const timer = setTimeout(() => setShowConfetti(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  if (!isOpen || !booking) return null;

  const handleSendWhatsApp = async () => {
    if (!userPhone) {
      alert(t('enterPhone'));
      return;
    }
    
    setIsSending(true);
    try {
      await sendWhatsAppTicket(userPhone, booking.id);
      setWhatsAppSent(true);
    } catch (err) {
      console.error('WhatsApp send failed:', err);
    } finally {
      setIsSending(false);
    }
  };

  const handleDownloadPDF = () => {
    // Create a simple text-based ticket (in real app, would generate PDF)
    const ticketContent = `
TRAVELIO TICKET
================
Booking Reference: ${booking.qr_code}

Flight: ${booking.flight_number}
Airline: ${booking.airline}
Route: ${booking.origin} → ${booking.destination}
Departure: ${new Date(booking.departure_time).toLocaleString()}
Arrival: ${new Date(booking.arrival_time).toLocaleString()}

Passengers: ${booking.passengers}
Total Price: ${booking.price.toLocaleString()} ${booking.currency}

Status: ${booking.status.toUpperCase()}
Payment: ${booking.payment_status.toUpperCase()}

Thank you for choosing Travelio!
    `;

    const blob = new Blob([ticketContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `travelio-ticket-${booking.qr_code}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      {/* Confetti Animation */}
      {showConfetti && (
        <div className="fixed inset-0 pointer-events-none overflow-hidden">
          {[...Array(50)].map((_, i) => (
            <div
              key={i}
              className="absolute w-2 h-2 rounded-full"
              style={{
                left: `${Math.random() * 100}%`,
                top: '-10px',
                backgroundColor: ['#6C63FF', '#00D4FF', '#00E5A0', '#FFCC00'][Math.floor(Math.random() * 4)],
                animation: `confetti ${2 + Math.random() * 2}s linear forwards`,
                animationDelay: `${Math.random() * 0.5}s`,
              }}
            />
          ))}
        </div>
      )}

      <div 
        className="glass-card w-full max-w-md mx-4 rounded-2xl overflow-hidden animate-[fadeSlideUp_0.3s_ease]"
        data-testid="confirmation-modal"
      >
        {/* Header */}
        <div className="relative p-6 text-center bg-gradient-to-br from-[#6C63FF]/20 to-[#00D4FF]/20">
          <button 
            onClick={onClose}
            className="absolute top-4 right-4 p-2 rounded-full hover:bg-[rgba(255,255,255,0.1)] transition-colors"
          >
            <X className="w-5 h-5 text-[#94A3B8]" />
          </button>
          
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-[#00E5A0] flex items-center justify-center">
            <Check className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-bold text-[#F8FAFC] flex items-center justify-center gap-2">
            <Sparkles className="w-5 h-5 text-[#FFCC00]" />
            {t('bookingConfirmed')}
            <Sparkles className="w-5 h-5 text-[#FFCC00]" />
          </h2>
          <p className="text-[#94A3B8] mt-1">{t('ticketReady')}</p>
        </div>

        {/* Booking Details */}
        <div className="p-6 space-y-4">
          {/* QR Code Placeholder */}
          <div className="flex justify-center">
            <div className="qr-container">
              <div className="w-32 h-32 bg-[#111827] rounded-lg flex items-center justify-center">
                <div className="text-center">
                  <div className="text-xs text-[#94A3B8] mb-1">{t('bookingRef')}</div>
                  <div className="text-lg font-bold text-[#6C63FF]">{booking.qr_code}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Flight Info */}
          <div className="glass-card p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-[#94A3B8] text-sm">{booking.airline}</span>
              <span className="text-[#94A3B8] text-sm">{booking.flight_number}</span>
            </div>
            <div className="flex justify-between items-center">
              <div>
                <div className="text-xl font-bold text-[#F8FAFC]">{booking.origin}</div>
                <div className="text-xs text-[#94A3B8]">
                  {new Date(booking.departure_time).toLocaleString()}
                </div>
              </div>
              <div className="text-[#6C63FF]">→</div>
              <div className="text-right">
                <div className="text-xl font-bold text-[#F8FAFC]">{booking.destination}</div>
                <div className="text-xs text-[#94A3B8]">
                  {new Date(booking.arrival_time).toLocaleString()}
                </div>
              </div>
            </div>
          </div>

          {/* Price */}
          <div className="text-center">
            <div className="text-sm text-[#94A3B8]">Total</div>
            <div className="text-2xl font-bold text-[#00D4FF]">
              {booking.price.toLocaleString()} {booking.currency}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="p-4 space-y-3 border-t border-[rgba(255,255,255,0.08)]">
          <button
            onClick={handleSendWhatsApp}
            disabled={isSending || whatsAppSent}
            className={`w-full py-3 rounded-full flex items-center justify-center gap-2 font-semibold transition-colors ${
              whatsAppSent 
                ? 'bg-[#00E5A0] text-white' 
                : 'bg-[#25D366] hover:bg-[#128C7E] text-white'
            }`}
            data-testid="send-whatsapp-btn"
          >
            {whatsAppSent ? (
              <>
                <Check className="w-5 h-5" />
                <span>{t('successWhatsApp')}</span>
              </>
            ) : (
              <>
                <MessageCircle className="w-5 h-5" />
                <span>{t('sendWhatsApp')}</span>
              </>
            )}
          </button>

          <button
            onClick={handleDownloadPDF}
            className="w-full py-3 rounded-full border border-[rgba(255,255,255,0.2)] text-[#F8FAFC] flex items-center justify-center gap-2 font-semibold hover:bg-[rgba(255,255,255,0.05)] transition-colors"
            data-testid="download-pdf-btn"
          >
            <Download className="w-5 h-5" />
            <span>{t('downloadPdf')}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmationModal;
