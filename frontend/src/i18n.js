// Internationalization for Travelioo
const translations = {
  en: {
    // General
    appName: "Travelioo",
    tagline: "Your voice, your journey",
    
    // Home
    homeTitle: "Where do you want to go?",
    homeSubtitle: "Tap the mic and tell me your travel plans",
    typeHere: "Or type your request here...",
    send: "Send",
    
    // Voice
    listening: "Listening...",
    tapToSpeak: "Tap to speak",
    processing: "Processing...",
    
    // Intent badges
    destination: "Destination",
    departure: "Departure",
    return: "Return",
    budget: "Budget",
    passengers: "Passengers",
    class: "Class",
    
    // Flights
    searchingFlights: "Searching flights...",
    flightsFound: "Available Flights",
    selectFlight: "Select",
    eco: "Economy",
    fast: "Direct",
    premium: "Premium",
    direct: "Direct",
    stop: "stop",
    stops: "stops",
    from: "From",
    duration: "Duration",
    
    // Payment
    payment: "Payment",
    selectPayment: "Select payment method",
    momo: "MTN Mobile Money",
    googlePay: "Google Pay",
    applePay: "Apple Pay",
    phoneNumber: "Phone number",
    enterPhone: "Enter your MTN number",
    pay: "Pay Now",
    processing: "Processing payment...",
    
    // Confirmation
    bookingConfirmed: "Booking Confirmed!",
    ticketReady: "Your ticket is ready",
    sendWhatsApp: "Send to WhatsApp",
    downloadPdf: "Download PDF",
    bookingRef: "Booking Reference",
    
    // Profile
    profile: "Profile",
    firstName: "First Name",
    lastName: "Last Name",
    phone: "Phone",
    email: "Email",
    save: "Save Profile",
    uploadJson: "Upload JSON",
    
    // History
    history: "My Trips",
    noTrips: "No trips yet",
    viewTicket: "View Ticket",
    
    // Navigation
    home: "Home",
    trips: "Trips",
    profileNav: "Profile",
    
    // Errors
    errorGeneric: "Something went wrong. Please try again.",
    errorVoice: "Voice recognition not supported",
    errorPayment: "Payment failed. Please try again.",
    noFlights: "No flights found for your criteria",
    
    // Success
    successPayment: "Payment successful!",
    successBooking: "Booking confirmed!",
    successProfile: "Profile saved!",
    successWhatsApp: "Ticket sent to WhatsApp!",
  },
  fr: {
    // General
    appName: "Travelioo",
    tagline: "Votre voix, votre voyage",
    
    // Home
    homeTitle: "Où voulez-vous aller?",
    homeSubtitle: "Appuyez sur le micro et dites-moi vos plans de voyage",
    typeHere: "Ou tapez votre demande ici...",
    send: "Envoyer",
    
    // Voice
    listening: "J'écoute...",
    tapToSpeak: "Appuyez pour parler",
    processing: "Traitement...",
    
    // Intent badges
    destination: "Destination",
    departure: "Départ",
    return: "Retour",
    budget: "Budget",
    passengers: "Passagers",
    class: "Classe",
    
    // Flights
    searchingFlights: "Recherche de vols...",
    flightsFound: "Vols Disponibles",
    selectFlight: "Sélectionner",
    eco: "Économique",
    fast: "Direct",
    premium: "Premium",
    direct: "Direct",
    stop: "escale",
    stops: "escales",
    from: "À partir de",
    duration: "Durée",
    
    // Payment
    payment: "Paiement",
    selectPayment: "Choisir le mode de paiement",
    momo: "MTN Mobile Money",
    googlePay: "Google Pay",
    applePay: "Apple Pay",
    phoneNumber: "Numéro de téléphone",
    enterPhone: "Entrez votre numéro MTN",
    pay: "Payer",
    processing: "Traitement du paiement...",
    
    // Confirmation
    bookingConfirmed: "Réservation Confirmée!",
    ticketReady: "Votre billet est prêt",
    sendWhatsApp: "Envoyer sur WhatsApp",
    downloadPdf: "Télécharger PDF",
    bookingRef: "Référence de réservation",
    
    // Profile
    profile: "Profil",
    firstName: "Prénom",
    lastName: "Nom",
    phone: "Téléphone",
    email: "Email",
    save: "Enregistrer",
    uploadJson: "Importer JSON",
    
    // History
    history: "Mes Voyages",
    noTrips: "Aucun voyage",
    viewTicket: "Voir le billet",
    
    // Navigation
    home: "Accueil",
    trips: "Voyages",
    profileNav: "Profil",
    
    // Errors
    errorGeneric: "Une erreur s'est produite. Veuillez réessayer.",
    errorVoice: "Reconnaissance vocale non supportée",
    errorPayment: "Paiement échoué. Veuillez réessayer.",
    noFlights: "Aucun vol trouvé pour vos critères",
    
    // Success
    successPayment: "Paiement réussi!",
    successBooking: "Réservation confirmée!",
    successProfile: "Profil enregistré!",
    successWhatsApp: "Billet envoyé sur WhatsApp!",
  }
};

export const getTranslation = (lang, key) => {
  const language = translations[lang] || translations.fr;
  return language[key] || key;
};

export const detectBrowserLanguage = () => {
  const browserLang = navigator.language || navigator.userLanguage;
  if (browserLang && browserLang.startsWith('en')) {
    return 'en';
  }
  return 'fr'; // Default to French for West African users
};

export default translations;
