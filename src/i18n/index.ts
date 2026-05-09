import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { getSavedLanguage } from './languageDetection';

import commonEn from '../locales/en/common.json';
import dashboardEn from '../locales/en/dashboard.json';
import settingsEn from '../locales/en/settings.json';

const resources = {
  en: {
    common: commonEn,
    dashboard: dashboardEn,
    settings: settingsEn,
  },
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: getSavedLanguage() || 'en',
    fallbackLng: 'en',
    defaultNS: 'common',
    ns: ['common', 'dashboard', 'settings'],
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: false,
    },
  });

export async function loadLanguage(lang: string): Promise<void> {
  if (lang === 'en' || !lang) {
    await i18n.changeLanguage('en');
    return;
  }

  try {
    const common = await import(`../locales/${lang}/common.json`);
    i18n.addResourceBundle(lang, 'common', common.default, true, true);
  } catch {
    // Fallback to English if translation file doesn't exist yet
  }

  // Load page-specific namespaces lazily as they're needed
  await i18n.changeLanguage(lang);
}

export async function loadNamespace(lang: string, ns: string): Promise<void> {
  if (lang === 'en' || i18n.hasResourceBundle(lang, ns)) return;

  try {
    const module = await import(`../locales/${lang}/${ns}.json`);
    i18n.addResourceBundle(lang, ns, module.default, true, true);
  } catch {
    // Fallback to English
  }
}

export default i18n;
