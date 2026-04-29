// ── giffgaff shake animation ──────────────────────────────────────────────
function ggShake(btn) {
  btn.classList.remove('btn--shake');
  void btn.offsetWidth; // force reflow so animation restarts
  btn.classList.add('btn--shake');
  setTimeout(() => btn.classList.remove('btn--shake'), 600);
}

document.addEventListener('click', e => {
  const btn = e.target.closest('.btn, .btn-save, .btn-read');
  if (btn) ggShake(btn);
});

document.addEventListener('focusin', e => {
  const btn = e.target.closest('.btn, .btn-save, .btn-read');
  if (btn) ggShake(btn);
});

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
})
