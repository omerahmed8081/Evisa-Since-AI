import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { en, type Dict } from "./en";
import { fi } from "./fi";

export { en, fi };
export type { Dict };

export type Lang = "en" | "fi";

const KEY = "uiLanguage";
const DICTS: Record<Lang, Dict> = { en, fi };

/** Saved choice wins; otherwise Finnish browsers get Finnish, everyone else English. */
function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "fi" || saved === "en") return saved;
  } catch {
    /* ignore */
  }
  try {
    if (navigator.language?.toLowerCase().startsWith("fi")) return "fi";
  } catch {
    /* ignore */
  }
  return "en";
}

// Defaults let components render without a provider (tests, storybook-style usage).
const DictContext = createContext<Dict>(en);
const LangContext = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({ lang: "en", setLang: () => {} });

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => setLangState(initialLang()), []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* ignore */
    }
  };

  return (
    <LangContext.Provider value={{ lang, setLang }}>
      <DictContext.Provider value={DICTS[lang]}>{children}</DictContext.Provider>
    </LangContext.Provider>
  );
}

/** The active UI dictionary. */
export function useT(): Dict {
  return useContext(DictContext);
}

/** The active language and its setter. */
export function useLanguage() {
  return useContext(LangContext);
}
