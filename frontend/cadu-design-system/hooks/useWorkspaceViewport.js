import {useUnifiedViewport} from './useUnifiedViewport';

// Same breakpoints as the Workspace CSS (560 / 760 / 1024), so React chrome and CSS switch together.
const WORKSPACE_QUERIES = {phone: '(max-width: 760px)', tablet: '(min-width: 761px) and (max-width: 1024px)'};

export function useWorkspaceViewport() {
  return useUnifiedViewport(WORKSPACE_QUERIES);
}
