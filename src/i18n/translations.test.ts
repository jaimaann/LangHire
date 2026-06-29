import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { LANGUAGE_NAMES, getLanguageFromCountry } from './languageDetection';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = path.resolve(__dirname, '../locales');
const EN_DIR = path.join(LOCALES_DIR, 'en');

const TARGET_LANGUAGES = ['it', 'zh'];

const EN_FILES = fs
  .readdirSync(EN_DIR)
  .filter((f) => f.endsWith('.json'))
  .sort();

type JsonValue = string | number | boolean | null | JsonObject | JsonValue[];
interface JsonObject {
  [key: string]: JsonValue;
}

function readJson(filePath: string): JsonObject {
  return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as JsonObject;
}

/** Recursively flatten an object into dot-separated key paths. */
function flattenKeys(obj: JsonObject, prefix = ''): string[] {
  const keys: string[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      keys.push(...flattenKeys(value as JsonObject, fullKey));
    } else {
      keys.push(fullKey);
    }
  }
  return keys.sort();
}

/** Collect every string leaf value keyed by its flattened path. */
function flattenValues(obj: JsonObject, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(out, flattenValues(value as JsonObject, fullKey));
    } else if (typeof value === 'string') {
      out[fullKey] = value;
    }
  }
  return out;
}

/** Extract {{placeholder}} tokens from a string. */
function extractPlaceholders(s: string): string[] {
  return (s.match(/\{\{\s*[^}]+\s*\}\}/g) ?? []).sort();
}

describe('translation file parity', () => {
  it('has at least the expected English locale files', () => {
    expect(EN_FILES.length).toBeGreaterThanOrEqual(13);
  });

  for (const lang of TARGET_LANGUAGES) {
    describe(`language: ${lang}`, () => {
      const langDir = path.join(LOCALES_DIR, lang);

      it(`has a ${lang} locale directory`, () => {
        expect(fs.existsSync(langDir)).toBe(true);
      });

      for (const file of EN_FILES) {
        describe(`file: ${file}`, () => {
          const enPath = path.join(EN_DIR, file);
          const langPath = path.join(langDir, file);

          it('exists', () => {
            expect(fs.existsSync(langPath)).toBe(true);
          });

          it('is valid JSON', () => {
            expect(() => readJson(langPath)).not.toThrow();
          });

          it('has identical (flattened) keys to en', () => {
            const enKeys = flattenKeys(readJson(enPath));
            const langKeys = flattenKeys(readJson(langPath));
            expect(langKeys).toEqual(enKeys);
          });

          it('preserves {{placeholder}} tokens', () => {
            const enValues = flattenValues(readJson(enPath));
            const langValues = flattenValues(readJson(langPath));
            for (const [key, enValue] of Object.entries(enValues)) {
              const enTokens = extractPlaceholders(enValue);
              if (enTokens.length === 0) continue;
              const langValue = langValues[key];
              expect(langValue, `missing string value for ${file}:${key}`).toBeTypeOf('string');
              expect(
                extractPlaceholders(langValue),
                `placeholder mismatch for ${file}:${key}`
              ).toEqual(enTokens);
            }
          });
        });
      }
    });
  }
});

describe('languageDetection metadata', () => {
  it('LANGUAGE_NAMES contains it and zh', () => {
    expect(LANGUAGE_NAMES.it).toBeDefined();
    expect(LANGUAGE_NAMES.zh).toBeDefined();
    expect(LANGUAGE_NAMES.it).toBe('Italiano');
    expect(LANGUAGE_NAMES.zh).toBe('中文');
  });

  it('maps country IT to it', () => {
    expect(getLanguageFromCountry('IT')).toBe('it');
  });

  it('maps country CN to zh', () => {
    expect(getLanguageFromCountry('CN')).toBe('zh');
  });
});
