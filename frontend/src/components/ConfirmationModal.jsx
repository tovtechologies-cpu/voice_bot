import React, { useState, useEffect } from 'react';
import { Check, MessageCircle, Download, Sparkles, X, AlertCircle } from 'lucide-react';
import { sendWhatsAppTicket, downloadTicket } from '../api';
import { toast } from 'sonner';

const ConfirmationModal = ({ isOpen, onClose, booking, userPhone, t }) => {
  const [showConfetti, setShowConfetti] = useState(false);
  const [whatsAppStatus, setWhatsAppStatus] = useState('idle'); // idle, sending, sent, failed
  const [phoneInput, setPhoneInput] = useState(userPhone || '');

  useEffect(() => {
    if (isOpen) {
      setShowConfetti(true);
      setWhatsAppStatus('idle');
      setPhoneInput(userPhone || '');
      const timer = setTimeout(() => setShowConfetti(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [isOpen, userPhone]);

  if (!isOpen || !booking) return null;

  const bookingData = booking.booking || booking;
  const bookingRef = bookingData.booking_ref || bookingData.qr_code || 'TRV-XXXXXX';
  const ticketUrl = booking.ticket_url || bookingData.ticket_url;

  const handleSendWhatsApp = async () => {
    if (!phoneInput || phoneInput.length < 8) {
      toast.error(t('enterPhone'));
      return;
    }
    
    setWhatsAppStatus('sending');
    try {
      const result = await sendWhatsAppTicket(phoneInput, bookingData.id);
      
      if (result.status === 'sent') {
        setWhatsAppStatus('sent');
        toast.success(t('successWhatsApp'));
      } else if (result.status === 'simulated') {
        setWhatsAppStatus('sent');
        toast.success('WhatsApp delivery simulated - download your ticket below');
      } else {
        throw new Error('WhatsApp delivery failed');
      }
    } catch (err) {
      console.error('WhatsApp send failed:', err);
      setWhatsAppStatus('failed');
      toast.error('WhatsApp delivery failed — your ticket was downloaded locally');
      // Auto-download on failure
      if (ticketUrl) {
        downloadTicket(ticketUrl);
      }
    }
  };

  const handleDownloadPDF = () => {
    if (ticketUrl) {
      downloadTicket(ticketUrl);
    } else {
      // Fallback: create simple text ticket
      const ticketContent = `
TRAVELIOO TICKET
================
Booking Reference: ${bookingRef}

Flight: ${bookingData.flight_number || 'N/A'}
Airline: ${bookingData.airline || 'N/A'}
Route: ${bookingData.origin || ''} → ${bookingData.destination || ''}
Departure: ${bookingData.departure_time ? new Date(bookingData.departure_time).toLocaleString() : 'N/A'}

Passengers: ${bookingData.passengers || 1}
Total Price: ${(bookingData.price || 0).toLocaleString()} ${bookingData.currency || 'XOF'}

Status: CONFIRMED
Payment: COMPLETED

Thank you for choosing Travelioo!
      `;

      const blob = new Blob([ticketContent], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `travelioo-ticket-${bookingRef}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
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
        className="glass-card w-full max-w-md mx-4 rounded-2xl overflow-hidden animate-[fadeSlideUp_0.3s_ease] max-h-[90vh] overflow-y-auto"
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
          {/* QR Code / Booking Ref */}
          <div className="flex justify-center">
            <div className="qr-container">
              <div className="w-32 h-32 bg-[#111827] rounded-lg flex items-center justify-center">
                <div className="text-center">
                  <div className="text-xs text-[#94A3B8] mb-1">{t('bookingRef')}</div>
                  <div className="text-lg font-bold text-[#6C63FF]">{bookingRef}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Flight Info */}
          <div className="glass-card p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-[#94A3B8] text-sm">{bookingData.airline || 'Airline'}</span>
              <span className="text-[#94A3B8] text-sm">{bookingData.flight_number || ''}</span>
            </div>
            <div className="flex justify-between items-center">
              <div>
                <div className="text-xl font-bold text-[#F8FAFC]">{bookingData.origin || 'DSS'}</div>
                <div className="text-xs text-[#94A3B8]">
                  {bookingData.departure_time ? new Date(bookingData.departure_time).toLocaleString() : ''}
                </div>
              </div>
              <div className="text-[#6C63FF]">→</div>
              <div className="text-right">
                <div className="text-xl font-bold text-[#F8FAFC]">{bookingData.destination || 'ABJ'}</div>
                <div className="text-xs text-[#94A3B8]">
                  {bookingData.arrival_time ? new Date(bookingData.arrival_time).toLocaleString() : ''}
                </div>
              </div>
            </div>
          </div>

          {/* Price */}
          <div className="text-center">
            <div className="text-sm text-[#94A3B8]">Total</div>
            <div className="text-2xl font-bold text-[#00D4FF]">
              {(bookingData.price || 0).toLocaleString()} {bookingData.currency || 'XOF'}
            </div>
          </div>

          {/* Phone Input for WhatsApp */}
          {whatsAppStatus !== 'sent' && (
            <div className="space-y-2">
              <label className="text-sm text-[#94A3B8]">WhatsApp Number</label>
              <input
                type="tel"
                value={phoneInput}
                onChange={(e) => setPhoneInput(e.target.value)}
                placeholder="+221 7X XXX XX XX"
                className="input-dark w-full"
                data-testid="whatsapp-phone-input"
              />
            </div>
          )}

          {/* WhatsApp Failed Notice */}
          {whatsAppStatus === 'failed' && (
            <div className="flex items-center gap-2 text-[#FFCC00] text-sm p-3 bg-[rgba(255,204,0,0.1)] rounded-lg">
              <AlertCircle className="w-4 h-4" />
              <span>WhatsApp delivery failed — ticket downloaded automatically</span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="p-4 space-y-3 border-t border-[rgba(255,255,255,0.08)]">
          <button
            onClick={handleSendWhatsApp}
            disabled={whatsAppStatus === 'sending' || whatsAppStatus === 'sent'}
            className={`w-full py-3 rounded-full flex items-center justify-center gap-2 font-semibold transition-colors ${
              whatsAppStatus === 'sent' 
                ? 'bg-[#00E5A0] text-white' 
                : 'bg-[#25D366] hover:bg-[#128C7E] text-white'
            } disabled:opacity-70`}
            data-testid="send-whatsapp-btn"
          >
            {whatsAppStatus === 'sending' ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Sending...</span>
              </>
            ) : whatsAppStatus === 'sent' ? (
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
