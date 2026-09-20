function messageMetadata(item) {
  return item?.metadata && typeof item.metadata === 'object' ? item.metadata : {};
}

export function recentConversations(items, limit = 30) {
  return (Array.isArray(items) ? items : [])
    .filter(item => !['arquivada', 'archived'].includes(String(item?.status || '').toLowerCase()))
    .slice(0, limit);
}

export function restoreConversationMessages(items, makeId) {
  let lastArtifact = '';
  let selectedContext = null;

  const messages = (Array.isArray(items) ? items : []).map(item => {
    const metadata = messageMetadata(item);
    if (item.role === 'user') {
      if (metadata.selected_context) selectedContext = metadata.selected_context;
      return {
        id: makeId(),
        role: 'user',
        content: item.content || '',
        files: item.files || [],
      };
    }

    const response = metadata.response && typeof metadata.response === 'object'
      ? {...metadata.response, answer: metadata.response.answer || item.content || ''}
      : {answer: item.content || ''};
    if (metadata.artifact_id) lastArtifact = String(metadata.artifact_id);
    return {
      id: makeId(),
      role: 'assistant',
      response,
      artifact: metadata.artifact_id ? {
        id: String(metadata.artifact_id),
        title: response.artifact_patch?.title || 'artefato',
        type: response.artifact_patch?.type,
      } : null,
    };
  });

  return {messages, selectedContext, lastArtifact};
}
