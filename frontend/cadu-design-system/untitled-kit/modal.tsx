// Source: Untitled UI React v8, components/application/modals/modal.tsx.
import React from 'react';
import type { DialogProps as AriaDialogProps, ModalOverlayProps as AriaModalOverlayProps } from 'react-aria-components';
import { Dialog as AriaDialog, DialogTrigger as AriaDialogTrigger, Modal as AriaModal, ModalOverlay as AriaModalOverlay } from 'react-aria-components';
import { cx } from './utils/cx';

export const DialogTrigger = AriaDialogTrigger;

export const ModalOverlay = (props: AriaModalOverlayProps) => <AriaModalOverlay {...props} className={state => cx('fixed inset-0 z-50 flex min-h-dvh w-full items-end justify-center bg-overlay/70 px-4 outline-hidden backdrop-blur-[6px] sm:items-center sm:px-8', 'pt-(--modal-pt) pb-(--modal-pb) [--modal-pb:clamp(16px,8vh,64px)] [--modal-pt:16px] sm:[--modal-pb:32px] sm:[--modal-pt:32px]', state.isEntering && 'duration-300 ease-out animate-in fade-in', state.isExiting && 'duration-200 ease-in animate-out fade-out', typeof props.className === 'function' ? props.className(state) : props.className)} />;

export const Modal = (props: AriaModalOverlayProps) => <AriaModal {...props} className={state => cx('w-full rounded-xl bg-primary align-middle shadow-xl outline-hidden max-sm:overflow-y-auto sm:rounded-2xl', 'max-h-[calc(var(--visual-viewport-height)-var(--modal-pt)-var(--modal-pb))]', state.isEntering && 'duration-300 ease-out animate-in zoom-in-95', state.isExiting && 'duration-200 ease-in animate-out zoom-out-95', typeof props.className === 'function' ? props.className(state) : props.className)} />;

export const Dialog = (props: AriaDialogProps) => <AriaDialog {...props} className={cx('relative max-h-[inherit] w-full overflow-y-auto outline-hidden', props.className)} />;
