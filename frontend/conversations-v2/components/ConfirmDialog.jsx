import React, {useRef} from 'react';
import {CaduDialog} from '../../cadu-design-system/components/CaduDialog';

export function ConfirmDialog({request, onResolve}) {
  const cancelButton = useRef(null);
  if (!request) return null;
  const finish = value => onResolve(value);
  return <CaduDialog label="Descartar alterações?" initialFocusRef={cancelButton} onClose={() => finish(false)} className="cv-dialog cv-w-[min(440px,calc(100vw-32px))] cv-p-0">
    <section className="cv-p-6">
      <h2 className="cv-m-0 cv-text-lg cv-font-semibold">Descartar alterações?</h2>
      <p className="cv-mb-0 cv-mt-3 cv-text-sm cv-leading-6 cv-text-mist">{request.copy}</p>
      <div className="cv-mt-6 cv-flex cv-justify-end cv-gap-2">
        <button ref={cancelButton} type="button" onClick={() => finish(false)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold hover:cv-bg-white/[.05]">Continuar editando</button>
        <button type="button" onClick={() => finish(true)} className="cv-rounded-lg cv-border-0 cv-bg-[#c85d64] cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-white hover:cv-bg-[#dc6c73]">Descartar</button>
      </div>
    </section>
  </CaduDialog>;
}
