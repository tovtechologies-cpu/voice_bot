"""Multilingual translations — 5 priority languages."""

# Phone country code → default language mapping
COUNTRY_CODE_TO_LANG = {
    "229": "fr",   # Benin
    "228": "fr",   # Togo
    "225": "fr",   # Cote d'Ivoire
    "221": "fr",   # Senegal
    "223": "fr",   # Mali
    "226": "fr",   # Burkina Faso
    "227": "fr",   # Niger
    "235": "fr",   # Chad
    "237": "fr",   # Cameroon
    "241": "fr",   # Gabon
    "242": "fr",   # Congo
    "243": "fr",   # DRC
    "33": "fr",    # France
    "32": "fr",    # Belgium
    "41": "fr",    # Switzerland
    "1": "en",     # US/Canada
    "44": "en",    # UK
    "234": "en",   # Nigeria
    "233": "en",   # Ghana
    "254": "en",   # Kenya
    "255": "en",   # Tanzania
    "256": "en",   # Uganda
    "27": "en",    # South Africa
    "34": "es",    # Spain
    "52": "es",    # Mexico
    "54": "es",    # Argentina
    "57": "es",    # Colombia
    "56": "es",    # Chile
    "51": "es",    # Peru
    "58": "es",    # Venezuela
    "212": "ar",   # Morocco
    "213": "ar",   # Algeria
    "216": "ar",   # Tunisia
    "218": "ar",   # Libya
    "20": "ar",    # Egypt
    "966": "ar",   # Saudi Arabia
    "971": "ar",   # UAE
    "974": "ar",   # Qatar
    "55": "pt",    # Brazil
    "351": "pt",   # Portugal
    "244": "pt",   # Angola
    "258": "pt",   # Mozambique
}

# Supported response languages
SUPPORTED_LANGS = {"fr", "en", "es", "ar", "pt"}

LANG_NAMES = {
    "fr": "Francais",
    "en": "English",
    "es": "Espanol",
    "ar": "العربية",
    "pt": "Portugues",
}


def detect_lang_from_phone(phone: str) -> str:
    """Detect language from phone number country code."""
    clean = phone.replace("+", "").replace(" ", "")
    # Try longest prefixes first (3-digit, 2-digit, 1-digit)
    for length in [3, 2, 1]:
        prefix = clean[:length]
        if prefix in COUNTRY_CODE_TO_LANG:
            return COUNTRY_CODE_TO_LANG[prefix]
    return "fr"  # Default


# ═══════════════════════════════════════════════════════
# ALL BOT MESSAGES — translated in 5 languages
# ═══════════════════════════════════════════════════════

MESSAGES = {
    "welcome_consent": {
        "fr": "Bienvenue sur Travelioo ! ✈️\n\nAvant de continuer, nous avons besoin de votre accord pour :\n\n✅ Utiliser votre nom pour émettre votre billet\n✅ Stocker votre profil pour vos prochaines réservations\n✅ Traiter votre paiement de façon sécurisée\n\n🔒 Vos données sont chiffrées (AES-256) et supprimables à tout moment.\n\n*1* J'accepte, continuer\n*2* Non merci",
        "en": "Welcome to Travelioo! ✈️\n\nBefore we continue, we need your agreement to:\n\n✅ Use your name to issue your ticket\n✅ Store your profile for future bookings\n✅ Process your payment securely\n\n🔒 Your data is encrypted (AES-256) and deletable anytime.\n\n*1* I agree, continue\n*2* No thanks",
        "es": "¡Bienvenido a Travelioo! ✈️\n\nAntes de continuar, necesitamos su acuerdo para:\n\n✅ Usar su nombre para emitir su boleto\n✅ Guardar su perfil para futuras reservas\n✅ Procesar su pago de forma segura\n\n🔒 Sus datos están cifrados (AES-256) y se pueden eliminar en cualquier momento.\n\n*1* Acepto, continuar\n*2* No gracias",
        "ar": "مرحبا بكم في Travelioo! ✈️\n\nقبل المتابعة، نحتاج موافقتكم على:\n\n✅ استخدام اسمكم لإصدار التذكرة\n✅ حفظ ملفكم الشخصي للحجوزات المستقبلية\n✅ معالجة الدفع بشكل آمن\n\n🔒 بياناتكم مشفرة (AES-256) ويمكن حذفها في أي وقت.\n\n*1* أوافق، متابعة\n*2* لا شكرا",
        "pt": "Bem-vindo ao Travelioo! ✈️\n\nAntes de continuar, precisamos da sua concordância para:\n\n✅ Usar seu nome para emitir sua passagem\n✅ Armazenar seu perfil para futuras reservas\n✅ Processar seu pagamento com segurança\n\n🔒 Seus dados são criptografados (AES-256) e podem ser excluídos a qualquer momento.\n\n*1* Concordo, continuar\n*2* Não obrigado",
    },
    "enrollment_menu": {
        "fr": "Comment souhaitez-vous enregistrer votre profil ? 👤\n\n*1* 📸 Scanner mon passeport (photo)\n*2* 🖼️ Envoyer une photo du passeport\n*3* ⌨️ Saisie manuelle",
        "en": "How would you like to register your profile? 👤\n\n*1* 📸 Scan my passport (photo)\n*2* 🖼️ Send a photo of the passport\n*3* ⌨️ Manual entry",
        "es": "¿Cómo desea registrar su perfil? 👤\n\n*1* 📸 Escanear mi pasaporte (foto)\n*2* 🖼️ Enviar una foto del pasaporte\n*3* ⌨️ Ingreso manual",
        "ar": "كيف تريد تسجيل ملفك الشخصي؟ 👤\n\n*1* 📸 مسح جواز السفر (صورة)\n*2* 🖼️ إرسال صورة جواز السفر\n*3* ⌨️ إدخال يدوي",
        "pt": "Como deseja registrar seu perfil? 👤\n\n*1* 📸 Escanear meu passaporte (foto)\n*2* 🖼️ Enviar uma foto do passaporte\n*3* ⌨️ Entrada manual",
    },
    "ask_first_name": {
        "fr": "Quel est votre prénom ? 😊\n(tel qu'il apparaît sur votre passeport)",
        "en": "What is your first name? 😊\n(as it appears on your passport)",
        "es": "¿Cuál es su nombre? 😊\n(tal como aparece en su pasaporte)",
        "ar": "ما هو اسمك الأول؟ 😊\n(كما يظهر في جواز سفرك)",
        "pt": "Qual é o seu primeiro nome? 😊\n(como aparece no seu passaporte)",
    },
    "ask_last_name": {
        "fr": "Quel est votre nom de famille ? 👤",
        "en": "What is your last name? 👤",
        "es": "¿Cuál es su apellido? 👤",
        "ar": "ما هو اسم عائلتك؟ 👤",
        "pt": "Qual é o seu sobrenome? 👤",
    },
    "ask_passport": {
        "fr": "Quel est votre numero de passeport ?\n(facultatif — tapez 'passer' pour ignorer)",
        "en": "What is your passport number?\n(optional — type 'skip' to skip)",
        "es": "Cual es su numero de pasaporte?\n(opcional — escriba 'saltar' para omitir)",
        "ar": "ما هو رقم جواز سفرك؟\n(اختياري — اكتب 'تخطي' للتخطي)",
        "pt": "Qual e o numero do seu passaporte?\n(opcional — digite 'pular' para pular)",
    },
    "ask_nationality": {
        "fr": "Quelle est votre nationalite ?\nEx : Beninoise, Francaise, Nigeriane...",
        "en": "What is your nationality?\nEx: Beninese, French, Nigerian...",
        "es": "Cual es su nacionalidad?\nEj: Francesa, Espanola, Nigeriana...",
        "ar": "ما هي جنسيتك؟\nمثال: فرنسية، مصرية، نيجيرية...",
        "pt": "Qual e a sua nacionalidade?\nEx: Brasileira, Portuguesa, Nigeriana...",
    },
    "ask_origin": {
        "fr": "D'où partez-vous ? 🛫\n_Exemple : Cotonou, Paris, Dakar, COO, CDG..._",
        "en": "Where are you departing from? 🛫\n_Example: Cotonou, Paris, Dakar, COO, CDG..._",
        "es": "¿Desde dónde sale? 🛫\n_Ejemplo: Paris, Madrid, Dakar, CDG, MAD..._",
        "ar": "من أين ستغادر؟ 🛫\n_مثال: باريس، الدار البيضاء، داكار، CDG..._",
        "pt": "De onde você está partindo? 🛫\n_Exemplo: Cotonou, Paris, Lisboa, COO, LIS..._",
    },
    "ask_destination": {
        "fr": "Où souhaitez-vous aller ? 🛬\n_Exemple : Paris, Dakar, Dubai, CDG..._",
        "en": "Where would you like to go? 🛬\n_Example: Paris, Dakar, Dubai, CDG..._",
        "es": "¿A dónde desea ir? 🛬\n_Ejemplo: Paris, Dakar, Dubai, CDG..._",
        "ar": "إلى أين تريد الذهاب؟ 🛬\n_مثال: باريس، داكار، دبي، CDG..._",
        "pt": "Para onde deseja ir? 🛬\n_Exemplo: Paris, Dakar, Dubai, CDG..._",
    },
    "ask_date": {
        "fr": "Quelle est votre date de départ ? 📅\n(ex: demain, vendredi prochain, 15 mars...)",
        "en": "When do you want to depart? 📅\n(e.g.: tomorrow, next Friday, March 15...)",
        "es": "¿Cuándo desea partir? 📅\n(ej: mañana, próximo viernes, 15 de marzo...)",
        "ar": "متى تريد المغادرة؟ 📅\n(مثال: غدا، الجمعة القادمة، 15 مارس...)",
        "pt": "Quando deseja partir? 📅\n(ex: amanhã, próxima sexta, 15 de março...)",
    },
    "ask_return": {
        "fr": "Souhaitez-vous un vol retour ?\n\n*1* Oui, chercher un vol retour\n*2* Non, aller simple uniquement",
        "en": "Would you like a return flight?\n\n*1* Yes, search a return flight\n*2* No, one-way only",
        "es": "Desea un vuelo de regreso?\n\n*1* Si, buscar vuelo de regreso\n*2* No, solo ida",
        "ar": "هل تريد رحلة عودة؟\n\n*1* نعم، ابحث عن رحلة عودة\n*2* لا، ذهاب فقط",
        "pt": "Deseja um voo de volta?\n\n*1* Sim, buscar voo de volta\n*2* Nao, somente ida",
    },
    "fallback_error": {
        "fr": "Desole, je n'ai pas compris votre choix.\n\nVeuillez selectionner une option valide ou tapez *annuler* pour recommencer.",
        "en": "Sorry, I didn't understand your choice.\n\nPlease select a valid option or type *cancel* to start over.",
        "es": "Lo siento, no entendi su eleccion.\n\nPor favor seleccione una opcion valida o escriba *cancelar* para reiniciar.",
        "ar": "عذرا، لم أفهم اختيارك.\n\nيرجى تحديد خيار صحيح أو اكتب *إلغاء* للبدء من جديد.",
        "pt": "Desculpe, nao entendi sua escolha.\n\nPor favor selecione uma opcao valida ou digite *cancelar* para recomeccar.",
    },
    "audio_failed": {
        "fr": "Je n'ai pas pu comprendre votre audio.\n\nPouvez-vous :\n*1* Reessayer avec un message vocal plus clair\n*2* Ou taper votre destination par ecrit\n\n_Exemple : Paris vendredi retour lundi_",
        "en": "I couldn't understand your audio.\n\nYou can:\n*1* Try again with a clearer voice message\n*2* Or type your destination\n\n_Example: Paris Friday return Monday_",
        "es": "No pude entender su audio.\n\nPuede:\n*1* Intentar de nuevo con un mensaje de voz mas claro\n*2* O escribir su destino\n\n_Ejemplo: Paris viernes regreso lunes_",
        "ar": "لم أتمكن من فهم الصوت.\n\nيمكنك:\n*1* المحاولة مرة أخرى برسالة صوتية أوضح\n*2* أو كتابة وجهتك\n\n_مثال: باريس الجمعة عودة الاثنين_",
        "pt": "Nao consegui entender seu audio.\n\nVoce pode:\n*1* Tentar novamente com uma mensagem de voz mais clara\n*2* Ou digitar seu destino\n\n_Exemplo: Paris sexta volta segunda_",
    },
    "searching_flights": {
        "fr": "Recherche de vols {origin} -> {destination}...",
        "en": "Searching flights {origin} -> {destination}...",
        "es": "Buscando vuelos {origin} -> {destination}...",
        "ar": "جاري البحث عن رحلات {origin} -> {destination}...",
        "pt": "Buscando voos {origin} -> {destination}...",
    },
    "no_flights": {
        "fr": "Aucun vol trouve pour cette destination.",
        "en": "No flights found for this destination.",
        "es": "No se encontraron vuelos para este destino.",
        "ar": "لم يتم العثور على رحلات لهذه الوجهة.",
        "pt": "Nenhum voo encontrado para este destino.",
    },
    "change_language": {
        "fr": "*Changer de langue / Change language*\n\n*1* Francais\n*2* English\n*3* Espanol\n*4* العربية (Arabe)\n*5* Portugues",
        "en": "*Change language / Changer de langue*\n\n*1* Francais\n*2* English\n*3* Espanol\n*4* العربية (Arabic)\n*5* Portugues",
        "es": "*Cambiar idioma / Change language*\n\n*1* Francais\n*2* English\n*3* Espanol\n*4* العربية (Arabe)\n*5* Portugues",
        "ar": "*تغيير اللغة / Change language*\n\n*1* Francais\n*2* English\n*3* Espanol\n*4* العربية (عربي)\n*5* Portugues",
        "pt": "*Mudar idioma / Change language*\n\n*1* Francais\n*2* English\n*3* Espanol\n*4* العربية (Arabe)\n*5* Portugues",
    },
    "language_changed": {
        "fr": "Langue changee : *Francais*",
        "en": "Language changed: *English*",
        "es": "Idioma cambiado: *Espanol*",
        "ar": "تم تغيير اللغة: *العربية*",
        "pt": "Idioma alterado: *Portugues*",
    },
    "returning_user": {
        "fr": "Rebonjour {name} ! 👋\nRéservez-vous ce vol pour vous-même ou pour quelqu'un d'autre ?\n\n*1* Pour moi ({fullname})\n*2* Pour un tiers",
        "en": "Welcome back {name}! 👋\nAre you booking for yourself or someone else?\n\n*1* For me ({fullname})\n*2* For someone else",
        "es": "¡Hola de nuevo {name}! 👋\n¿Reserva para usted o para otra persona?\n\n*1* Para mí ({fullname})\n*2* Para otra persona",
        "ar": "مرحبا مجددا {name}! 👋\nهل تحجز لنفسك أم لشخص آخر؟\n\n*1* لي ({fullname})\n*2* لشخص آخر",
        "pt": "Olá novamente {name}! 👋\nVocê está reservando para si ou para outra pessoa?\n\n*1* Para mim ({fullname})\n*2* Para outra pessoa",
    },
}


def t(key: str, lang: str, **kwargs) -> str:
    """Get translated message. Falls back to French if key/lang not found."""
    lang = lang if lang in SUPPORTED_LANGS else "fr"
    msg_dict = MESSAGES.get(key, {})
    msg = msg_dict.get(lang, msg_dict.get("fr", f"[{key}]"))
    if kwargs:
        msg = msg.format(**kwargs)
    return msg
