import React, {useEffect, useRef} from 'react';

export function ConfirmDialog({request, onResolve}) {
  const dialog = useRef(null);
  useEffect(() => {
    if (request && !dialog.current?.open) dialog.current?.showModal();
  }, [request]);
  if (!request) return null;
  const finish = value => {
    dialog.current?.close();
    onResolve(value);
  };
  return <dialog ref={dialog} onCancel={event => { event.preventDefault(); finish(false); }} className="cv-dialog cv-w-[min(440px,calc(100vw-32px))] cv-p-0">
    <section className="cv-p-6">
      <h2 className="cv-m-0 cv-text-lg cv-font-semibold">Descartar alterações?</h2>
      <p className="cv-mb-0 cv-mt-3 cv-text-sm cv-leading-6 cv-text-mist">{request.copy}</p>
      <div className="cv-mt-6 cv-flex cv-justify-end cv-gap-2">
        <button type="button" autoFocus onClick={() => finish(false)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold hover:cv-bg-white/[.05]">Continuar editando</button>
        <button type="button" onClick={() => finish(true)} className="cv-rounded-lg cv-border-0 cv-bg-[#c85d64] cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-white hover:cv-bg-[#dc6c73]">Descartar</button>
      </div>
    </section>
  </dialog>;
}
