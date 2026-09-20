export function projectContextPayload(projectRef) {
  return {project_ref: projectRef || null, brand_ref: null};
}

export function conversationPayload({
  message,
  requestId,
  conversationId,
  providerFileIds,
  executionMode,
  context,
  selectedContext,
  activeArtifact,
}) {
  return {
    message,
    request_id: requestId,
    conversation_id: conversationId,
    surface: 'conversations',
    files: providerFileIds,
    execution_mode: executionMode,
    project_ref: context?.project_ref || null,
    brand_ref: context?.brand_ref || null,
    selected_context: selectedContext ? {type: selectedContext.type, text: selectedContext.text} : null,
    active_object: activeArtifact?.id
      ? {type: `artifact:${activeArtifact.type}`, id: activeArtifact.id}
      : null,
  };
}
