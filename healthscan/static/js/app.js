// App Controller for Settings updates and Saved Products toggles
document.addEventListener('DOMContentLoaded', () => {
  const profileSettingsForm = document.getElementById('profile-settings-form');
  const btnSaveToggle = document.getElementById('btn-save-toggle');
  
  // 1. Handle Profile Settings Save
  if (profileSettingsForm) {
    profileSettingsForm.addEventListener('submit', (e) => {
      e.preventDefault();
      
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
      const healthGoal = document.getElementById('health-goal-select').value;
      const preferredLanguage = document.getElementById('preferred-language-select').value;
      const alertDiv = document.getElementById('settings-alert');

      fetch('/api/profile/', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          health_goal: healthGoal,
          preferred_language: preferredLanguage
        })
      })
      .then(response => {
        if (!response.ok) throw new Error("Failed to update settings");
        return response.json();
      })
      .then(data => {
        // Show success alert
        alertDiv.style.display = 'block';
        
        // Instantly translate static UI strings on page
        if (typeof translatePage === 'function') {
          translatePage(preferredLanguage);
        }
        
        // Reload after 1 second to apply changes on server side (session updates)
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      })
      .catch(err => {
        console.error(err);
        alert("Error saving settings.");
      });
    });
  }

  // Handle Log Purchase on Results Page
  const btnLogPurchase = document.getElementById('btn-log-purchase');
  if (btnLogPurchase) {
    btnLogPurchase.addEventListener('click', () => {
      const barcode = btnLogPurchase.getAttribute('data-barcode');
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                        getCookie('csrftoken');
      
      btnLogPurchase.disabled = true;
      btnLogPurchase.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Logging...`;
      
      fetch('/api/history/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          barcode: barcode
        })
      })
      .then(response => {
        if (!response.ok) throw new Error("Failed to log purchase");
        return response.json();
      })
      .then(data => {
        // Hide prompt and show success card
        document.getElementById('purchase-prompt-card').style.display = 'none';
        document.getElementById('purchase-logged-card').style.display = 'block';
      })
      .catch(err => {
        console.error(err);
        alert("Error logging purchase.");
        btnLogPurchase.disabled = false;
        btnLogPurchase.innerHTML = `<i class="fa-solid fa-check me-1"></i> Yes, I bought it`;
      });
    });
  }

  // 2. Handle Save/Unsave Product on Results Page
  if (btnSaveToggle) {
    btnSaveToggle.addEventListener('click', () => {
      const barcode = btnSaveToggle.getAttribute('data-barcode');
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                        getCookie('csrftoken');
      
      // Determine if currently saved
      const isSaved = btnSaveToggle.classList.contains('btn-warning');
      
      if (isSaved) {
        // Perform Delete/Unsave
        fetch(`/api/saved/${barcode}/`, {
          method: 'DELETE',
          headers: {
            'X-CSRFToken': csrfToken
          }
        })
        .then(response => {
          if (!response.ok) throw new Error("Failed to unsave");
          return response.json();
        })
        .then(data => {
          // Update button styles
          btnSaveToggle.classList.remove('btn-warning', 'text-white');
          btnSaveToggle.classList.add('btn-outline-warning');
          btnSaveToggle.innerHTML = `<i class="fa-regular fa-star me-1"></i> <span id="save-btn-text">Save Product</span>`;
          if (typeof translatePage === 'function') translatePage(PREFERRED_LANGUAGE);
        })
        .catch(err => {
          console.error(err);
          alert("Error unsaving product.");
        });
      } else {
        // Read metadata from DOM to post
        const productName = document.querySelector('h3.fw-bold')?.textContent.trim() || 'Unknown Product';
        const brand = document.querySelector('p.text-secondary')?.textContent.trim() || 'Unknown Brand';
        const imageUrl = document.querySelector('.mb-4 img')?.src || '';
        const healthScore = parseFloat(document.querySelector('.score-number')?.textContent.trim() || '0');
        const riskLevel = document.querySelector('.rounded-pill')?.textContent.trim().toUpperCase() || 'MODERATE';

        // Perform Save
        fetch('/api/saved/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({
            barcode: barcode,
            product_name: productName,
            brand: brand,
            image_url: imageUrl,
            health_score: healthScore,
            risk_level: riskLevel
          })
        })
        .then(response => {
          if (!response.ok) throw new Error("Failed to save");
          return response.json();
        })
        .then(data => {
          // Update button styles
          btnSaveToggle.classList.remove('btn-outline-warning');
          btnSaveToggle.classList.add('btn-warning', 'text-white');
          btnSaveToggle.innerHTML = `<i class="fa-solid fa-star me-1"></i> <span id="save-btn-text">Saved</span>`;
          if (typeof translatePage === 'function') translatePage(PREFERRED_LANGUAGE);
        })
        .catch(err => {
          console.error(err);
          alert("Error saving product.");
        });
      }
    });
  }

  // 3. Handle Saved Product Deletion on History Page
  document.querySelectorAll('.btn-delete-saved').forEach(button => {
    button.addEventListener('click', (e) => {
      e.preventDefault();
      const barcode = button.getAttribute('data-barcode');
      const csrfToken = getCookie('csrftoken');

      fetch(`/api/saved/${barcode}/`, {
        method: 'DELETE',
        headers: {
          'X-CSRFToken': csrfToken
        }
      })
      .then(response => {
        if (!response.ok) throw new Error("Failed to delete");
        // Remove card element from DOM
        const card = document.getElementById(`saved-card-${barcode}`);
        if (card) {
          card.remove();
        }
        // If container empty, show placeholder
        const container = document.getElementById('saved-list-container');
        if (container && container.children.length === 0) {
          container.innerHTML = `
            <div class="col-12 text-center py-5">
              <i class="fa-regular fa-star text-muted mb-3" style="font-size: 3rem;"></i>
              <h5 class="fw-bold" data-translate="no_saved">No saved products. Click the star icon on results to save items.</h5>
            </div>
          `;
          if (typeof translatePage === 'function') translatePage(PREFERRED_LANGUAGE);
        }
      })
      .catch(err => {
        console.error(err);
        alert("Error deleting saved item.");
      });
    });
  });

  // Helper: Get Cookie by Name (CSRF Token fallback)
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
});
