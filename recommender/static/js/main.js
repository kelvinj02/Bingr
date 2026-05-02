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

  // ── Open Library cover fallback (global) ─────────────────────────────
  // Handles any img with a class containing "ol-cover" on every page.
  // If the image loads as a 1px placeholder or fails, show the initials div.
  document.querySelectorAll('img[class*="ol-cover"]').forEach(img => {
    img.addEventListener('load', function () {
      if (this.naturalWidth < 10) {
        this.style.display = 'none';
        if (this.nextElementSibling) this.nextElementSibling.style.display = 'flex';
      }
    });
    img.addEventListener('error', function () {
      this.style.display = 'none';
      if (this.nextElementSibling) this.nextElementSibling.style.display = 'flex';
    });
  });
});
