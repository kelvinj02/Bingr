// Wishlist toggle + star rating for detail pages
// Used by: book_details.html, movie_details.html
//
// Requires on the #wishlist-btn element:
//   data-item-type="book"  or  "movie"
//   data-title="..."
//   data-movie-id="..."    (movie only)
document.addEventListener('DOMContentLoaded', () => {

  // ── wishlist toggle ─────────────────────────────────────────────────
  const wishlistBtn = document.getElementById('wishlist-btn');
  if (wishlistBtn) {
    wishlistBtn.addEventListener('click', async () => {
      try {
        const itemType = wishlistBtn.dataset.itemType;
        const url      = itemType === 'movie' ? '/movies/wishlist' : '/books/wishlist';
        const payload  = itemType === 'movie'
          ? { movie_id: parseInt(wishlistBtn.dataset.movieId), title: wishlistBtn.dataset.title }
          : { title: wishlistBtn.dataset.title };

        const res  = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!data.ok) return;

        if (data.in_wishlist) {
          wishlistBtn.textContent = 'Saved to Wishlist ✓';
          wishlistBtn.classList.replace('btn-outline', 'btn-primary');
        } else {
          wishlistBtn.textContent = 'Save to Wishlist';
          wishlistBtn.classList.replace('btn-primary', 'btn-outline');
        }
      } catch (e) { console.error('Wishlist error:', e); }
    });
  }

  // ── star rating ─────────────────────────────────────────────────────
  const formStars  = document.querySelectorAll('.form-star');
  const scoreInput = document.getElementById('review-score-input');
  // Pre-fill stars when editing an existing review (scoreInput already has a value)
  let selectedRating = parseInt(scoreInput?.value) || 0;
  formStars.forEach((s, i) => s.classList.toggle('filled', i < selectedRating));

  formStars.forEach(star => {
    star.addEventListener('click', () => {
      selectedRating = parseInt(star.dataset.value);
      if (scoreInput) scoreInput.value = selectedRating;
      formStars.forEach((s, i) => s.classList.toggle('filled', i < selectedRating));
    });
    star.addEventListener('mouseover', () => {
      const val = parseInt(star.dataset.value);
      formStars.forEach((s, i) => s.classList.toggle('filled', i < val));
    });
    star.addEventListener('mouseout', () => {
      formStars.forEach((s, i) => s.classList.toggle('filled', i < selectedRating));
    });
  });

});
