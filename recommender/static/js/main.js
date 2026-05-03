// ── theme toggle ─────────────────────────────────────────────────────────
const THEME_KEY = 'reel-reads-theme';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);
  const btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem(THEME_KEY);
  const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  applyTheme(saved || preferred);

  const btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      applyTheme(current === 'dark' ? 'light' : 'dark');
    });
  }

  // ── Cover image fallback (global) ────────────────────────────────────
  // Covers ol-cover fallback images AND direct thumbnail imgs in cover containers.
  // Hides 1px OL placeholders (naturalWidth < 10) and broken images, then shows
  // the initials sibling div. Also checks img.complete for browser-cached images
  // that have already loaded before this listener was attached.
  const hidePlaceholder = function () {
    if (this.naturalWidth < 10) {
      this.style.display = 'none';
      if (this.nextElementSibling) this.nextElementSibling.style.display = 'flex';
    }
  };
  const hideBroken = function () {
    this.style.display = 'none';
    if (this.nextElementSibling) this.nextElementSibling.style.display = 'flex';
  };
  document.querySelectorAll(
    'img[class*="ol-cover"], .browse-cover img, .book-cover img, .wishlist-cover img, .detail-poster img, .similar-cover img'
  ).forEach(img => {
    if (img.complete) {
      hidePlaceholder.call(img);
    } else {
      img.addEventListener('load', hidePlaceholder);
    }
    img.addEventListener('error', hideBroken);
  });
});
