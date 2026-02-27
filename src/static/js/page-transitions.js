/**
 * Smooth page transitions and scroll management
 * Prevents header and sidebar from appearing to jump during navigation
 */

// Preserve scroll position of main content during navigation
window.addEventListener('beforeunload', () => {
  const main = document.querySelector('main');
  if (main) {
    sessionStorage.setItem('mainScrollPosition', main.scrollTop);
  }
});

// Restore scroll position after navigation
window.addEventListener('DOMContentLoaded', () => {
  const main = document.querySelector('main');
  const savedScroll = sessionStorage.getItem('mainScrollPosition');
  if (main && savedScroll) {
    // Only restore if we navigated to a different page
    main.scrollTop = parseInt(savedScroll, 10);
    sessionStorage.removeItem('mainScrollPosition');
  }
});

// Ensure sidebar active states update immediately on page load
window.addEventListener('DOMContentLoaded', () => {
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll('.sidebar-nav-item');
  
  navLinks.forEach(link => {
    const href = link.getAttribute('href');
    // Update active class based on current path
    if (href === currentPath || 
        (href !== '/' && currentPath.startsWith(href))) {
      link.classList.add('active');
    } else if (link.classList.contains('active') && 
               href !== currentPath && 
               !currentPath.startsWith(href)) {
      link.classList.remove('active');
    }
  });
});

