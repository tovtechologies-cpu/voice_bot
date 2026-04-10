import React from 'react';
import { Plane, Clock, ArrowRight, AlertCircle } from 'lucide-react';

const FlightCard = ({ flight, isSelected, onSelect, t }) => {
  const getTierClass = (tier) => {
    switch (tier) {
      case 'ECO': return 'tier-eco';
      case 'FAST': return 'tier-fast';
      case 'PREMIUM': return 'tier-premium';
      default: return '';
    }
  };

  const getTierLabel = (tier) => {
    switch (tier) {
      case 'ECO': return t('eco');
      case 'FAST': return t('fast');
      case 'PREMIUM': return t('premium');
      default: return tier;
    }
  };

  const formatTime = (timeStr) => {
    try {
      const date = new Date(timeStr);
      return date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false 
      });
    } catch {
      return timeStr;
    }
  };

  const formatPrice = (price) => {
    return price.toLocaleString();
  };

  return (
    <div
      data-testid="flight-option-card"
      onClick={() => onSelect(flight)}
      className={`
        flight-card cursor-pointer relative
        ${isSelected ? 'selected' : ''}
      `}
    >
      {/* Demo Data Badge */}
      {flight.is_demo && (
        <div 
          className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 rounded-full bg-[rgba(255,204,0,0.15)] border border-[rgba(255,204,0,0.3)]"
          data-testid="demo-data-badge"
        >
          <AlertCircle className="w-3 h-3 text-[#FFCC00]" />
          <span className="text-[10px] text-[#FFCC00] font-medium">Demo</span>
        </div>
      )}

      {/* Tier Badge */}
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-2">
          <Plane className="w-5 h-5 text-[#6C63FF]" />
          <span className="font-semibold text-[#F8FAFC]">{flight.airline}</span>
        </div>
        <span className={`badge-pill text-xs ${getTierClass(flight.tier)} ${flight.is_demo ? 'mr-16' : ''}`}>
          {getTierLabel(flight.tier)}
        </span>
      </div>

      {/* Route */}
      <div className="flex items-center justify-between mb-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-[#F8FAFC]">{formatTime(flight.departure_time)}</div>
          <div className="text-sm text-[#94A3B8]">{flight.origin}</div>
        </div>
        
        <div className="flex-1 flex flex-col items-center px-4">
          <div className="flex items-center gap-2 text-[#94A3B8] text-xs mb-1">
            <Clock className="w-3 h-3" />
            <span>{flight.duration}</span>
          </div>
          <div className="w-full h-[1px] bg-gradient-to-r from-transparent via-[#6C63FF] to-transparent relative">
            <ArrowRight className="w-4 h-4 text-[#6C63FF] absolute right-0 top-1/2 -translate-y-1/2" />
          </div>
          <div className="text-xs text-[#94A3B8] mt-1">
            {flight.stops === 0 ? t('direct') : `${flight.stops} ${flight.stops === 1 ? t('stop') : t('stops')}`}
          </div>
        </div>

        <div className="text-center">
          <div className="text-2xl font-bold text-[#F8FAFC]">{formatTime(flight.arrival_time)}</div>
          <div className="text-sm text-[#94A3B8]">{flight.destination}</div>
        </div>
      </div>

      {/* Price and Flight Number */}
      <div className="flex justify-between items-center pt-4 border-t border-[rgba(255,255,255,0.08)]">
        <div className="text-xs text-[#94A3B8]">
          {flight.flight_number} • {flight.available_seats} seats
        </div>
        <div className="text-right">
          <div className="text-xs text-[#94A3B8]">{t('from')}</div>
          <div className="text-xl font-bold text-[#00D4FF]">
            {formatPrice(flight.price)} <span className="text-sm font-normal">XOF</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FlightCard;
