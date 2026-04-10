import React from 'react';
import FlightCard from './FlightCard';
import { Plane, Loader2 } from 'lucide-react';

const FlightResults = ({ flights, selectedFlight, onSelectFlight, isLoading, t }) => {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-12" data-testid="flight-search-loading">
        <div className="relative mb-4">
          <div className="airplane-animation">
            <Plane className="w-8 h-8 text-[#6C63FF]" />
          </div>
        </div>
        <div className="flex items-center gap-2 text-[#94A3B8]">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>{t('searchingFlights')}</span>
        </div>
      </div>
    );
  }

  if (!flights || flights.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4" data-testid="flight-search-results">
      <h2 className="text-lg font-bold text-[#F8FAFC] text-center mb-4">
        {t('flightsFound')}
      </h2>
      {flights.map((flight) => (
        <FlightCard
          key={flight.id}
          flight={flight}
          isSelected={selectedFlight?.id === flight.id}
          onSelect={onSelectFlight}
          t={t}
        />
      ))}
    </div>
  );
};

export default FlightResults;
