// Filter pills — update hidden type input and re-submit the search form
// Used by: search_result.html
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const typeInput = document.getElementById('filter-type-input');
      if (typeInput) typeInput.value = pill.dataset.value;
      pill.closest('form').submit();
    });
  });
});
