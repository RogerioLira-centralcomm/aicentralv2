// Untitled UI React v8 base Dropdown (react-aria-components Menu), adapted to the CADU kit conventions.
// Upstream: https://www.untitledui.com/react/base/dropdowns
import type { ReactNode } from "react";
import React from "react";
import type { MenuItemProps as AriaMenuItemProps, MenuProps as AriaMenuProps, PopoverProps as AriaPopoverProps } from "react-aria-components";
import { Menu as AriaMenu, MenuItem as AriaMenuItem, MenuTrigger as AriaMenuTrigger, Popover as AriaPopover, Separator as AriaSeparator } from "react-aria-components";
import { cx } from "./utils/cx";

export const DropdownRoot = AriaMenuTrigger;

export function DropdownPopover({ className, ...props }: AriaPopoverProps) {
    return (
        <AriaPopover
            placement="bottom start"
            offset={6}
            {...props}
            className={(state) =>
                cx(
                    "z-50 min-w-56 origin-(--trigger-anchor-point) overflow-auto rounded-lg bg-primary py-1 shadow-lg ring-1 ring-secondary_alt outline-hidden will-change-transform",
                    state.isEntering && "duration-150 ease-out animate-in fade-in",
                    state.isExiting && "duration-100 ease-in animate-out fade-out",
                    typeof className === "function" ? className(state) : className,
                )
            }
        />
    );
}

export function DropdownMenu<T extends object>(props: AriaMenuProps<T>) {
    return <AriaMenu {...props} className={(state) => cx("outline-hidden", typeof props.className === "function" ? props.className(state) : props.className)} />;
}

interface DropdownItemProps extends Omit<AriaMenuItemProps, "children"> {
    children: ReactNode;
    destructive?: boolean;
}

export function DropdownItem({ children, destructive, className, ...props }: DropdownItemProps) {
    return (
        <AriaMenuItem
            {...props}
            className={(state) =>
                cx(
                    "mx-1 flex cursor-pointer items-center rounded-md px-2.5 py-2 text-sm font-medium outline-hidden select-none",
                    destructive ? "text-error-primary" : "text-secondary",
                    state.isFocused && "bg-primary_hover",
                    state.isDisabled && "cursor-not-allowed opacity-50",
                    typeof className === "function" ? className(state) : className,
                )
            }
        >
            {children}
        </AriaMenuItem>
    );
}

export function DropdownSeparator() {
    return <AriaSeparator className="my-1 h-px bg-border-secondary" />;
}

export const Dropdown = {
    Root: DropdownRoot,
    Popover: DropdownPopover,
    Menu: DropdownMenu,
    Item: DropdownItem,
    Separator: DropdownSeparator,
};
