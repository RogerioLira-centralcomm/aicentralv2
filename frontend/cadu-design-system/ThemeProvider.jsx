import React, {createContext, useContext, useLayoutEffect, useMemo, useState} from 'react';

const ThemeContext = createContext(null);

export function ThemeProvider({children, skin = 'workspace', theme = 'light', persistKey = 'cadu-theme'}) {
  const [currentTheme, setCurrentTheme] = useState(() => {
    if (typeof window === 'undefined') return theme;
    return window.localStorage.getItem(persistKey) || theme;
  });
  const value = useMemo(() => ({skin, theme: currentTheme, setTheme: setCurrentTheme, toggleTheme: () => setCurrentTheme(item => item === 'dark' ? 'light' : 'dark')}), [skin, currentTheme]);
  // Applying before paint avoids the light-to-dark flash when a React surface
  // replaces the portal shell. Theme changes remain local to each product.
  useLayoutEffect(() => { document.documentElement.dataset.caduTheme = currentTheme; document.documentElement.dataset.caduSkin = skin; window.localStorage.setItem(persistKey, currentTheme); }, [currentTheme, persistKey, skin]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useCaduTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useCaduTheme precisa estar dentro de ThemeProvider.');
  return context;
}
