import React, { useState, useRef } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { getTranslation } from '../i18n';
import { useLocalProfile } from '../hooks/useLocalProfile';
import { createUser, createUsersBulk } from '../api';
import { User, Upload, Save, Check, Loader2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

const ProfilePage = () => {
  const { language } = useLanguage();
  const t = (key) => getTranslation(language, key);
  const { profile, saveProfile, hasProfile } = useLocalProfile();
  const fileInputRef = useRef(null);

  const [formData, setFormData] = useState({
    first_name: profile?.first_name || '',
    last_name: profile?.last_name || '',
    phone: profile?.phone || '',
    email: profile?.email || '',
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError(null);
    setSuccess(false);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    
    if (!formData.first_name.trim() || !formData.last_name.trim()) {
      setError(language === 'fr' ? 'Prénom et nom requis' : 'First and last name required');
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const user = await createUser(formData);
      saveProfile(user, user.id);
      setSuccess(true);
      toast.success(t('successProfile'));
    } catch (err) {
      console.error('Save error:', err);
      setError(t('errorGeneric'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setError(null);

    try {
      const text = await file.text();
      const data = JSON.parse(text);
      
      // Handle both single object and array
      const users = Array.isArray(data) ? data : [data];
      
      // Validate structure
      const validUsers = users.filter(u => u.firstName || u.first_name);
      if (validUsers.length === 0) {
        throw new Error('Invalid JSON format');
      }

      // Normalize keys
      const normalizedUsers = validUsers.map(u => ({
        first_name: u.firstName || u.first_name,
        last_name: u.lastName || u.last_name,
        phone: u.phone || '',
        email: u.email || '',
      }));

      // Create users
      const created = await createUsersBulk(normalizedUsers);
      
      // Save first user as current profile
      if (created.length > 0) {
        const firstUser = created[0];
        saveProfile(firstUser, firstUser.id);
        setFormData({
          first_name: firstUser.first_name,
          last_name: firstUser.last_name,
          phone: firstUser.phone || '',
          email: firstUser.email || '',
        });
        setSuccess(true);
        toast.success(`${created.length} ${language === 'fr' ? 'profil(s) importé(s)' : 'profile(s) imported'}`);
      }
    } catch (err) {
      console.error('Upload error:', err);
      setError(language === 'fr' ? 'Format JSON invalide' : 'Invalid JSON format');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="min-h-screen pb-24 pt-4 px-4" data-testid="profile-page">
      <div className="max-w-md mx-auto">
        {/* Header */}
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-[#F8FAFC] flex items-center gap-2">
            <User className="w-6 h-6 text-[#6C63FF]" />
            {t('profile')}
          </h1>
        </header>

        {/* Profile Form */}
        <form onSubmit={handleSave} className="glass-card p-6 space-y-4">
          {/* Avatar */}
          <div className="flex justify-center mb-4">
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[#6C63FF] to-[#00D4FF] flex items-center justify-center text-2xl font-bold text-white">
              {formData.first_name?.[0]?.toUpperCase() || '?'}
              {formData.last_name?.[0]?.toUpperCase() || ''}
            </div>
          </div>

          {/* First Name */}
          <div>
            <label className="block text-sm text-[#94A3B8] mb-2">{t('firstName')}</label>
            <input
              type="text"
              name="first_name"
              value={formData.first_name}
              onChange={handleInputChange}
              className="input-dark w-full"
              placeholder={t('firstName')}
              data-testid="profile-first-name"
            />
          </div>

          {/* Last Name */}
          <div>
            <label className="block text-sm text-[#94A3B8] mb-2">{t('lastName')}</label>
            <input
              type="text"
              name="last_name"
              value={formData.last_name}
              onChange={handleInputChange}
              className="input-dark w-full"
              placeholder={t('lastName')}
              data-testid="profile-last-name"
            />
          </div>

          {/* Phone */}
          <div>
            <label className="block text-sm text-[#94A3B8] mb-2">{t('phone')}</label>
            <input
              type="tel"
              name="phone"
              value={formData.phone}
              onChange={handleInputChange}
              className="input-dark w-full"
              placeholder="+221 XX XXX XX XX"
              data-testid="profile-phone"
            />
          </div>

          {/* Email */}
          <div>
            <label className="block text-sm text-[#94A3B8] mb-2">{t('email')}</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleInputChange}
              className="input-dark w-full"
              placeholder="email@example.com"
              data-testid="profile-email"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 text-[#FF4D6D] text-sm p-3 bg-[rgba(255,77,109,0.1)] rounded-lg">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          {/* Success */}
          {success && (
            <div className="flex items-center gap-2 text-[#00E5A0] text-sm p-3 bg-[rgba(0,229,160,0.1)] rounded-lg">
              <Check className="w-4 h-4" />
              {t('successProfile')}
            </div>
          )}

          {/* Save Button */}
          <button
            type="submit"
            disabled={isSaving}
            className="btn-gradient w-full py-4 flex items-center justify-center gap-2"
            data-testid="save-profile-btn"
          >
            {isSaving ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                <Save className="w-5 h-5" />
                {t('save')}
              </>
            )}
          </button>
        </form>

        {/* JSON Upload */}
        <div className="mt-6 glass-card p-6">
          <h2 className="text-lg font-semibold text-[#F8FAFC] mb-4">{t('uploadJson')}</h2>
          <p className="text-sm text-[#94A3B8] mb-4">
            {language === 'fr' 
              ? 'Importez un fichier JSON avec firstName et lastName'
              : 'Import a JSON file with firstName and lastName'
            }
          </p>
          
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            onChange={handleFileUpload}
            className="hidden"
            data-testid="json-file-input"
          />
          
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="w-full py-4 rounded-full border border-[rgba(255,255,255,0.2)] text-[#F8FAFC] flex items-center justify-center gap-2 font-semibold hover:bg-[rgba(255,255,255,0.05)] transition-colors"
            data-testid="upload-json-btn"
          >
            {isUploading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                <Upload className="w-5 h-5" />
                {t('uploadJson')}
              </>
            )}
          </button>

          {/* Example JSON */}
          <div className="mt-4 p-3 bg-[#0A0F1E] rounded-lg">
            <code className="text-xs text-[#94A3B8]">
              {`{"firstName": "Amadou", "lastName": "Diallo"}`}
            </code>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
