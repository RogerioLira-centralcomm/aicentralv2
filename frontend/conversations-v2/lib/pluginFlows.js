// Group and mode descriptions come from the agent capability contract.
export function availableFlows(plugins, flowCatalog = []) {
  const all = new Map((plugins || []).map(plugin => [plugin.id, plugin]));
  const entries = new Map((plugins || []).filter(plugin => plugin.selectable &&
    ['active', 'in_development'].includes(plugin.maturity)).map(plugin => [plugin.id, plugin]));
  return (flowCatalog || []).map(flow => ({
    ...flow,
    availableModes: (flow.modes || []).map(mode => ({...mode, plugin: entries.get(mode.id)}))
      .filter(mode => mode.plugin),
    upcomingModes: (flow.modes || []).filter(mode => all.has(mode.id) && !entries.has(mode.id)),
  })).filter(flow => flow.availableModes.length);
}

export function flowPluginIds(flowCatalog = []) {
  return new Set((flowCatalog || []).flatMap(flow => (flow.modes || []).map(mode => mode.id)));
}
