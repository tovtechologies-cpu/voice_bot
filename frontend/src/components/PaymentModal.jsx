import React, { useState } from 'react';
import { Smartphone, CreditCard, Loader2, X, Check } from 'lucide-react';
import { processMomoPayment, processGooglePay, processApplePay } from '../api';

const PaymentModal = ({ isOpen, onClose, flight, passengers, userId, onSuccess, t }) => {
  const [selectedMethod, setSelectedMethod] = useState('momo');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen || !flight) return null;

  const totalAmount = flight.price * passengers;

  const handlePayment = async () => {
    setError(null);
    setIsProcessing(true);

    try {
      const paymentData = {
        booking_id: 'temp', // Will be created during booking
        amount: totalAmount,
        currency: 'XOF',
        phone_number: phoneNumber || '0000000000',
        payment_method: selectedMethod,
      };

      let result;
      switch (selectedMethod) {
        case 'momo':
          if (!phoneNumber || phoneNumber.length < 8) {
            throw new Error(t('enterPhone'));
          }
          result = await processMomoPayment(paymentData);
          break;
        case 'google':
          result = await processGooglePay(paymentData);
          break;
        case 'apple':
          result = await processApplePay(paymentData);
          break;
        default:
          throw new Error('Invalid payment method');
      }

      if (result.status === 'success') {
        onSuccess(result, selectedMethod);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || t('errorPayment'));
    } finally {
      setIsProcessing(false);
    }
  };

  const paymentMethods = [
    { id: 'momo', label: t('momo'), icon: Smartphone, color: '#FFCC00' },
    { id: 'google', label: t('googlePay'), icon: CreditCard, color: '#4285F4' },
    { id: 'apple', label: t('applePay'), icon: CreditCard, color: '#000000' },
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
            className="p-2 rounded-full hover:bg-[rgba(255,255,255,0.1)] transition-colors"
            data-testid="close-payment-modal"
          >
            <X className="w-5 h-5 text-[#94A3B8]" />
          </button>
        </div>

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
            <div className="text-[#FF4D6D] text-sm text-center p-2 bg-[rgba(255,77,109,0.1)] rounded-lg">
              {error}
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
      </div>
    </div>
  );
};

export default PaymentModal;
