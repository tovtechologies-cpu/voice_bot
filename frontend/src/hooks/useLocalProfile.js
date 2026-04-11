import { useState, useEffect, useCallback } from 'react';

const PROFILE_KEY = 'travelioo_user_profile';
const USER_ID_KEY = 'travelioo_user_id';

export const useLocalProfile = () => {
  const [profile, setProfile] = useState(null);
  const [userId, setUserId] = useState(null);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load profile from localStorage on mount
  useEffect(() => {
    try {
      const savedProfile = localStorage.getItem(PROFILE_KEY);
      const savedUserId = localStorage.getItem(USER_ID_KEY);
      
      if (savedProfile) {
        setProfile(JSON.parse(savedProfile));
      }
      if (savedUserId) {
        setUserId(savedUserId);
      }
    } catch (err) {
      console.error('Failed to load profile from localStorage:', err);
    }
    setIsLoaded(true);
  }, []);

  // Save profile to localStorage
  const saveProfile = useCallback((newProfile, newUserId = null) => {
    try {
      setProfile(newProfile);
      localStorage.setItem(PROFILE_KEY, JSON.stringify(newProfile));
      
      if (newUserId) {
        setUserId(newUserId);
        localStorage.setItem(USER_ID_KEY, newUserId);
      }
    } catch (err) {
      console.error('Failed to save profile to localStorage:', err);
    }
  }, []);

  // Clear profile from localStorage
  const clearProfile = useCallback(() => {
    try {
      localStorage.removeItem(PROFILE_KEY);
      localStorage.removeItem(USER_ID_KEY);
      setProfile(null);
      setUserId(null);
    } catch (err) {
      console.error('Failed to clear profile from localStorage:', err);
    }
  }, []);

  // Update specific profile fields
  const updateProfile = useCallback((updates) => {
    const newProfile = { ...profile, ...updates };
    saveProfile(newProfile);
  }, [profile, saveProfile]);

  return {
    profile,
    userId,
    isLoaded,
    saveProfile,
    clearProfile,
    updateProfile,
    hasProfile: !!profile && !!profile.first_name,
  };
};

export default useLocalProfile;
