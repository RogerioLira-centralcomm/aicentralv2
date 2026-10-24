// Substitui next/link: o editor roda numa página só do Flask.
import { forwardRef, type AnchorHTMLAttributes } from "react";

type Props = AnchorHTMLAttributes<HTMLAnchorElement> & { href: string; prefetch?: boolean };

const Link = forwardRef<HTMLAnchorElement, Props>(function Link({ prefetch, ...rest }, ref) {
	return <a ref={ref} {...rest} />;
});

export default Link;
