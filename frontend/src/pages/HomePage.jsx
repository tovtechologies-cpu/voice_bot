import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { getTranslation } from '../i18n';
import { useVoiceInput } from '../hooks/useVoiceInput';
import { useLocalProfile } from '../hooks/useLocalProfile';
import MicButton from '../components/MicButton';
import LanguageToggle from '../components/LanguageToggle';
import IntentBadges from '../components/IntentBadges';
import FlightResults from '../components/FlightResults';
import PaymentModal from '../components/PaymentModal';
import ConfirmationModal from '../components/ConfirmationModal';
import { parseIntent, searchFlights, createBooking, createUser } from '../api';
import { Send, Loader2 } from 'lucide-react';

const HomePage = () => {
  const { language } = useLanguage();
  const t = useCallback((key) => getTranslation(language, key), [language]);
  
  const { profile, userId, saveProfile, hasProfile } = useLocalProfile();
  const { 
    isListening, 
    transcript, 
    error: voiceError, 
    isSupported,
    startListening, 
    stopListening, 
    clearTranscript 
  } = useVoiceInput(language);

  const [textInput, setTextInput] = useState('');
  const [intent, setIntent] = useState(null);
  const [flights, setFlights] = useState([]);
  const [selectedFlight, setSelectedFlight] = useState(null);
  const [isParsingIntent, setIsParsingIntent] = useState(false);
  const [isSearchingFlights, setIsSearchingFlights] = useState(false);
  const [showPayment, setShowPayment] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [booking, setBooking] = useState(null);
  const [error, setError] = useState(null);

  // Process voice input when transcript changes
  useEffect(() => {
    if (transcript && !isListening) {
      setTextInput(transcript);
      handleSubmit(transcript);
    }
  }, [transcript, isListening]);

  const handleMicClick = () => {
    if (isListening) {
      stopListening();
    } else {
      clearTranscript();
      setError(null);
      startListening();
    }
  };

  const handleSubmit = async (text = textInput) => {
    if (!text.trim()) return;
    
    setError(null);
    setIsParsingIntent(true);
    setFlights([]);
    setSelectedFlight(null);
    setIntent(null);

    try {
      // Parse intent
      const parsedIntent = await parseIntent(text, language);
      setIntent(parsedIntent);

      // Search flights if we have enough info
      if (parsedIntent.destination && parsedIntent.departure_date) {
        setIsSearchingFlights(true);
        const flightResults = await searchFlights({
          origin: parsedIntent.origin || 'Dakar',
          destination: parsedIntent.destination,
          departure_date: parsedIntent.departure_date,
          return_date: parsedIntent.return_date,
          passengers: parsedIntent.passengers || 1,
          travel_class: parsedIntent.travel_class || 'economy',
          budget: parsedIntent.budget,
        });
        setFlights(flightResults);
      }
    } catch (err) {
      console.error('Error:', err);
      setError(t('errorGeneric'));
    } finally {
      setIsParsingIntent(false);
      setIsSearchingFlights(false);
    }
  };

  const handleSelectFlight = (flight) => {
    setSelectedFlight(flight);
    setShowPayment(true);
  };

  const handlePaymentSuccess = async (paymentResult, paymentMethod) => {
    setShowPayment(false);
    
    try {
      // Ensure user exists
      let currentUserId = userId;
      if (!currentUserId) {
        // Create a temporary user
        const newUser = await createUser({
          first_name: profile?.first_name || 'Guest',
          last_name: profile?.last_name || 'User',
          phone: profile?.phone || '',
          email: profile?.email || '',
        });
        currentUserId = newUser.id;
        saveProfile(newUser, newUser.id);
      }

      // Create booking
      const newBooking = await createBooking({
        user_id: currentUserId,
        flight_id: selectedFlight.id,
        passengers: intent?.passengers || 1,
        payment_method: paymentMethod,
      });

      setBooking(newBooking);
      setShowConfirmation(true);
    } catch (err) {
      console.error('Booking error:', err);
      setError(t('errorGeneric'));
    }
  };

  const handleConfirmationClose = () => {
    setShowConfirmation(false);
    setBooking(null);
    setSelectedFlight(null);
    setFlights([]);
    setIntent(null);
    setTextInput('');
    clearTranscript();
  };

  return (
    <div className="min-h-screen pb-24 pt-4 px-4" data-testid="home-page">
      {/* Header */}
      <header className="flex justify-between items-center mb-8 max-w-md mx-auto">
        <h1 className="text-xl font-bold bg-gradient-to-r from-[#6C63FF] to-[#00D4FF] bg-clip-text text-transparent">
          Travelio
        </h1>
        <LanguageToggle />
      </header>

      <div className="max-w-md mx-auto">
        {/* Hero Section */}
        <div className="text-center mb-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-[#F8FAFC] mb-2">
            {t('homeTitle')}
          </h2>
          <p className="text-[#94A3B8] text-sm">
            {t('homeSubtitle')}
          </p>
        </div>

        {/* Mic Button */}
        <div className="flex flex-col items-center mb-8">
          <MicButton
            isListening={isListening}
            isSupported={isSupported}
            onClick={handleMicClick}
            disabled={isParsingIntent || isSearchingFlights}
          />
          <p className="mt-4 text-sm text-[#94A3B8]">
            {isListening ? t('listening') : isParsingIntent ? t('processing') : t('tapToSpeak')}
          </p>
          {voiceError && (
            <p className="mt-2 text-sm text-[#FF4D6D]">{voiceError}</p>
          )}
        </div>

        {/* Text Input */}
        <div className="glass-card p-4 mb-6">
          <div className="flex gap-2">
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder={t('typeHere')}
              className="input-dark flex-1"
              disabled={isParsingIntent || isSearchingFlights}
              data-testid="text-input-field"
            />
            <button
              onClick={() => handleSubmit()}
              disabled={!textInput.trim() || isParsingIntent || isSearchingFlights}
              className="btn-gradient px-4 py-2 flex items-center gap-2"
              data-testid="send-button"
            >
              {isParsingIntent ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>

        {/* Intent Badges */}
        {intent && (
          <div className="mb-6">
            <IntentBadges intent={intent} t={t} />
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-[rgba(255,77,109,0.1)] border border-[#FF4D6D]/30 text-[#FF4D6D] text-sm text-center">
            {error}
          </div>
        )}

        {/* Flight Results */}
        <FlightResults
          flights={flights}
          selectedFlight={selectedFlight}
          onSelectFlight={handleSelectFlight}
          isLoading={isSearchingFlights}
          t={t}
        />

        {/* Select Flight Button */}
        {selectedFlight && !showPayment && (
          <button
            onClick={() => setShowPayment(true)}
            className="btn-gradient w-full py-4 mt-6"
            data-testid="select-flight-button"
          >
            {t('selectFlight')} - {selectedFlight.price.toLocaleString()} XOF
          </button>
        )}
      </div>

      {/* Payment Modal */}
      <PaymentModal
        isOpen={showPayment}
        onClose={() => setShowPayment(false)}
        flight={selectedFlight}
        passengers={intent?.passengers || 1}
        userId={userId}
        onSuccess={handlePaymentSuccess}
        t={t}
      />

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={showConfirmation}
        onClose={handleConfirmationClose}
        booking={booking}
        userPhone={profile?.phone}
        t={t}
      />
    </div>
  );
};

export default HomePage;
