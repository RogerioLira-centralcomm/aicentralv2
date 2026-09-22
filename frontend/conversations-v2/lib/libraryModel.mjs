function reference(prefix, value) {
  const id = String(value || '');
  return id.startsWith(`${prefix}:`) ? id : `${prefix}:${id}`;
}

export function libraryGroups(data = {}) {
  const asset = (item, source) => {
    const libraryRef = reference(source, item.id);
    const url = item.display_url || item.asset_url || item.image_url || item.url || item.asset_path || item.source_url || '';
    return {
      ...item, id: libraryRef, libraryRef,
      title: item.metadata?.display_name || item.metadata?.original_name || item.title || item.name || 'Sem título',
      preview: item.display_url || item.thumb_url || url, url,
      kind: item.role === 'logo' ? 'logo' : item.kind || 'image', source,
    };
  };
  const resource = item => {
    const libraryRef = reference('resource', item.id || `${item.source_system || 'item'}:${item.source_id || ''}`);
    return {
      ...item, id: libraryRef, libraryRef,
      title: item.title || 'Referência',
      url: item.editor_url || item.download_url || item.url || item.locator || '',
      kind: item.type || item.resource_type || 'file',
      detail: item.category || item.mime_type || '',
      project_ref: item.project_ref || data.project_ref || '',
    };
  };
  return [
    {id: 'brand', title: 'Criativos da marca', layout: 'carousel', items: (data.brand_assets || []).map(item => asset(item, 'brand'))},
    {id: 'created', title: 'Criações', layout: 'carousel', items: (data.personal_assets || []).map(item => asset(item, 'personal'))},
    {id: 'references', title: 'Arquivos e links importantes', layout: 'list', items: (data.resources || []).map(resource)},
  ];
}

export function findLibraryItem(data, libraryRef) {
  return libraryGroups(data).flatMap(group => group.items).find(item => item.libraryRef === libraryRef) || null;
}
