// Untitled UI React v8 foundations Dot (official Vite starter via untitledui CLI, 2026-10-02).
// Upstream: https://www.untitledui.com/react/foundations
import type { HTMLAttributes } from "react";

const sizes = {
    sm: {
        wh: 8,
        c: 4,
        r: 2.5,
    },
    md: {
        wh: 10,
        c: 5,
        r: 4,
    },
};

export const Dot = ({ size = "md", ...props }: HTMLAttributes<HTMLOrSVGElement> & { size?: "sm" | "md" }) => {
    return (
        <svg width={sizes[size].wh} height={sizes[size].wh} viewBox={`0 0 ${sizes[size].wh} ${sizes[size].wh}`} fill="none" {...props}>
            <circle cx={sizes[size].c} cy={sizes[size].c} r={sizes[size].r} fill="currentColor" stroke="currentColor" />
        </svg>
    );
};
