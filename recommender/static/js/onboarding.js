// Genre pill selection toggle on the onboarding page
// Used by: onboarding.html
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.genre-pill-label').forEach(label => {
    label.addEventListener('click', () => label.classList.toggle('selected'));
  });
});
