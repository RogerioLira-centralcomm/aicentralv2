// Projetos criados antes da tradução guardam o nome padrão do OpenCut; na tela ele aparece em português.
export function sceneLabel(name: string | undefined): string {
	if (!name) return "Sem cena";
	return name === "Main scene" ? "Cena principal" : name;
}
