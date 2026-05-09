export type SupportedLanguage = 'en' | 'hi' | 'de' | 'fr' | 'nl' | 'ar' | 'ms' | 'ja' | 'ko' | 'pt' | 'es';

const COUNTRY_TO_LANGUAGE: Record<string, SupportedLanguage> = {
  US: 'en', GB: 'en', AU: 'en', CA: 'en', NZ: 'en', IE: 'en', SG: 'en',
  IN: 'hi',
  DE: 'de',
  FR: 'fr',
  NL: 'nl',
  AE: 'ar',
};

export const LANGUAGE_NAMES: Record<SupportedLanguage, string> = {
  en: 'English',
  hi: 'हिन्दी (Hindi)',
  de: 'Deutsch (German)',
  fr: 'Français (French)',
  nl: 'Nederlands (Dutch)',
  ar: 'العربية (Arabic)',
  ms: 'Bahasa Melayu (Malay)',
  ja: '日本語 (Japanese)',
  ko: '한국어 (Korean)',
  pt: 'Português (Portuguese)',
  es: 'Español (Spanish)',
};

const STORAGE_KEY = 'langhire_language';

export function getLanguageFromCountry(countryCode: string): SupportedLanguage {
  return COUNTRY_TO_LANGUAGE[countryCode] || 'en';
}

export function getSavedLanguage(): SupportedLanguage | null {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && saved in LANGUAGE_NAMES) return saved as SupportedLanguage;
  return null;
}

export function saveLanguagePreference(lang: string): void {
  if (lang) {
    localStorage.setItem(STORAGE_KEY, lang);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

export function getDirection(lang: string): 'ltr' | 'rtl' {
  return lang === 'ar' ? 'rtl' : 'ltr';
}
