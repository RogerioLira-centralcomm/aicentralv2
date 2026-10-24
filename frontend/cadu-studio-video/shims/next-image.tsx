// Substitui next/image no editor: o Studio serve imagens já dimensionadas.
import type { ImgHTMLAttributes } from "react";

type Props = ImgHTMLAttributes<HTMLImageElement> & {
	src: string | { src: string };
	fill?: boolean;
	priority?: boolean;
	unoptimized?: boolean;
	quality?: number;
};

export default function Image({ src, fill, priority, unoptimized, quality, style, ...rest }: Props) {
	const url = typeof src === "string" ? src : src.src;
	const fillStyle = fill ? { position: "absolute" as const, inset: 0, width: "100%", height: "100%" } : {};
	return <img src={url} loading={priority ? "eager" : "lazy"} style={{ ...fillStyle, ...style }} {...rest} />;
}
