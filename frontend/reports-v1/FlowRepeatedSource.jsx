import './flow-sources.css';
import React, {useState} from 'react';
import {Dialog, Modal, ModalOverlay} from 'react-aria-components';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {CaduTextField} from '../cadu-design-system/components/CaduField.jsx';
import {isSearchSource} from './flowValidation.js';
import {SEARCH_ENGINES, channelLabel, conflictingSource, distinctCampaign, freeSearchEngines, utmInput, withCampaign} from './flowSourceIdentity.js';

/**
 * Asked when an origin already on the map is added again. Two Instagram origins only stay apart in the
 * reports with different utm_campaign values; two search origins only with different engines.
 * `pending` = {nodes: the new origin nodes, config: the map before adding, flowName, apply, existing}.
 */
export function FlowRepeatedSource({pending, onResolve, onCancel}) {
  const node = pending.nodes[0];
  const search = isSearchSource(node);
  const label = channelLabel(node);
  const [campaign, setCampaign] = useState(() => distinctCampaign(pending.config.nodes, node, pending.flowName));
  const free = search ? freeSearchEngines(pending.config.nodes) : [];
  const [engines, setEngines] = useState(() => free.slice(0, 1));
  const takenCampaign = !search && Boolean(conflictingSource(pending.config.nodes, withCampaign(node, campaign)));
  const toggle = id => setEngines(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
  const canAdd = search ? engines.length > 0 : Boolean(campaign) && !takenCampaign;
  return <ModalOverlay className="cadu-ds-overlay cadu-ds-overlay--center" isOpen isDismissable onOpenChange={open => { if (!open) onCancel(); }}>
    <Modal className="cadu-ds-confirm flow-repeat-source">
      <Dialog aria-label={search ? 'Escolher buscadores' : `${label} repetido`} className="cadu-ds-confirm__dialog">
        {search ? <>
          <h2>Busca orgânica já está no fluxo</h2>
          <p>Cada buscador entra em uma única origem, para que as visitas de Google, Bing e os demais apareçam separadas no monitoramento e nos relatórios.</p>
          {free.length ? <fieldset className="flow-repeat-source__engines">
            <legend>Buscadores desta origem</legend>
            {SEARCH_ENGINES.map(([id, name]) => <label key={id} className={free.includes(id) ? '' : 'is-taken'}>
              <input type="checkbox" checked={engines.includes(id)} disabled={!free.includes(id)} onChange={() => toggle(id)}/>
              <span>{name}</span>{!free.includes(id) && <small>em outra origem</small>}
            </label>)}
          </fieldset> : <p className="flow-repeat-source__note">Todos os buscadores já estão em outra origem de busca. Ajuste os buscadores dela no painel da origem.</p>}
        </> : <>
          <h2>{label} já está no fluxo. É outra campanha?</h2>
          <p>Sem uma <code>utm_campaign</code> própria, as visitas das duas origens chegam iguais e não é possível separar qual campanha trouxe cada pessoa.</p>
          <CaduTextField label="utm_campaign desta origem" value={campaign} maxLength={100} onChange={event => setCampaign(utmInput(event.target.value))}
            hint={takenCampaign ? 'Outra origem deste canal já usa este valor.' : 'Use o mesmo valor nos links dos anúncios desta campanha.'}/>
        </>}
        <div className="cadu-ds-confirm__actions">
          <Button color="secondary" size="sm" onPress={onCancel}>{search ? 'Cancelar' : 'É a mesma campanha'}</Button>
          <Button color="primary" size="sm" isDisabled={!canAdd} onPress={() => onResolve(search ? {engines} : {campaign: campaign.replace(/^-+|-+$/g, '')})}>{search ? 'Adicionar busca' : 'Adicionar outra campanha'}</Button>
        </div>
      </Dialog>
    </Modal>
  </ModalOverlay>;
}
