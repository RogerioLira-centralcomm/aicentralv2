import {useEffect, useState} from 'react';
import {CONVERSATION_MOBILE_QUERY, isConversationMobile} from '../lib/browser.mjs';

export function useResponsiveHistory(hasConversation) {
  const [historyOpen, setHistoryOpen] = useState(() => !isConversationMobile());

  useEffect(() => {
    const media = window.matchMedia(CONVERSATION_MOBILE_QUERY);
    const adaptHistory = event => {
      if (event.matches) setHistoryOpen(false);
      else if (!hasConversation) setHistoryOpen(true);
    };

    adaptHistory(media);
    if (media.addEventListener) media.addEventListener('change', adaptHistory);
    else media.addListener(adaptHistory);
    return () => {
      if (media.removeEventListener) media.removeEventListener('change', adaptHistory);
      else media.removeListener(adaptHistory);
    };
  }, [hasConversation]);

  return [historyOpen, setHistoryOpen];
}
