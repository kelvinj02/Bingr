// Save / Watched interact buttons for movie lists
// Used by: movie_recommendations.html, movie_search_result.html
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.interact-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        const res  = await fetch('/movies/interact', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: btn.dataset.title, action: btn.dataset.action })
        });
        const data = await res.json();
        if (!data.ok) return;
        if (data.status === 'saved')   btn.textContent = 'Saved ✓';
        else if (data.status === 'removed')  btn.textContent = '+ Save';
        else if (data.status === 'watched')  btn.textContent = '✓ Watched';
      } catch (e) { console.error('Interact error:', e); }
    });
  });
});
