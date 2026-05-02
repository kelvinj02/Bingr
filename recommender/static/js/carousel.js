// scrollCarousel — wraps around at both ends
// Used by: index.html, book_details.html, movie_details.html
function scrollCarousel(id, direction) {
  const carousel = document.getElementById('carousel-' + id);
  if (!carousel) return;
  const atStart = carousel.scrollLeft <= 0;
  const atEnd   = carousel.scrollLeft + carousel.clientWidth >= carousel.scrollWidth - 1;

  if (direction === -1 && atStart) {
    carousel.scrollTo({ left: carousel.scrollWidth, behavior: 'smooth' });
  } else if (direction === 1 && atEnd) {
    carousel.scrollTo({ left: 0, behavior: 'smooth' });
  } else {
    carousel.scrollBy({ left: direction * 340, behavior: 'smooth' });
  }
}
