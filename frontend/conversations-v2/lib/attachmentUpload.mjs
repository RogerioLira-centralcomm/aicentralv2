export async function uploadAttachments({
  attachments,
  projectRef,
  uploadsEndpoint,
  requestFn,
  fetchFn,
  csrfToken,
  uuid,
  onProgress,
  mcpEndpoint = '/workspace/mcp',
}) {
  const staged = [...attachments];
  const publish = () => onProgress?.([...staged]);

  for (let index = 0; index < staged.length; index += 1) {
    if (staged[index].id || staged[index].source) continue;
    staged[index] = {...staged[index], uploading: true, error: false};
    publish();
    try {
      if (staged[index].destination === 'conversation') {
        const body = new FormData();
        body.append('file', staged[index].file);
        const response = await fetchFn(uploadsEndpoint, {
          method: 'POST', credentials: 'same-origin', headers: {'X-CSRF-Token': csrfToken()}, body,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.file?.id) throw new Error(data.error || 'Não foi possível anexar o arquivo.');
        staged[index] = {...staged[index], id: data.file.id, uploading: false};
      } else {
        if (!projectRef) throw new Error('Escolha um projeto antes de adicionar arquivos a ele.');
        const prepared = await requestFn(mcpEndpoint, {
          method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken()},
          body: JSON.stringify({jsonrpc: '2.0', id: uuid(), method: 'tools/call', params: {
            name: 'projects.prepare_source_upload', surface: 'conversations', project_ref: projectRef, arguments: {
              request_id: uuid(), use_as_knowledge: staged[index].destination === 'knowledge',
            },
          }}),
        });
        const intent = prepared.result?.structuredContent;
        if (prepared.result?.isError || !intent?.upload_token) {
          throw new Error(prepared.result?.content?.[0]?.text || 'Não foi possível preparar o arquivo para o projeto.');
        }
        const body = new FormData();
        body.append('upload_token', intent.upload_token);
        body.append('file', staged[index].file);
        const response = await fetchFn(intent.upload_url, {
          method: 'POST', credentials: 'same-origin', headers: {'X-CSRF-Token': csrfToken()}, body,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.source?.source_id) throw new Error(data.error || 'Não foi possível adicionar o arquivo ao projeto.');
        staged[index] = {...staged[index], source: data.source, uploading: false};
      }
    } catch (error) {
      staged[index] = {...staged[index], uploading: false, error: true};
      publish();
      throw error;
    }
    publish();
  }
  return staged;
}
