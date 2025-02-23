// Check if the user is logged in
function isLoggedIn() {
    const userId = localStorage.getItem('userId');
    return !!userId; // Returns true if userId exists, false otherwise
  }
  
  // Redirect to the profile page if not logged in
  function redirectToProfileIfNotLoggedIn() {
    if (!isLoggedIn()) {
      window.location.href = 'profile';
    }
  }
  
  // Save user details after login
  function saveUserDetails(userId) {
    localStorage.setItem('userId', userId);
  }