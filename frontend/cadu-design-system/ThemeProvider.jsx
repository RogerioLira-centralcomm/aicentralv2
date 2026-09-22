import React, {createContext, useContext, useLayoutEffect, useMemo, useState} from 'react';

const ThemeContext = createContext(null);

export function ThemeProvider({children, skin = 'workspace', theme = 'light', persistKey = 'cadu-theme', locked = false}) {
  const [currentTheme, setCurrentTheme] = useState(() => {
    if (locked || typeof window === 'undefined') return theme;
    return window.localStorage.getItem(persistKey) || theme;
  });
  const resolvedTheme = locked ? theme : currentTheme;
  const value = useMemo(() => ({skin, theme: resolvedTheme, setTheme: locked ? () => {} : setCurrentTheme, toggleTheme: locked ? () => {} : () => setCurrentTheme(item => item === 'dark' ? 'light' : 'dark')}), [skin, resolvedTheme, locked]);
  // Applying before paint avoids the light-to-dark flash when a React surface
  // replaces the portal shell. Theme changes remain local to each product.
  useLayoutEffect(() => {
    document.documentElement.dataset.caduTheme = resolvedTheme;
    document.documentElement.dataset.caduSkin = skin;
    if (!locked) window.localStorage.setItem(persistKey, resolvedTheme);
  }, [locked, persistKey, resolvedTheme, skin]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useCaduTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useCaduTheme precisa estar dentro de ThemeProvider.');
  return context;
}
