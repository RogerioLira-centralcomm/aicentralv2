import React from 'react';

export const FLOW_PLATFORMS = {
  google: {label: 'Google Ads', logo: '/static/images/cadu/technology-logos/google.svg'},
  youtube: {label: 'YouTube Ads', logo: '/static/images/creative-viewers/youtube.svg'},
  facebook: {label: 'Facebook Ads', logo: '/static/images/creative-viewers/facebook.svg'},
  instagram: {label: 'Instagram Ads', logo: '/static/images/creative-viewers/instagram.svg'},
  dv360: {label: 'Display & Video 360', logo: '/static/images/canais/google-dv360.svg'},
  meta: {label: 'Meta Ads'},
  linkedin: {label: 'LinkedIn Ads', logo: '/static/images/creative-viewers/linkedin.svg'},
  tiktok: {label: 'TikTok Ads', logo: '/static/images/canais/tiktok.png'},
  whatsapp: {label: 'WhatsApp', logo: '/static/images/canais/whatsapp.svg'},
  amazon_ads: {label: 'Amazon Ads', wordmark: 'amazon'},
  spotify_ads: {label: 'Spotify Ads', logo: '/static/images/canais/spotify.svg'},
  netflix_ads: {label: 'Netflix Ads', logo: '/static/images/creative-viewers/netflix.png'},
  serasa: {label: 'Serasa', wordmark: 'serasa'},
  disney_ads: {label: 'Disney Ads', logo: '/static/images/creative-viewers/disney-plus.png'},
  email: {label: 'E-mail', wordmark: 'email'},
};


export function FlowPlatformLogo({platform}) {
  const brand = FLOW_PLATFORMS[platform] || FLOW_PLATFORMS[({google_ads:'google',meta_ads:'meta',linkedin_ads:'linkedin',tiktok_ads:'tiktok'})[platform]];
  if (!brand) return <span className="reports-flow-brand-fallback" aria-hidden="true">◇</span>;
  if (platform === 'meta' || platform === 'meta_ads') return <svg className="reports-flow-brand-mark is-meta" viewBox="0 0 44 28" role="img" aria-label="Meta"><path d="M3 19c4-11 8-14 12-10l8 11c4 5 8 2 12-8 2-6 5-7 7-1 3 8-1 14-6 12-3-1-6-5-9-9l-6-8C16 1 11 5 6 14l-3 5" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"/></svg>;
  if (brand.wordmark === 'amazon') return <svg className="reports-flow-brand-mark is-amazon" viewBox="0 0 48 28" role="img" aria-label="Amazon"><text x="2" y="17" fontSize="15" fontWeight="700" fill="currentColor">amazon</text><path d="M10 21c10 6 23 6 32-1m0 0-5-1m5 1-2 4" fill="none" stroke="#f0a323" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>;
  if (brand.wordmark === 'serasa') return <span className="reports-brand-wordmark is-serasa" aria-label="Serasa">serasa</span>;
  if (brand.wordmark === 'email') return <svg className="reports-flow-brand-mark is-email" viewBox="0 0 24 24" role="img" aria-label="E-mail"><path d="M3 5h18v14H3zM4 7l8 6 8-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/></svg>;
  return <img className="reports-flow-brand-mark" src={brand.logo} alt={brand.label} draggable="false" />;
}

