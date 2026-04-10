import React from 'react';
import { MapPin, Calendar, Wallet, Users, Sparkles } from 'lucide-react';

const IntentBadge = ({ icon: Icon, label, value }) => {
  // Only render if value exists - never show placeholders
  if (!value) return null;

  return (
    <div className="badge-pill flex items-center gap-2" data-testid="intent-badge">
      <Icon className="w-4 h-4 text-[#6C63FF]" />
      <span className="text-[#94A3B8] text-xs">{label}:</span>
      <span className="text-[#F8FAFC] font-medium">{value}</span>
    </div>
  );
};

const IntentBadges = ({ intent, t }) => {
  if (!intent) return null;

  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(intent.language === 'fr' ? 'fr-FR' : 'en-US', {
        weekday: 'short',
        day: 'numeric',
        month: 'short'
      });
    } catch {
      return dateStr;
    }
  };

  const formatBudget = (budget) => {
    if (!budget) return null;
    return `${budget.toLocaleString()} XOF`;
  };

  return (
    <div className="flex flex-wrap gap-2 justify-center" data-testid="intent-badges-container">
      <IntentBadge 
        icon={MapPin} 
        label={t('destination')} 
        value={intent.destination} 
      />
      <IntentBadge 
        icon={Calendar} 
        label={t('departure')} 
        value={formatDate(intent.departure_date)} 
      />
      <IntentBadge 
        icon={Calendar} 
        label={t('return')} 
        value={formatDate(intent.return_date)} 
      />
      <IntentBadge 
        icon={Wallet} 
        label={t('budget')} 
        value={formatBudget(intent.budget)} 
      />
      {intent.passengers > 1 && (
        <IntentBadge 
          icon={Users} 
          label={t('passengers')} 
          value={intent.passengers.toString()} 
        />
      )}
      {intent.travel_class && intent.travel_class !== 'economy' && (
        <IntentBadge 
          icon={Sparkles} 
          label={t('class')} 
          value={intent.travel_class} 
        />
      )}
    </div>
  );
};

export default IntentBadges;
