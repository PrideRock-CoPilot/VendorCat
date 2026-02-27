// Toggle sidebar and persist state
function toggleSidebar() {
  const isCollapsed = document.body.classList.toggle('sidebar-collapsed');
  localStorage.setItem('sidebarCollapsed', isCollapsed);
}

// No initialization needed - state is applied inline in HTML for performance
