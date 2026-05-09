import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { getDirection } from './languageDetection';

export function useDirection() {
  const { i18n } = useTranslation();

  useEffect(() => {
    const dir = getDirection(i18n.language);
    document.documentElement.setAttribute('dir', dir);
    document.documentElement.setAttribute('lang', i18n.language);
  }, [i18n.language]);
}
