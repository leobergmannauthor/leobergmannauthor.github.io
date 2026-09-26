/* Basic consent mode: the Google tag is not downloaded before opt-in. */
(() => {
  'use strict';
  const script = document.currentScript;
  const id = script?.dataset.measurementId || '';
  if (!/^G-[A-Z0-9]+$/.test(id)) return;
  const storageKey = 'leo_analytics_consent_v1';
  const lifetime = 180 * 24 * 60 * 60 * 1000;
  const banner = document.querySelector('[data-analytics-banner]');
  const settings = document.querySelector('[data-analytics-settings]');
  const article = document.querySelector('[data-book-id]');
  let allowed = false;
  let loaded = false;
  let previousFocus = null;
  const denyAds = {ad_storage:'denied', ad_user_data:'denied', ad_personalization:'denied'};
  const campaign = new URLSearchParams(location.search);
  const cleanLocation = new URL(location.origin + location.pathname);
  for (const key of ['utm_source','utm_medium','utm_campaign','utm_content']) {
    const value = campaign.get(key) || '';
    if (/^[a-zA-Z0-9_:.\-]{1,120}$/.test(value)) cleanLocation.searchParams.set(key, value);
  }
  const candidateVariant = (campaign.get('utm_content') || '').split(':').pop();
  const context = {
    book_id: article?.dataset.bookId || 'none',
    recipe_id: article?.dataset.recipeId || 'none',
    pin_variant: ['editorial','photo','bold'].includes(candidateVariant) ? candidateVariant : 'unattributed'
  };
  function readChoice() {
    try {
      const value = JSON.parse(localStorage.getItem(storageKey));
      if (value && typeof value.allowed === 'boolean' && value.expires > Date.now()) return value.allowed;
    } catch (_) { /* Storage can be unavailable in private browsers. */ }
    return null;
  }
  function writeChoice(value) {
    try { localStorage.setItem(storageKey, JSON.stringify({allowed:value, expires:Date.now()+lifetime})); } catch (_) {}
  }
  function clearCookies() {
    for (const cookie of document.cookie.split(';')) {
      const name = cookie.trim().split('=')[0];
      if (!/^_ga(?:_|$)/.test(name)) continue;
      for (const domain of ['', '; domain='+location.hostname, '; domain=.'+location.hostname]) {
        document.cookie = name+'=; Max-Age=0; path=/'+domain+'; SameSite=Lax';
      }
    }
  }
  function loadAnalytics() {
    // Local previews never contribute to live statistics.
    if (loaded || !allowed || location.hostname !== script.dataset.siteHost) return;
    loaded = true;
    window['ga-disable-'+id] = false;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function() { window.dataLayer.push(arguments); };
    window.gtag('consent','default',{...denyAds,analytics_storage:'denied'});
    window.gtag('consent','update',{...denyAds,analytics_storage:'granted'});
    window.gtag('js',new Date());
    let referrer = '';
    try { referrer = document.referrer ? new URL(document.referrer).origin : ''; } catch (_) {}
    window.gtag('config',id,{
      allow_google_signals:false, allow_ad_personalization_signals:false,
      cookie_expires:15552000, cookie_update:false,
      page_location:cleanLocation.href, page_referrer:referrer,
      ...context
    });
    const tag = document.createElement('script');
    tag.async = true;
    tag.src = 'https://www.googletagmanager.com/gtag/js?id='+encodeURIComponent(id);
    document.head.appendChild(tag);
  }
  function closeBanner() {
    if (banner) banner.hidden = true;
    previousFocus?.focus();
  }
  function choose(value) {
    allowed = value;
    writeChoice(value);
    closeBanner();
    if (value) loadAnalytics();
    else {
      window['ga-disable-'+id] = true;
      clearCookies();
      // Unload Google's script entirely on withdrawal; no cookieless pings.
      if (loaded) location.reload();
    }
  }
  if (settings) {
    settings.hidden = false;
    settings.addEventListener('click', () => {
      previousFocus = settings;
      banner.hidden = false;
      banner.querySelector('button')?.focus();
    });
  }
  document.querySelector('[data-analytics-accept]')?.addEventListener('click', () => choose(true));
  document.querySelector('[data-analytics-reject]')?.addEventListener('click', () => choose(false));
  window.addEventListener('storage', event => {
    if (event.key !== storageKey) return;
    allowed = readChoice() === true;
    if (!allowed) {
      window['ga-disable-'+id] = true;
      clearCookies();
      if (loaded) location.reload();
    } else loadAnalytics();
  });
  document.addEventListener('click', event => {
    const link = event.target.closest?.('a[data-amazon-cta]');
    if (!link || !allowed || !loaded) return;
    const target = new URL(link.href, location.href);
    if (target.hostname !== 'www.amazon.de' || !/^\/dp\/[A-Z0-9]{10}/.test(target.pathname)) return;
    window.gtag('event','amazon_click',{
      ...context,
      cta_position:link.closest('.mobile-buy-bar') ? 'mobile_bar' :
        link.closest('.conversion-card') ? 'hero' : link.closest('.book-offer') ? 'book_offer' : 'closing',
      link_url:target.origin+target.pathname,
      transport_type:'beacon'
    });
  });
  const saved = readChoice();
  if (saved === true) { allowed = true; loadAnalytics(); }
  else if (saved === false) { window['ga-disable-'+id] = true; clearCookies(); }
  else if (banner) banner.hidden = false;
})();
