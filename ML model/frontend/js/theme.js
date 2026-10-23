/**
 * LifeLink Theme Manager: Dark HUD vs Red & White Light Theme
 * Persists theme preference across Driver HUD, Admin Studio, Login, and Gateway.
 */

function getSavedTheme() {
  return localStorage.getItem('lifelink_theme') || 'dark';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  if (document.body) {
    document.body.setAttribute('data-theme', theme);
  }
  localStorage.setItem('lifelink_theme', theme);

  const iconEls = document.querySelectorAll('.theme-toggle-icon');
  const textEls = document.querySelectorAll('.theme-toggle-text');

  iconEls.forEach(el => {
    el.innerText = theme === 'light' ? '🌙' : '☀️';
  });

  textEls.forEach(el => {
    el.innerText = theme === 'light' ? 'Dark HUD' : 'Red & White';
  });

  // Update Chart.js themes if present on Admin page
  if (typeof updateChartsTheme === 'function') {
    updateChartsTheme(theme);
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || getSavedTheme();
  const newTheme = current === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
}

// Immediate execution to prevent flash of wrong theme
(function() {
  const saved = getSavedTheme();
  document.documentElement.setAttribute('data-theme', saved);
  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(saved);
  });
})();
