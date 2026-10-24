import type { ParamDefinition } from "@/params";

export type GraphicStrokeAlign = "inside" | "center" | "outside";

export const STROKE_ALIGN_PARAM: ParamDefinition<"strokeAlign"> = {
	key: "strokeAlign",
	label: "Alinhamento do contorno",
	type: "select",
	default: "center",
	group: "stroke",
	options: [
		{ value: "inside", label: "Dentro" },
		{ value: "center", label: "Centro" },
		{ value: "outside", label: "Fora" },
	],
};
