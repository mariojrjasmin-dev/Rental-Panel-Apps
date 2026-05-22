import { I18n } from 'i18n-js';
import * as Localization from 'expo-localization';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Translation strings — keep keys short and stable.
// Add new keys to BOTH `en` and `es` — never miss a key.
const translations = {
  en: {
    // ---- Auth ----
    appName: 'DAMS Car Rental',
    welcomeBack: 'Welcome back',
    welcomeNew: 'Welcome',
    signInSub: 'Sign in to continue',
    signUpSub: 'Create your account',
    email: 'Email',
    password: 'Password',
    fullName: 'Full Name',
    phone: 'Phone',
    signIn: 'Sign In',
    signUp: 'Sign Up',
    noAccountYet: "Don't have an account?",
    haveAccount: 'Already have an account?',
    continueWithGoogle: 'Continue with Google',
    or: 'OR',
    invalidLogin: 'Invalid email or password',
    fillAllFields: 'Please fill all fields',

    // ---- Tabs ----
    tabHome: 'Home',
    tabBookings: 'Bookings',
    tabProfile: 'Profile',

    // ---- Home ----
    findCar: 'Find your perfect car',
    rentInDR: 'Rent in the Dominican Republic',
    searchByCity: 'Filter by city',
    allLocations: 'All locations',
    noCars: 'No cars available',
    seats: 'seats',
    bags: 'bags',
    perDay: '/day',

    // ---- Car Detail ----
    orSimilar: 'Or Similar',
    transmission: 'Transmission',
    fuel: 'Fuel',
    unlimitedMileage: 'Unlimited mileage',
    unlimitedMileageSub: 'Drive as far as you want — no limits',
    kmDayIncluded: '{{km}} km/day included',
    extraKmFee: 'Extra kilometers may incur additional charges',
    minDriverAge: 'Minimum driver age: {{age}} years',
    licenseRequired: "Valid driver's license required at pickup",
    features: 'Features',
    androidAuto: 'Android Auto',
    appleCarplay: 'Apple CarPlay',
    blindSpot: 'Blind Spot Warning',
    gps: 'GPS Navigation',
    keylessEntry: 'Keyless Entry',
    sunroof: 'Sunroof',
    about: 'About',
    reviews: 'Reviews',
    writeReview: 'Write a review',
    bookNow: 'Book Now',

    // ---- Booking ----
    pickupDate: 'Pickup Date',
    dropoffDate: 'Drop-off Date',
    pickupLocation: 'Pickup Location',
    dropoffLocation: 'Drop-off Location',
    paymentMethod: 'Payment Method',
    cash: 'Cash',
    card: 'Card',
    days: 'days',
    day: 'day',
    subtotal: 'Subtotal',
    tax: 'Tax',
    total: 'Total',
    confirmBooking: 'Confirm Booking',
    pay: 'Pay',
    selectPickup: 'Select pickup location',
    selectDropoff: 'Select drop-off location',

    // ---- Booking Success ----
    bookingConfirmed: 'Booking Confirmed!',
    bookingConfirmedSub: 'Your reservation is locked in. Have a safe trip!',
    paymentPending: 'Payment Pending',
    paymentPendingSub: 'Complete your payment to confirm the booking',
    viewReceipt: 'View Receipt',
    viewBookings: 'View My Bookings',
    browseMore: 'Browse More Cars',

    // ---- My Bookings ----
    myBookings: 'My Bookings',
    noBookings: 'No bookings yet',
    receipt: 'Receipt',
    statusPending: 'pending',
    statusConfirmed: 'confirmed',
    statusActive: 'active',
    statusCompleted: 'completed',
    statusCancelled: 'cancelled',
    paidStatus: 'PAID',
    unpaidStatus: 'UNPAID',
    refundedStatus: 'REFUNDED',

    // ---- Biometric ----
    biometricLogin: 'Use Biometric Login',
    enableBiometric: 'Enable Biometric Login',
    biometricPrompt: 'Sign in with biometrics',
    biometricUnavailable: 'Biometric authentication is not available on this device',
    biometricEnabled: 'Biometric login enabled',
    biometricDisabled: 'Biometric login disabled',
    enableBiometricSub: 'Sign in faster next time using Face ID, Touch ID, or your fingerprint.',
    yes: 'Yes, enable',
    notNow: 'Not now',
    signInWithBiometric: 'Sign in with Face ID / Touch ID',
    // Type-specific labels
    faceIdTitle: 'Face ID',
    touchIdTitle: 'Touch ID',
    fingerprintTitle: 'Fingerprint',
    biometricGenericTitle: 'Biometric Login',
    biometricEnableSubFace: 'Sign in faster with a glance using Face ID.',
    biometricEnableSubTouch: 'Sign in faster with your finger using Touch ID.',
    biometricEnableSubFinger: 'Sign in faster with your fingerprint.',
    biometricOnFace: 'Face ID is on. Sign in with a glance.',
    biometricOnTouch: 'Touch ID is on. Sign in with your finger.',
    biometricOnFinger: 'Fingerprint is on. Tap to sign in.',
    // Confirm password modal
    confirmPasswordTitle: 'Confirm your password',
    confirmPasswordSub: 'For security, please enter your password to enable biometric login.',
    cancelBtn: 'Cancel',
    enableBtn: 'Enable',
    wrongPassword: 'Wrong password. Please try again.',
    biometricEnableSuccess: 'Biometric login enabled.',
    biometricNotEnrolled: 'No biometrics enrolled on this device. Please add Face ID / Touch ID in Settings first.',
    biometricUnenrolledTitle: 'Set up Face ID / Touch ID',

    // ---- Receipt ----
    rentalReceipt: 'Rental Receipt',
    receiptNumber: 'Receipt #',
    issued: 'Issued',
    billedTo: 'Billed To',
    rentalDetails: 'Rental Details',
    costBreakdown: 'Cost Breakdown',
    pickup: 'Pickup',
    dropoff: 'Drop-off',
    duration: 'Duration',
    payment: 'Payment',
    grandTotal: 'Grand Total',
    dailyRate: 'Daily Rate',
    downloadPdf: 'Download PDF Receipt',
    sharePdf: 'Share / Save PDF Receipt',
    thankYou: 'Thank you for choosing DAMS Car Rental.',

    // ---- Profile ----
    profile: 'Profile',
    accountDetails: 'Account Details',
    settings: 'Settings',
    language: 'Language',
    english: 'English',
    spanish: 'Español',
    logout: 'Logout',
    editProfile: 'Edit Profile',
    save: 'Save',
    cancel: 'Cancel',
    member: 'Member',
    manageLocations: 'Manage Locations',

    // ---- Misc ----
    loading: 'Loading...',
    error: 'Error',
    retry: 'Retry',
    back: 'Back',
    close: 'Close',
    sessionExpired: 'Session expired. Please sign in again.',
    networkError: 'Network error. Please check your connection.',
  },

  es: {
    // ---- Auth ----
    appName: 'DAMS Renta de Autos',
    welcomeBack: 'Bienvenido de nuevo',
    welcomeNew: 'Bienvenido',
    signInSub: 'Inicia sesión para continuar',
    signUpSub: 'Crea tu cuenta',
    email: 'Correo',
    password: 'Contraseña',
    fullName: 'Nombre completo',
    phone: 'Teléfono',
    signIn: 'Iniciar sesión',
    signUp: 'Registrarse',
    noAccountYet: '¿No tienes cuenta?',
    haveAccount: '¿Ya tienes cuenta?',
    continueWithGoogle: 'Continuar con Google',
    or: 'O',
    invalidLogin: 'Correo o contraseña inválidos',
    fillAllFields: 'Por favor completa todos los campos',

    // ---- Tabs ----
    tabHome: 'Inicio',
    tabBookings: 'Reservas',
    tabProfile: 'Perfil',

    // ---- Home ----
    findCar: 'Encuentra tu auto ideal',
    rentInDR: 'Renta en República Dominicana',
    searchByCity: 'Filtrar por ciudad',
    allLocations: 'Todas las ubicaciones',
    noCars: 'No hay autos disponibles',
    seats: 'asientos',
    bags: 'maletas',
    perDay: '/día',

    // ---- Car Detail ----
    orSimilar: 'O Similar',
    transmission: 'Transmisión',
    fuel: 'Combustible',
    unlimitedMileage: 'Kilometraje ilimitado',
    unlimitedMileageSub: 'Conduce sin límites',
    kmDayIncluded: '{{km}} km/día incluidos',
    extraKmFee: 'Los kilómetros extra pueden generar cargos adicionales',
    minDriverAge: 'Edad mínima del conductor: {{age}} años',
    licenseRequired: 'Licencia de conducir válida requerida en la entrega',
    features: 'Características',
    androidAuto: 'Android Auto',
    appleCarplay: 'Apple CarPlay',
    blindSpot: 'Alerta de Punto Ciego',
    gps: 'GPS',
    keylessEntry: 'Entrada Sin Llave',
    sunroof: 'Techo Solar',
    about: 'Acerca de',
    reviews: 'Reseñas',
    writeReview: 'Escribir una reseña',
    bookNow: 'Reservar',

    // ---- Booking ----
    pickupDate: 'Fecha de recogida',
    dropoffDate: 'Fecha de entrega',
    pickupLocation: 'Lugar de recogida',
    dropoffLocation: 'Lugar de entrega',
    paymentMethod: 'Método de pago',
    cash: 'Efectivo',
    card: 'Tarjeta',
    days: 'días',
    day: 'día',
    subtotal: 'Subtotal',
    tax: 'Impuesto',
    total: 'Total',
    confirmBooking: 'Confirmar reserva',
    pay: 'Pagar',
    selectPickup: 'Selecciona el lugar de recogida',
    selectDropoff: 'Selecciona el lugar de entrega',

    // ---- Booking Success ----
    bookingConfirmed: '¡Reserva confirmada!',
    bookingConfirmedSub: 'Tu reserva está confirmada. ¡Buen viaje!',
    paymentPending: 'Pago pendiente',
    paymentPendingSub: 'Completa tu pago para confirmar la reserva',
    viewReceipt: 'Ver recibo',
    viewBookings: 'Ver mis reservas',
    browseMore: 'Explorar más autos',

    // ---- My Bookings ----
    myBookings: 'Mis reservas',
    noBookings: 'No tienes reservas',
    receipt: 'Recibo',
    statusPending: 'pendiente',
    statusConfirmed: 'confirmada',
    statusActive: 'activa',
    statusCompleted: 'completada',
    statusCancelled: 'cancelada',
    paidStatus: 'PAGADO',
    unpaidStatus: 'POR PAGAR',
    refundedStatus: 'REEMBOLSADO',

    // ---- Biometric ----
    biometricLogin: 'Acceso biométrico',
    enableBiometric: 'Activar acceso biométrico',
    biometricPrompt: 'Inicia sesión con biometría',
    biometricUnavailable: 'La autenticación biométrica no está disponible en este dispositivo',
    biometricEnabled: 'Acceso biométrico activado',
    biometricDisabled: 'Acceso biométrico desactivado',
    enableBiometricSub: 'Inicia sesión más rápido la próxima vez con Face ID, Touch ID o tu huella.',
    yes: 'Sí, activar',
    notNow: 'Ahora no',
    signInWithBiometric: 'Iniciar sesión con Face ID / Huella',
    // Type-specific labels
    faceIdTitle: 'Face ID',
    touchIdTitle: 'Touch ID',
    fingerprintTitle: 'Huella digital',
    biometricGenericTitle: 'Acceso biométrico',
    biometricEnableSubFace: 'Inicia sesión más rápido con una mirada usando Face ID.',
    biometricEnableSubTouch: 'Inicia sesión más rápido con tu dedo usando Touch ID.',
    biometricEnableSubFinger: 'Inicia sesión más rápido con tu huella digital.',
    biometricOnFace: 'Face ID está activado. Inicia sesión con una mirada.',
    biometricOnTouch: 'Touch ID está activado. Inicia sesión con tu dedo.',
    biometricOnFinger: 'La huella está activada. Toca para iniciar sesión.',
    // Confirm password modal
    confirmPasswordTitle: 'Confirma tu contraseña',
    confirmPasswordSub: 'Por seguridad, ingresa tu contraseña para activar el acceso biométrico.',
    cancelBtn: 'Cancelar',
    enableBtn: 'Activar',
    wrongPassword: 'Contraseña incorrecta. Inténtalo de nuevo.',
    biometricEnableSuccess: 'Acceso biométrico activado.',
    biometricNotEnrolled: 'No hay datos biométricos registrados en este dispositivo. Configura Face ID / Touch ID en Ajustes primero.',
    biometricUnenrolledTitle: 'Configura Face ID / Touch ID',

    // ---- Receipt ----
    rentalReceipt: 'Recibo de renta',
    receiptNumber: 'Recibo #',
    issued: 'Emitido',
    billedTo: 'Facturado a',
    rentalDetails: 'Detalles de la renta',
    costBreakdown: 'Desglose de costos',
    pickup: 'Recogida',
    dropoff: 'Entrega',
    duration: 'Duración',
    payment: 'Pago',
    grandTotal: 'Total general',
    dailyRate: 'Tarifa diaria',
    downloadPdf: 'Descargar recibo PDF',
    sharePdf: 'Compartir recibo PDF',
    thankYou: 'Gracias por elegir DAMS Renta de Autos.',

    // ---- Profile ----
    profile: 'Perfil',
    accountDetails: 'Detalles de la cuenta',
    settings: 'Configuración',
    language: 'Idioma',
    english: 'English',
    spanish: 'Español',
    logout: 'Cerrar sesión',
    editProfile: 'Editar perfil',
    save: 'Guardar',
    cancel: 'Cancelar',
    member: 'Miembro',
    manageLocations: 'Administrar Ubicaciones',

    // ---- Misc ----
    loading: 'Cargando...',
    error: 'Error',
    retry: 'Reintentar',
    back: 'Atrás',
    close: 'Cerrar',
    sessionExpired: 'Sesión expirada. Inicia sesión de nuevo.',
    networkError: 'Error de red. Verifica tu conexión.',
  },
};

const i18n = new I18n(translations);
i18n.enableFallback = true;
i18n.defaultLocale = 'en';

const STORAGE_KEY = 'app_locale';

export type AppLocale = 'en' | 'es';

export async function loadSavedLocale(): Promise<AppLocale> {
  try {
    const saved = await AsyncStorage.getItem(STORAGE_KEY);
    if (saved === 'en' || saved === 'es') {
      i18n.locale = saved;
      return saved;
    }
  } catch {}
  // Fallback to device locale, defaulting to English for non-ES devices
  const deviceLocale = Localization.getLocales()[0]?.languageCode || 'en';
  const initial: AppLocale = deviceLocale.startsWith('es') ? 'es' : 'en';
  i18n.locale = initial;
  return initial;
}

export async function setLocale(locale: AppLocale) {
  i18n.locale = locale;
  try {
    await AsyncStorage.setItem(STORAGE_KEY, locale);
  } catch {}
}

export function t(key: string, opts?: Record<string, unknown>): string {
  return i18n.t(key, opts);
}

export default i18n;
