import React, { useState, useEffect } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { getTranslation } from '../i18n';
import { useLocalProfile } from '../hooks/useLocalProfile';
import { getUserBookings } from '../api';
import { Clock, Plane, MapPin, ChevronRight, Ticket } from 'lucide-react';

const HistoryPage = () => {
  const { language } = useLanguage();
  const t = (key) => getTranslation(language, key);
  const { userId } = useLocalProfile();

  const [bookings, setBookings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedBooking, setSelectedBooking] = useState(null);

  useEffect(() => {
    const fetchBookings = async () => {
      if (!userId) {
        setIsLoading(false);
        return;
      }

      try {
        const data = await getUserBookings(userId);
        setBookings(data);
      } catch (err) {
        console.error('Failed to fetch bookings:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchBookings();
  }, [userId]);

  const formatDate = (dateStr) => {
    try {
      return new Date(dateStr).toLocaleDateString(language === 'fr' ? 'fr-FR' : 'en-US', {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const formatTime = (dateStr) => {
    try {
      return new Date(dateStr).toLocaleTimeString(language === 'fr' ? 'fr-FR' : 'en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="min-h-screen pb-24 pt-4 px-4" data-testid="history-page">
      <div className="max-w-md mx-auto">
        {/* Header */}
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-[#F8FAFC] flex items-center gap-2">
            <Clock className="w-6 h-6 text-[#6C63FF]" />
            {t('history')}
          </h1>
        </header>

        {/* Loading State */}
        {isLoading && (
          <div className="flex justify-center py-12">
            <div className="spinner"></div>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && bookings.length === 0 && (
          <div className="text-center py-12" data-testid="no-trips-message">
            <Plane className="w-16 h-16 text-[#94A3B8] mx-auto mb-4 opacity-30" />
            <p className="text-[#94A3B8]">{t('noTrips')}</p>
          </div>
        )}

        {/* Bookings List */}
        <div className="space-y-4" data-testid="bookings-list">
          {bookings.map((booking) => (
            <div
              key={booking.id}
              className="flight-card cursor-pointer"
              onClick={() => setSelectedBooking(selectedBooking?.id === booking.id ? null : booking)}
              data-testid={`booking-card-${booking.id}`}
            >
              {/* Main Info */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#6C63FF] to-[#00D4FF] flex items-center justify-center">
                    <Plane className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <div className="font-semibold text-[#F8FAFC]">{booking.airline}</div>
                    <div className="text-xs text-[#94A3B8]">{booking.flight_number}</div>
                  </div>
                </div>
                <div className={`badge-pill text-xs ${
                  booking.status === 'confirmed' ? 'tier-eco' : 'tier-premium'
                }`}>
                  {booking.status}
                </div>
              </div>

              {/* Route */}
              <div className="flex items-center gap-3 mb-3">
                <div className="flex items-center gap-1 text-[#F8FAFC]">
                  <MapPin className="w-4 h-4 text-[#6C63FF]" />
                  <span className="font-medium">{booking.origin}</span>
                </div>
                <div className="flex-1 h-[1px] bg-gradient-to-r from-[#6C63FF] to-[#00D4FF]"></div>
                <div className="flex items-center gap-1 text-[#F8FAFC]">
                  <span className="font-medium">{booking.destination}</span>
                  <MapPin className="w-4 h-4 text-[#00D4FF]" />
                </div>
              </div>

              {/* Date & Price */}
              <div className="flex justify-between items-center text-sm">
                <div className="text-[#94A3B8]">{formatDate(booking.departure_time)}</div>
                <div className="font-bold text-[#00D4FF]">
                  {booking.price.toLocaleString()} {booking.currency}
                </div>
              </div>

              {/* Expanded Details */}
              {selectedBooking?.id === booking.id && (
                <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.08)] space-y-3 animate-[fadeSlideUp_0.2s_ease]">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-[#94A3B8] text-xs">{t('departure')}</div>
                      <div className="text-[#F8FAFC]">{formatTime(booking.departure_time)}</div>
                    </div>
                    <div>
                      <div className="text-[#94A3B8] text-xs">Arrival</div>
                      <div className="text-[#F8FAFC]">{formatTime(booking.arrival_time)}</div>
                    </div>
                    <div>
                      <div className="text-[#94A3B8] text-xs">{t('passengers')}</div>
                      <div className="text-[#F8FAFC]">{booking.passengers}</div>
                    </div>
                    <div>
                      <div className="text-[#94A3B8] text-xs">{t('bookingRef')}</div>
                      <div className="text-[#6C63FF] font-mono">{booking.qr_code}</div>
                    </div>
                  </div>

                  <button
                    className="w-full py-3 rounded-full border border-[#6C63FF] text-[#6C63FF] flex items-center justify-center gap-2 font-semibold hover:bg-[rgba(108,99,255,0.1)] transition-colors"
                    data-testid={`view-ticket-${booking.id}`}
                  >
                    <Ticket className="w-5 h-5" />
                    {t('viewTicket')}
                  </button>
                </div>
              )}

              {/* Expand Indicator */}
              <div className="flex justify-center mt-2">
                <ChevronRight 
                  className={`w-5 h-5 text-[#94A3B8] transition-transform ${
                    selectedBooking?.id === booking.id ? 'rotate-90' : ''
                  }`} 
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default HistoryPage;
