import React from 'react';
import { useLanguage } from '../context/LanguageContext';

const LanguageToggle = () => {
  const { language, setLanguage } = useLanguage();

  return (
    <div className="lang-toggle" data-testid="language-toggle">
      <button
        onClick={() => setLanguage('fr')}
        className={language === 'fr' ? 'active' : ''}
        data-testid="lang-fr-btn"
      >
        FR
      </button>
      <button
        onClick={() => setLanguage('en')}
        className={language === 'en' ? 'active' : ''}
        data-testid="lang-en-btn"
      >
        EN
      </button>
    </div>
  );
};

export default LanguageToggle;
