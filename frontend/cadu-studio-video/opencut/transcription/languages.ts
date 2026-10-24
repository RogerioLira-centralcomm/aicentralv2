export const LANGUAGES = [
	{ code: "en", name: "Inglês" },
	{ code: "es", name: "Espanhol" },
	{ code: "it", name: "Italiano" },
	{ code: "fr", name: "Francês" },
	{ code: "de", name: "Alemão" },
	{ code: "pt", name: "Português" },
	{ code: "ru", name: "Russo" },
	{ code: "ja", name: "Japonês" },
	{ code: "zh", name: "Chinês" },
] as const;

export type Language = (typeof LANGUAGES)[number];
export type LanguageCode = Language["code"];
