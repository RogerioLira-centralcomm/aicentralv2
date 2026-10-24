// O Studio é dark-only: tema fixo, sem alternância.
export function useTheme() {
	return { theme: "dark", resolvedTheme: "dark", setTheme: () => undefined, themes: ["dark"] };
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
	return <>{children}</>;
}
