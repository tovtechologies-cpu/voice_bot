import React from 'react';
import { NavLink } from 'react-router-dom';
import { Home, Clock, User } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { getTranslation } from '../i18n';

const BottomNav = () => {
  const { language } = useLanguage();
  const t = (key) => getTranslation(language, key);

  const navItems = [
    { path: '/', icon: Home, label: t('home'), testId: 'nav-home' },
    { path: '/history', icon: Clock, label: t('trips'), testId: 'nav-trips' },
    { path: '/profile', icon: User, label: t('profileNav'), testId: 'nav-profile' },
  ];

  return (
    <nav className="bottom-nav" data-testid="bottom-navigation">
      <div className="flex justify-around items-center max-w-md mx-auto">
        {navItems.map(({ path, icon: Icon, label, testId }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) => 
              `bottom-nav-item ${isActive ? 'active' : ''}`
            }
            data-testid={testId}
          >
            <Icon className="w-6 h-6 mb-1" />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
};

export default BottomNav;
