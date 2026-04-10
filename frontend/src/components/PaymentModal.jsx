import React, { useState, useEffect, useCallback } from 'react';
import { Smartphone, CreditCard, Loader2, X, Check, Timer, RefreshCw } from 'lucide-react';
import { initiatePayment, checkPaymentStatus, completePayment, createBooking } from '../api';

const PaymentModal = ({ 
  isOpen, 
  onClose, 
  flight, 
  passengers, 
  userId, 
  userProfile,
  intent,
  onSuccess, 
  t 
}) => {
  const [selectedMethod, setSelectedMethod] = useState('momo');
  const [phoneNumber, setPhoneNumber] = useState(userProfile?.phone || '');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPollng, setIsPolling] = useState(false);
  const [error, setError] = useState(null);
  const [paymentRef, setPaymentRef] = useState(null);
  const [countdown, setCountdown] = useState(30);
  const [pollCount, setPollCount] = useState(0);
  const [bookingId, setBookingId] = useState(null);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setSelectedMethod('momo');
      setIsProcessing(false);
      setIsPolling(false);
      setError(null);
      setPaymentRef(null);
      setCountdown(30);
      setPollCount(0);
      setBookingId(null);
      if (userProfile?.phone) {
        setPhoneNumber(userProfile.phone);
      }
    }
  }, [isOpen, userProfile]);

  // Countdown timer during polling
  useEffect(() => {
    let timer;
    if (isPollng && countdown > 0) {
      timer = setInterval(() => {
        setCountdown(prev => prev - 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isPollng, countdown]);

  // Payment status polling
  const pollPaymentStatus = useCallback(async (reference, bId) => {
    if (pollCount >= 10) {
      setIsPolling(false);
      setError(t('errorPayment') + ' (Timeout)');
      return;
    }

    try {
      const status = await checkPaymentStatus(reference);
      
      if (status.status === 'SUCCESSFUL') {
        setIsPolling(false);
        // Complete payment and generate ticket
        const result = await completePayment(bId, reference);
        onSuccess(result, selectedMethod);
      } else if (status.status === 'FAILED') {
        setIsPolling(false);
        setError(t('errorPayment'));
      } else {
        // Still pending, poll again
        setPollCount(prev => prev + 1);
        setTimeout(() => pollPaymentStatus(reference, bId), 3000);
      }
    } catch (err) {
      console.error('Payment status check failed:', err);
      setPollCount(prev => prev + 1);
      if (pollCount < 10) {
        setTimeout(() => pollPaymentStatus(reference, bId), 3000);
      } else {
        setIsPolling(false);
        setError(t('errorPayment'));
      }
    }
  }, [pollCount, selectedMethod, onSuccess, t]);

  if (!isOpen || !flight) return null;

  const totalAmount = flight.price * passengers;

  const handlePayment = async () => {
    setError(null);
    setIsProcessing(true);

    try {
      // Validate phone for MoMo
      if (selectedMethod === 'momo' && (!phoneNumber || phoneNumber.length < 8)) {
        throw new Error(t('enterPhone'));
      }

      // Create booking first
      const booking = await createBooking({
        user_id: userId,
        flight_id: flight.id,
        flight_data: flight,
        passengers: passengers,
        travel_class: intent?.travel_class || 'economy',
        passenger_name: `${userProfile?.first_name || 'Guest'} ${userProfile?.last_name || 'User'}`,
        return_date: intent?.return_date || null
      });

      setBookingId(booking.id);

      // Initiate payment
      const paymentData = {
        booking_id: booking.id,
        amount: totalAmount,
        currency: 'XOF',
        phone_number: phoneNumber || '0000000000',
        payment_method: selectedMethod,
      };

      const result = await initiatePayment(paymentData);
      
      if (result.status === 'success') {
        // Instant success (Google Pay / Apple Pay)
        const completeResult = await completePayment(booking.id, result.reference_id);
        onSuccess(completeResult, selectedMethod);
      } else if (result.status === 'pending') {
        // MoMo - need to poll
        setPaymentRef(result.reference_id);
        setIsProcessing(false);
        setIsPolling(true);
        setCountdown(30);
        setPollCount(0);
        
        // Start polling after 3 seconds
        setTimeout(() => pollPaymentStatus(result.reference_id, booking.id), 3000);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || t('errorPayment'));
      setIsProcessing(false);
    }
  };

  const handleRetry = () => {
    setError(null);
    setIsPolling(false);
    setPaymentRef(null);
    setCountdown(30);
    setPollCount(0);
  };

  const paymentMethods = [
    { id: 'momo', label: t('momo'), icon: Smartphone, color: '#FFCC00' },
    { id: 'google', label: t('googlePay'), icon: CreditCard, color: '#4285F4' },
    { id: 'apple', label: t('applePay'), icon: CreditCard, color: '#FFFFFF' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm">
      <div 
        className="glass-card w-full max-w-md mx-4 mb-0 sm:mb-4 rounded-t-2xl sm:rounded-2xl overflow-hidden animate-[fadeSlideUp_0.3s_ease]"
        data-testid="payment-modal"
      >
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-[rgba(255,255,255,0.08)]">
          <h2 className="text-lg font-bold text-[#F8FAFC]">{t('payment')}</h2>
          <button 
            onClick={onClose}
            disabled={isPollng}
            className="p-2 rounded-full hover:bg-[rgba(255,255,255,0.1)] transition-colors disabled:opacity-50"
            data-testid="close-payment-modal"
          >
            <X className="w-5 h-5 text-[#94A3B8]" />
          </button>
        </div>

        {/* Polling State */}
        {isPollng && (
          <div className="p-6 text-center">
            <div className="relative w-24 h-24 mx-auto mb-4">
              {/* Animated ring */}
              <svg className="w-24 h-24 transform -rotate-90">
                <circle
                  cx="48"
                  cy="48"
                  r="44"
                  stroke="#111827"
                  strokeWidth="8"
                  fill="none"
                />
                <circle
                  cx="48"
                  cy="48"
                  r="44"
                  stroke="#6C63FF"
                  strokeWidth="8"
                  fill="none"
                  strokeLinecap="round"
                  strokeDasharray={`${(countdown / 30) * 276.46} 276.46`}
                  className="transition-all duration-1000"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-2xl font-bold text-[#F8FAFC]">{countdown}s</span>
              </div>
            </div>
            <h3 className="text-lg font-semibold text-[#F8FAFC] mb-2">
              {selectedMethod === 'momo' ? 'Approve on your phone' : 'Processing...'}
            </h3>
            <p className="text-sm text-[#94A3B8]">
              {selectedMethod === 'momo' 
                ? 'Check your MTN MoMo notification and enter your PIN'
                : 'Please wait while we process your payment'
              }
            </p>
            <div className="mt-4 flex items-center justify-center gap-2 text-[#6C63FF]">
              <Timer className="w-4 h-4 animate-pulse" />
              <span className="text-sm">Waiting for confirmation...</span>
            </div>
          </div>
        )}

        {/* Normal Content */}
        {!isPollng && (
          <>
            {/* Content */}
            <div className="p-4 space-y-4">
              {/* Amount */}
              <div className="text-center py-4">
                <div className="text-sm text-[#94A3B8] mb-1">Total</div>
                <div className="text-3xl font-bold text-[#00D4FF]">
                  {totalAmount.toLocaleString()} <span className="text-lg">XOF</span>
                </div>
                <div className="text-xs text-[#94A3B8] mt-1">
                  {flight.origin} → {flight.destination} • {passengers} {passengers > 1 ? t('passengers') : 'passenger'}
                </div>
              </div>

              {/* Payment Methods */}
              <div className="space-y-2">
                <div className="text-sm text-[#94A3B8] mb-2">{t('selectPayment')}</div>
                {paymentMethods.map((method) => (
                  <button
                    key={method.id}
                    onClick={() => setSelectedMethod(method.id)}
                    className={`payment-method w-full ${selectedMethod === method.id ? 'selected' : ''}`}
                    data-testid={`payment-method-${method.id}`}
                  >
                    <div 
                      className="w-10 h-10 rounded-full flex items-center justify-center"
                      style={{ backgroundColor: `${method.color}20` }}
                    >
                      <method.icon className="w-5 h-5" style={{ color: method.color }} />
                    </div>
                    <span className="flex-1 text-left font-medium text-[#F8FAFC]">{method.label}</span>
                    {selectedMethod === method.id && (
                      <Check className="w-5 h-5 text-[#6C63FF]" />
                    )}
                  </button>
                ))}
              </div>

              {/* Phone Number Input (for MoMo) */}
              {selectedMethod === 'momo' && (
                <div className="space-y-2">
                  <label className="text-sm text-[#94A3B8]">{t('phoneNumber')}</label>
                  <input
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder={t('enterPhone')}
                    className="input-dark w-full"
                    data-testid="momo-phone-input"
                  />
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="flex items-center justify-between text-[#FF4D6D] text-sm p-3 bg-[rgba(255,77,109,0.1)] rounded-lg">
                  <span>{error}</span>
                  <button
                    onClick={handleRetry}
                    className="flex items-center gap-1 text-[#6C63FF] hover:underline"
                  >
                    <RefreshCw className="w-4 h-4" />
                    Retry
                  </button>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-[rgba(255,255,255,0.08)]">
              <button
                onClick={handlePayment}
                disabled={isProcessing}
                className="btn-gradient w-full py-4 flex items-center justify-center gap-2"
                data-testid="payment-submit-button"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>{t('processing')}</span>
                  </>
                ) : (
                  <span>{t('pay')} {totalAmount.toLocaleString()} XOF</span>
                )}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default PaymentModal;
