// ==================================================================
// RESTRICTED APPS MANAGEMENT JAVASCRIPT
// ==================================================================
// Replace the blocked apps functions in dashboard_scripts.html with these

// Load restricted apps for a child
function loadRestrictedApps(childHash) {
  const restrictedAppsList = document.getElementById('restrictedAppsList' + childHash);
  const restrictedAppsCount = document.getElementById('restrictedAppsCount' + childHash);
  
  if (!restrictedAppsList) return;
  
  fetch('/api/blocked-apps/' + childHash + '/')
    .then(response => response.json())
    .then(data => {
      if (data.status === 'success') {
        const restrictedApps = data.restricted_apps || {};
        const appDomains = Object.keys(restrictedApps);
        
        // Update count
        if (restrictedAppsCount) {
          restrictedAppsCount.textContent = appDomains.length;
        }
        
        // Render restricted apps list
        if (appDomains.length === 0) {
          restrictedAppsList.innerHTML = `
            <div class="text-center py-8">
              <svg class="w-12 h-12 mx-auto text-textsec/30 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
              <p class="text-textsec text-sm">No restricted apps yet</p>
              <p class="text-textsec/60 text-xs mt-1">Add time limits for apps on the child's device</p>
            </div>
          `;
        } else {
          // Fetch app details for all restricted apps
          fetchAppDetailsForRestricted(childHash, restrictedApps);
        }
        
        // Update quick restrict buttons visibility
        updateQuickRestrictButtons(childHash, appDomains);
      }
    })
    .catch(error => {
      console.error('Error loading restricted apps:', error);
      restrictedAppsList.innerHTML = `
        <div class="text-center py-8">
          <svg class="w-12 h-12 mx-auto text-red-500/50 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          <p class="text-red-400 text-sm">Failed to load restricted apps</p>
        </div>
      `;
    });
}

// Fetch app details for restricted apps from search API
async function fetchAppDetailsForRestricted(childHash, restrictedApps) {
  const restrictedAppsList = document.getElementById('restrictedAppsList' + childHash);
  if (!restrictedAppsList) return;
  
  // Show loading state
  restrictedAppsList.innerHTML = `
    <div class="text-center py-8">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-2"></div>
      <p class="text-textsec text-sm">Loading app details...</p>
    </div>
  `;
  
  try {
    // Fetch details for each app
    const appDetailsPromises = Object.entries(restrictedApps).map(async ([packageName, hours]) => {
      try {
        const response = await fetch(`/api/apps/search/?q=${encodeURIComponent(packageName)}`);
        const data = await response.json();
        
        if (data.status === 'success' && data.apps && data.apps.length > 0) {
          // Find exact match
          const exactMatch = data.apps.find(app => app.domain === packageName);
          if (exactMatch) {
            return {
              package_name: packageName,
              app_name: exactMatch.name,
              icon_url: exactMatch.icon,
              hours: hours
            };
          }
        }
        
        // Fallback if not found
        return {
          package_name: packageName,
          app_name: packageName.split('.').pop().charAt(0).toUpperCase() + packageName.split('.').pop().slice(1),
          icon_url: null,
          hours: hours
        };
      } catch (error) {
        console.error(`Error fetching details for ${packageName}:`, error);
        return {
          package_name: packageName,
          app_name: packageName.split('.').pop().charAt(0).toUpperCase() + packageName.split('.').pop().slice(1),
          icon_url: null,
          hours: hours
        };
      }
    });
    
    const restrictedAppsDetails = await Promise.all(appDetailsPromises);
    
    // Render the restricted apps list with fetched details
    renderRestrictedAppsList(childHash, restrictedAppsDetails);
  } catch (error) {
    console.error('Error fetching app details:', error);
    // Fallback to simple list
    const fallbackDetails = Object.entries(restrictedApps).map(([packageName, hours]) => ({
      package_name: packageName,
      app_name: packageName.split('.').pop().charAt(0).toUpperCase() + packageName.split('.').pop().slice(1),
      icon_url: null,
      hours: hours
    }));
    renderRestrictedAppsList(childHash, fallbackDetails);
  }
}

// Render restricted apps list with details
function renderRestrictedAppsList(childHash, restrictedAppsDetails) {
  const restrictedAppsList = document.getElementById('restrictedAppsList' + childHash);
  if (!restrictedAppsList) return;
  
  let appsHTML = '';
  restrictedAppsDetails.forEach((appDetail, index) => {
    const packageName = appDetail.package_name;
    const appName = appDetail.app_name;
    const iconUrl = appDetail.icon_url;
    const hours = appDetail.hours;
    
    // Format hours display
    const hoursDisplay = hours === 0 ? 'Blocked' : `${hours}h/day`;
    const hoursColor = hours === 0 ? 'text-red-400' : 'text-amber-400';
    
    const colors = [
      'bg-amber-500/20 border-amber-500/40',
      'bg-orange-500/20 border-orange-500/40',
      'bg-yellow-500/20 border-yellow-500/40',
      'bg-lime-500/20 border-lime-500/40',
    ];
    const colorClass = colors[index % colors.length];
    
    // Create icon element
    let iconElement = '';
    if (iconUrl) {
      iconElement = `
        <div class="w-10 h-10 flex-shrink-0 mr-3 bg-darkbg2 rounded-lg overflow-hidden flex items-center justify-center">
          <img src="${iconUrl}" alt="${appName}" class="w-full h-full object-cover" onerror="this.parentElement.innerHTML='<span class=\\'text-primary text-lg font-bold\\'>${appName.charAt(0)}</span>'">
        </div>
      `;
    } else {
      iconElement = `
        <div class="w-10 h-10 flex-shrink-0 mr-3 bg-darkbg2 rounded-lg overflow-hidden flex items-center justify-center">
          <span class="text-primary text-lg font-bold">${appName.charAt(0)}</span>
        </div>
      `;
    }
    
    appsHTML += `
      <div class="flex items-center justify-between p-4 ${colorClass} border rounded-xl hover:bg-opacity-30 transition-all group">
        <div class="flex items-center flex-1 min-w-0">
          ${iconElement}
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <h4 class="font-semibold text-textmain text-sm">${appName}</h4>
              <span class="text-xs ${hoursColor} font-bold px-2 py-0.5 bg-black/30 rounded">${hoursDisplay}</span>
            </div>
            <p class="text-xs text-textsec/80 font-mono truncate">${packageName}</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <input 
            type="number"
            id="editHours_${packageName.replace(/\./g, '_')}_${childHash}"
            value="${hours}"
            min="0"
            step="0.5"
            class="w-20 px-2 py-1 text-sm bg-darkbg1 border border-textsec/20 rounded text-textmain opacity-0 group-hover:opacity-100 transition-opacity"
            onchange="updateAppHours('${childHash}', '${packageName}', this.value)"
          />
          <button 
            onclick="removeRestrictedApp('${childHash}', '${packageName}')"
            class="px-3 py-2 bg-red-500/20 hover:bg-red-500 border border-red-500/40 hover:border-red-500 text-red-400 hover:text-white rounded-lg transition-all duration-200 flex items-center gap-2 text-xs font-semibold opacity-0 group-hover:opacity-100"
            title="Remove restriction"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
            Remove
          </button>
        </div>
      </div>
    `;
  });
  
  restrictedAppsList.innerHTML = appsHTML;
}

// Update quick restrict buttons visibility based on restricted apps
function updateQuickRestrictButtons(childHash, restrictedDomains) {
  const quickAddContainer = document.getElementById('quickAddButtons' + childHash);
  if (!quickAddContainer) return;
  
  const buttons = quickAddContainer.querySelectorAll('.quick-restrict-btn');
  buttons.forEach(button => {
    const packageName = button.getAttribute('data-package');
    if (restrictedDomains.includes(packageName)) {
      button.classList.add('hidden-restricted');
    } else {
      button.classList.remove('hidden-restricted');
    }
  });
}

// Add a restricted app
function addRestrictedApp(childHash) {
  const input = document.getElementById('newRestrictedApp' + childHash);
  const hoursInput = document.getElementById('newAppHours' + childHash);
  const packageName = input.value.trim();
  const hours = parseFloat(hoursInput.value);
  
  if (!packageName) {
    showToast('Please enter an app package name', 'error');
    return;
  }
  
  // Basic validation for package name format
  if (!packageName.includes('.')) {
    showToast('Please enter a valid package name (e.g., com.example.app)', 'error');
    return;
  }
  
  if (isNaN(hours) || hours < 0) {
    showToast('Please enter a valid number of hours (0 or greater)', 'error');
    return;
  }
  
  // Get current restricted apps
  fetch('/api/blocked-apps/' + childHash + '/')
    .then(response => response.json())
    .then(data => {
      const restrictedApps = data.restricted_apps || {};
      
      // Check if already restricted
      if (packageName in restrictedApps) {
        showToast('This app is already restricted. Edit its time limit instead.', 'info');
        return;
      }
      
      // Add to object
      restrictedApps[packageName] = hours;
      
      // Update on server
      return updateRestrictedAppsOnServer(childHash, restrictedApps);
    })
    .then(success => {
      if (success) {
        input.value = ''; // Clear input
        hoursInput.value = '2'; // Reset to default
        loadRestrictedApps(childHash); // Reload list
        showToast('App restriction added successfully', 'success');
      }
    })
    .catch(error => {
      console.error('Error adding restricted app:', error);
      showToast('Failed to add restriction. Please try again.', 'error');
    });
}

// Quick restrict an app
function quickRestrictApp(childHash, packageName, appName, defaultHours) {
  fetch('/api/blocked-apps/' + childHash + '/')
    .then(response => response.json())
    .then(data => {
      const restrictedApps = data.restricted_apps || {};
      
      // Check if already restricted
      if (packageName in restrictedApps) {
        showToast(appName + ' is already restricted', 'info');
        return;
      }
      
      // Add to object
      restrictedApps[packageName] = defaultHours;
      
      // Update on server
      return updateRestrictedAppsOnServer(childHash, restrictedApps);
    })
    .then(success => {
      if (success) {
        loadRestrictedApps(childHash);
        showToast(appName + ` restricted to ${defaultHours}h/day`, 'success');
      }
    })
    .catch(error => {
      console.error('Error restricting app:', error);
      showToast('Failed to restrict ' + appName, 'error');
    });
}

// Update hours for an existing app
function updateAppHours(childHash, packageName, newHours) {
  const hours = parseFloat(newHours);
  
  if (isNaN(hours) || hours < 0) {
    showToast('Please enter a valid number of hours', 'error');
    return;
  }
  
  fetch('/api/blocked-apps/' + childHash + '/')
    .then(response => response.json())
    .then(data => {
      const restrictedApps = data.restricted_apps || {};
      
      // Update hours
      restrictedApps[packageName] = hours;
      
      // Update on server
      return updateRestrictedAppsOnServer(childHash, restrictedApps);
    })
    .then(success => {
      if (success) {
        loadRestrictedApps(childHash);
        showToast('Time limit updated successfully', 'success');
      }
    })
    .catch(error => {
      console.error('Error updating app hours:', error);
      showToast('Failed to update time limit', 'error');
    });
}

// Remove a restricted app
function removeRestrictedApp(childHash, packageName) {
  if (!confirm('Are you sure you want to remove this restriction?')) {
    return;
  }
  
  fetch('/api/blocked-apps/' + childHash + '/')
    .then(response => response.json())
    .then(data => {
      const restrictedApps = data.restricted_apps || {};
      
      // Remove from object
      delete restrictedApps[packageName];
      
      // Update on server
      return updateRestrictedAppsOnServer(childHash, restrictedApps);
    })
    .then(success => {
      if (success) {
        loadRestrictedApps(childHash);
        showToast('Restriction removed successfully', 'success');
      }
    })
    .catch(error => {
      console.error('Error removing restricted app:', error);
      showToast('Failed to remove restriction. Please try again.', 'error');
    });
}

// Update restricted apps on server
function updateRestrictedAppsOnServer(childHash, restrictedApps) {
  return fetch('/api/blocked-apps/' + childHash + '/update/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({
      restricted_apps: restrictedApps
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.status === 'success') {
      return true;
    } else {
      console.error('Server returned error:', data);
      showToast(data.error || 'Failed to update restrictions', 'error');
      return false;
    }
  })
  .catch(error => {
    console.error('Error updating restricted apps on server:', error);
    showToast('Failed to communicate with server', 'error');
    return false;
  });
}

// Initialize - load restricted apps when page loads
document.addEventListener('DOMContentLoaded', function() {
  // Find all child hashes on the page and load their restricted apps
  const restrictedAppsLists = document.querySelectorAll('[id^="restrictedAppsList"]');
  restrictedAppsLists.forEach(list => {
    const childHash = list.id.replace('restrictedAppsList', '');
    if (childHash) {
      loadRestrictedApps(childHash);
    }
  });
});
