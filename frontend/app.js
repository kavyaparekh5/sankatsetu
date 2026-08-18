/**
 * Disaster Intelligence App - Client JavaScript
 */

// Detect API base URL: use current origin if served via HTTP, fallback to localhost:8000
const API_BASE_URL = window.location.protocol.startsWith('http') 
  ? window.location.origin 
  : 'http://127.0.0.1:8000';

// Application State
const state = {
  reports: [],
  resources: [],
  selectedReportId: null,
  filters: {
    category: '',
    minScore: 0
  },
  currentUser: null,     // { username, role, token }
  currentView: 'citizen', // 'citizen' | 'authority'
  activeServiceTab: 'hospital', // 'hospital' | 'police' | 'fire'
  userLocation: { lat: 22.9962, lng: 72.6081 }, // Default to Maninagar
  audioContext: null,
  sirenOscillator: null,
  sirenInterval: null
};

// Global variables for Leaflet maps
let citizenMap = null;
let authorityMap = null;
let citizenReportsLayer = null;
let authorityReportsLayer = null;
let citizenResourcesLayer = null;
let authorityResourcesLayer = null;

// Map category strings to HTML icons for markers/tags
const CATEGORY_ICONS = {
  flood: '<i data-lucide="droplet"></i>',
  fire: '<i data-lucide="flame"></i>',
  medical: '<i data-lucide="activity"></i>',
  rescue: '<i data-lucide="life-buoy"></i>',
  infrastructure: '<i data-lucide="wrench"></i>',
  uncategorized: '<i data-lucide="help-circle"></i>'
};

const RESOURCE_ICONS = {
  ambulance: 'ambulance',
  ndrf_team: 'users',
  shelter: 'home',
  fire_unit: 'flame',
  hospital: 'building-2',
  police_station: 'shield'
};

// ==============================================================================
// INITIALIZATION
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initPortals();
  initMaps();
  initEventListeners();
  initSurvivalChecklist();
  initSirenSettings();
  initTooltipModal();
  loadData();
  restoreSession();
});

// Theme Handling
function initTheme() {
  const themeToggle = document.getElementById('theme-toggle');
  const savedTheme = localStorage.getItem('theme') || 'dark';
  
  if (savedTheme === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
  
  themeToggle.addEventListener('click', () => {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
  });
}

let citizenTempMarker = null;
let authorityTempMarker = null;

// Set up double Leaflet map containers (one for each portal view)
function initMaps() {
  // 1. Citizen View Map
  citizenMap = L.map('citizen-map', {
    center: [state.userLocation.lat, state.userLocation.lng],
    zoom: 13
  });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(citizenMap);
  citizenReportsLayer = L.layerGroup().addTo(citizenMap);
  citizenResourcesLayer = L.layerGroup().addTo(citizenMap);

  // Map clicks on citizen map to autofill coordinates
  citizenMap.on('click', (e) => {
    const lat = e.latlng.lat.toFixed(4);
    const lng = e.latlng.lng.toFixed(4);
    
    const latInput = document.getElementById('cit-lat');
    const lngInput = document.getElementById('cit-lng');
    if (latInput && lngInput) {
      latInput.value = lat;
      lngInput.value = lng;
    }
    
    state.userLocation = { lat: parseFloat(lat), lng: parseFloat(lng) };
    renderNearbyServices();
    
    if (citizenTempMarker) {
      citizenMap.removeLayer(citizenTempMarker);
    }
    
    citizenTempMarker = L.marker([lat, lng], {
      icon: L.divIcon({
        className: 'custom-marker temp-marker',
        html: '<div class="marker-inner" style="background-color:#6366f1;"><i data-lucide="map-pin"></i></div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
      })
    }).addTo(citizenMap);
    
    lucide.createIcons();
    
    L.popup()
      .setLatLng([lat, lng])
      .setContent(`<strong>Location Selected:</strong><br>${lat}, ${lng}<br><span style="font-size:11px;color:#71717a;">Coordinates copied to report form!</span>`)
      .openOn(citizenMap);
  });

  // 2. Authority View Map
  authorityMap = L.map('authority-map', {
    center: [23.0225, 72.5714],
    zoom: 12
  });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(authorityMap);
  authorityReportsLayer = L.layerGroup().addTo(authorityMap);
  authorityResourcesLayer = L.layerGroup().addTo(authorityMap);

  // Map clicks on authority map to autofill coordinates
  authorityMap.on('click', (e) => {
    const lat = e.latlng.lat.toFixed(4);
    const lng = e.latlng.lng.toFixed(4);
    
    const latInput = document.getElementById('input-lat');
    const lngInput = document.getElementById('input-lng');
    if (latInput && lngInput) {
      latInput.value = lat;
      lngInput.value = lng;
    }
    
    if (authorityTempMarker) {
      authorityMap.removeLayer(authorityTempMarker);
    }
    
    authorityTempMarker = L.marker([lat, lng], {
      icon: L.divIcon({
        className: 'custom-marker temp-marker',
        html: '<div class="marker-inner" style="background-color:#6366f1;"><i data-lucide="map-pin"></i></div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
      })
    }).addTo(authorityMap);
    
    lucide.createIcons();
    
    L.popup()
      .setLatLng([lat, lng])
      .setContent(`<strong>Incident Location Picker:</strong><br>${lat}, ${lng}<br><span style="font-size:11px;color:#71717a;">Coordinates copied to form!</span>`)
      .openOn(authorityMap);
  });
}

function switchView(viewName) {
  const views = ['home', 'sos', 'services', 'safety', 'authority'];
  const tabs = {
    home: 'tab-home',
    sos: 'tab-sos',
    services: 'tab-services',
    safety: 'tab-safety',
    authority: 'tab-authority-portal'
  };

  views.forEach(v => {
    const tabEl = document.getElementById(tabs[v]);
    const viewEl = document.getElementById(`${v}-view`);
    if (!tabEl || !viewEl) return;

    if (v === viewName) {
      tabEl.classList.add('active');
      viewEl.classList.remove('hidden');
    } else {
      tabEl.classList.remove('active');
      viewEl.classList.add('hidden');
    }
  });

  state.currentView = viewName;

  if (viewName === 'authority') {
    renderAuthorityView();
    setTimeout(() => {
      authorityMap.invalidateSize();
    }, 100);
  } else if (viewName === 'services') {
    renderNearbyServices();
    setTimeout(() => {
      citizenMap.invalidateSize();
    }, 100);
  } else if (viewName === 'safety') {
    renderSurvivalChecklist();
  }
}

window.navigateTo = switchView; // Expose globally

function initPortals() {
  const views = ['home', 'sos', 'services', 'safety', 'authority'];
  const tabs = {
    home: 'tab-home',
    sos: 'tab-sos',
    services: 'tab-services',
    safety: 'tab-safety',
    authority: 'tab-authority-portal'
  };

  views.forEach(v => {
    const tabEl = document.getElementById(tabs[v]);
    if (tabEl) {
      tabEl.addEventListener('click', () => {
        switchView(v);
      });
    }
  });

  // Bind hero actions
  const heroSos = document.getElementById('btn-hero-sos');
  if (heroSos) {
    heroSos.addEventListener('click', () => switchView('sos'));
  }
  const heroServices = document.getElementById('btn-hero-services');
  if (heroServices) {
    heroServices.addEventListener('click', () => switchView('services'));
  }
}

function initEventListeners() {
  // Forms expand/collapse buttons
  setupCollapsible('citizen-report-header', 'citizen-report-form', '#toggle-citizen-form i');
  setupCollapsible('auth-report-header', 'auth-report-form', '#toggle-auth-form i');

  // Submit forms
  const citForm = document.getElementById('citizen-report-form');
  if (citForm) citForm.addEventListener('submit', (e) => handleFormSubmit(e, 'citizen'));
  const authForm = document.getElementById('auth-report-form');
  if (authForm) authForm.addEventListener('submit', (e) => handleFormSubmit(e, 'authority'));

  // Autofill coordinates buttons
  const citAutofill = document.getElementById('btn-cit-autofill');
  if (citAutofill) citAutofill.addEventListener('click', () => autofillCoordinates('cit-lat', 'cit-lng', 'btn-cit-autofill'));
  const authAutofill = document.getElementById('btn-auth-autofill');
  if (authAutofill) authAutofill.addEventListener('click', () => autofillCoordinates('input-lat', 'input-lng', 'btn-auth-autofill'));

  // Details actions & close
  const closeDetails = document.getElementById('close-details-btn');
  if (closeDetails) closeDetails.addEventListener('click', deselectReport);
  const verifyIncident = document.getElementById('btn-verify-incident');
  if (verifyIncident) verifyIncident.addEventListener('click', handleVerifyIncident);

  // Authority Auth Forms toggles
  const loginTab = document.getElementById('toggle-login-tab');
  if (loginTab) loginTab.addEventListener('click', () => toggleAuthFormTab('login'));
  const signupTab = document.getElementById('toggle-signup-tab');
  if (signupTab) signupTab.addEventListener('click', () => toggleAuthFormTab('signup'));

  // Auth Form submissions
  const loginForm = document.getElementById('auth-login-form');
  if (loginForm) loginForm.addEventListener('submit', handleLogin);
  const signupForm = document.getElementById('auth-signup-form');
  if (signupForm) signupForm.addEventListener('submit', handleSignup);
  const logoutBtn = document.getElementById('btn-logout');
  if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);

  // Category and Score filters
  const filterCat = document.getElementById('filter-category');
  if (filterCat) {
    filterCat.addEventListener('change', (e) => {
      state.filters.category = e.target.value;
      renderReports();
      renderMapMarkers();
    });
  }
  const filterScore = document.getElementById('filter-score');
  if (filterScore) {
    filterScore.addEventListener('change', (e) => {
      state.filters.minScore = parseInt(e.target.value, 10) || 0;
      renderReports();
      renderMapMarkers();
    });
  }

  // Citizen Portal Nearby Services Toggles
  const svcHospital = document.getElementById('svc-tab-hospital');
  if (svcHospital) svcHospital.addEventListener('click', () => toggleServiceTab('hospital'));
  const svcPolice = document.getElementById('svc-tab-police');
  if (svcPolice) svcPolice.addEventListener('click', () => toggleServiceTab('police'));
  const svcFire = document.getElementById('svc-tab-fire');
  if (svcFire) svcFire.addEventListener('click', () => toggleServiceTab('fire'));

  // "Iron Bell" SOS distress Panic click triggers
  const ironBellBtn = document.getElementById('btn-iron-bell');
  if (ironBellBtn) ironBellBtn.addEventListener('click', triggerIronBellSOS);
  const cancelSosBtn = document.getElementById('btn-cancel-sos');
  if (cancelSosBtn) cancelSosBtn.addEventListener('click', stopIronBellSOS);
}

function setupCollapsible(headerId, bodyId, iconSelector) {
  const header = document.getElementById(headerId);
  const body = document.getElementById(bodyId);
  const icon = document.querySelector(iconSelector);

  header.addEventListener('click', () => {
    const isHidden = body.classList.toggle('hidden');
    if (icon) {
      icon.setAttribute('data-lucide', isHidden ? 'chevron-down' : 'chevron-up');
      lucide.createIcons();
    }
  });
}

// ==============================================================================
// SESSION & SYSTEM RESTORATION
// ==============================================================================

function restoreSession() {
  const savedUser = localStorage.getItem('user');
  if (savedUser) {
    try {
      state.currentUser = JSON.parse(savedUser);
      renderUserStatusHeader();
    } catch (e) {
      localStorage.removeItem('user');
    }
  }
}

// Render User Account Header Status Badge
function renderUserStatusHeader() {
  const badge = document.getElementById('user-status');
  const nameSpan = document.getElementById('user-display-name');
  
  if (state.currentUser) {
    nameSpan.innerText = `${state.currentUser.username} (${state.currentUser.role})`;
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

// Toggle showing the login tab vs signup tab
function toggleAuthFormTab(tab) {
  const loginBtn = document.getElementById('toggle-login-tab');
  const signupBtn = document.getElementById('toggle-signup-tab');
  const loginForm = document.getElementById('auth-login-form');
  const signupForm = document.getElementById('auth-signup-form');

  if (tab === 'login') {
    loginBtn.classList.add('active');
    signupBtn.classList.remove('active');
    loginForm.classList.remove('hidden');
    signupForm.classList.add('hidden');
  } else {
    loginBtn.classList.remove('active');
    signupBtn.classList.add('active');
    loginForm.classList.add('hidden');
    signupForm.classList.remove('hidden');
  }
}

// ==============================================================================
// AUTHENTICATION CLIENT HANDLERS
// ==============================================================================

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-login-submit');
  btn.disabled = true;

  const payload = {
    username: document.getElementById('login-username').value.trim(),
    password: document.getElementById('login-password').value
  };

  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Login failed');
    }

    const tokenData = await response.json();
    state.currentUser = {
      username: tokenData.username,
      role: tokenData.role,
      token: tokenData.access_token
    };

    localStorage.setItem('user', JSON.stringify(state.currentUser));
    
    // Reset form
    document.getElementById('auth-login-form').reset();
    
    // Render and refresh
    renderUserStatusHeader();
    renderAuthorityView();

  } catch (error) {
    alert(error.message);
  } finally {
    btn.disabled = false;
  }
}

async function handleSignup(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-signup-submit');
  btn.disabled = true;

  const payload = {
    username: document.getElementById('signup-username').value.trim(),
    password: document.getElementById('signup-password').value,
    role: document.getElementById('signup-role').value
  };

  try {
    const response = await fetch(`${API_BASE_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Sign up failed');
    }

    alert('Sign up successful! Please log in.');
    document.getElementById('auth-signup-form').reset();
    
    // Switch back to login form tab
    toggleAuthFormTab('login');

  } catch (error) {
    alert(error.message);
  } finally {
    btn.disabled = false;
  }
}

function handleLogout() {
  state.currentUser = null;
  localStorage.removeItem('user');
  renderUserStatusHeader();
  renderAuthorityView();
}

function renderAuthorityView() {
  const authCardWrapper = document.getElementById('auth-forms-container');
  const dashboardContent = document.getElementById('authority-dashboard-content');

  if (state.currentUser && state.currentUser.role === 'authority') {
    authCardWrapper.classList.add('hidden');
    dashboardContent.classList.remove('hidden');
    // Refresh stats and components
    renderKPIs();
    renderReports();
    renderMapMarkers();
  } else {
    authCardWrapper.classList.remove('hidden');
    dashboardContent.classList.add('hidden');
  }
}

// ==============================================================================
// PUBLIC CITIZEN PORTAL OPERATIONS
// ==============================================================================

function toggleServiceTab(tab) {
  state.activeServiceTab = tab;
  
  const tabs = ['svc-tab-hospital', 'svc-tab-police', 'svc-tab-fire'];
  tabs.forEach(t => {
    const el = document.getElementById(t);
    if (t.endsWith(tab)) el.classList.add('active');
    else el.classList.remove('active');
  });

  renderNearbyServices();
}

// Render nearby service help cards based on proximity (hospitals/police/fire)
function renderNearbyServices() {
  const container = document.getElementById('nearby-services-list');
  container.innerHTML = '';

  let resourceTypeFilter = '';
  let iconName = 'building';
  
  if (state.activeServiceTab === 'hospital') {
    resourceTypeFilter = 'hospital';
    iconName = 'hospital';
  } else if (state.activeServiceTab === 'police') {
    resourceTypeFilter = 'police_station';
    iconName = 'shield';
  } else {
    resourceTypeFilter = 'fire_unit';
    iconName = 'flame';
  }

  // Filter resources and calculate Haversine distance
  const candidates = state.resources.filter(r => r.type === resourceTypeFilter);
  
  const scored = candidates.map(res => {
    const dist = haversineDistance(
      state.userLocation.lat,
      state.userLocation.lng,
      res.lat,
      res.lng
    );
    return { resource: res, distance: dist };
  });

  // Sort closest first
  scored.sort((a, b) => a.distance - b.distance);

  if (scored.length === 0) {
    container.innerHTML = '<p class="loading-state">No matching services seeded in database.</p>';
    return;
  }

  scored.forEach(item => {
    const res = item.resource;
    const dist = item.distance.toFixed(2);
    
    const div = document.createElement('div');
    div.className = 'service-item';
    
    // Availability indicators
    const availText = res.is_available ? 'Available' : 'Busy';
    const availColor = res.is_available ? 'bg-emerald' : 'bg-rose';

    div.innerHTML = `
      <div class="service-left">
        <div class="service-icon-wrapper">
          <i data-lucide="${iconName}"></i>
        </div>
        <div>
          <div class="service-title">${res.name}</div>
          <div class="service-meta">
            <span class="service-avail-tag">
              <span class="avail-dot ${availColor}"></span> ${availText}
            </span>
            <span>• Emergency Contact: +91 79 2630-9111</span>
          </div>
        </div>
      </div>
      <div class="service-right">
        <span class="service-distance">${dist} km</span>
        <button class="btn-ghost btn-track-service" title="Locate on Map">
          <i data-lucide="locate-fixed"></i>
        </button>
      </div>
    `;

    // Map locate helper
    div.querySelector('.btn-track-service').addEventListener('click', () => {
      citizenMap.setView([res.lat, res.lng], 15);
      // Open resource marker popup dynamically
      L.popup()
        .setLatLng([res.lat, res.lng])
        .setContent(`<strong>${res.name}</strong><br><span style="font-size:11px;">Status: ${availText}</span>`)
        .openOn(citizenMap);
    });

    container.appendChild(div);
  });

  lucide.createIcons();
}

// Compute great-circle distance in kilometers using the Haversine formula
function haversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371; // Earth's radius in km
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = 
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

// ==============================================================================
// "IRON BELL" SOS AUDIO & BEACON SYSTEM
// ==============================================================================

let sirenVolume = 0.5;
let sirenMode = 'wobble';

function initSirenSettings() {
  const volumeSlider = document.getElementById('siren-volume');
  const volumeText = document.getElementById('volume-val');
  const sirenTypeSelect = document.getElementById('siren-type');

  if (volumeSlider) {
    volumeSlider.addEventListener('input', (e) => {
      const pct = e.target.value;
      if (volumeText) volumeText.innerText = `${pct}%`;
      sirenVolume = parseFloat(pct) / 100;
      if (state.gainNode && state.audioContext) {
        state.gainNode.gain.setValueAtTime(sirenVolume, state.audioContext.currentTime);
      }
    });
  }

  if (sirenTypeSelect) {
    sirenTypeSelect.addEventListener('change', (e) => {
      sirenMode = e.target.value;
      if (state.sirenInterval) {
        stopIronBellSOS();
        triggerIronBellSOS();
      }
    });
  }
}

async function triggerIronBellSOS() {
  const beacon = document.getElementById('sos-beacon');
  beacon.classList.remove('hidden');

  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    state.audioContext = new AudioContextClass();
    
    const osc1 = state.audioContext.createOscillator();
    const osc2 = state.audioContext.createOscillator();
    
    const gainNode = state.audioContext.createGain();
    gainNode.gain.setValueAtTime(sirenVolume, state.audioContext.currentTime);
    state.gainNode = gainNode;

    if (sirenMode === 'phaser') {
      osc1.type = 'sawtooth';
      osc2.type = 'sawtooth';
    } else if (sirenMode === 'hilo') {
      osc1.type = 'sine';
      osc2.type = 'square';
    } else {
      osc1.type = 'sawtooth';
      osc2.type = 'sine';
    }

    osc1.connect(gainNode);
    osc2.connect(gainNode);
    gainNode.connect(state.audioContext.destination);

    osc1.start();
    osc2.start();

    state.sirenOscillator = [osc1, osc2];

    let toggle = false;
    
    if (sirenMode === 'hilo') {
      state.sirenInterval = setInterval(() => {
        if (!state.audioContext) return;
        const t = state.audioContext.currentTime;
        if (toggle) {
          osc1.frequency.setValueAtTime(800, t);
          osc2.frequency.setValueAtTime(400, t);
        } else {
          osc1.frequency.setValueAtTime(500, t);
          osc2.frequency.setValueAtTime(300, t);
        }
        toggle = !toggle;
      }, 750);
    } else if (sirenMode === 'phaser') {
      state.sirenInterval = setInterval(() => {
        if (!state.audioContext) return;
        const t = state.audioContext.currentTime;
        if (toggle) {
          osc1.frequency.linearRampToValueAtTime(1800, t + 0.12);
          osc2.frequency.linearRampToValueAtTime(1400, t + 0.12);
        } else {
          osc1.frequency.setValueAtTime(200, t);
          osc2.frequency.setValueAtTime(200, t);
        }
        toggle = !toggle;
      }, 150);
    } else {
      state.sirenInterval = setInterval(() => {
        if (!state.audioContext) return;
        const t = state.audioContext.currentTime;
        if (toggle) {
          osc1.frequency.exponentialRampToValueAtTime(950, t + 0.35);
          osc2.frequency.exponentialRampToValueAtTime(700, t + 0.35);
        } else {
          osc1.frequency.exponentialRampToValueAtTime(600, t + 0.35);
          osc2.frequency.exponentialRampToValueAtTime(1100, t + 0.35);
        }
        toggle = !toggle;
      }, 400);
    }

  } catch (error) {
    console.error('AudioContext synthesis failed:', error);
  }

  const payload = {
    text: "⚠️ [IRON BELL SOS ACTIVATED] Citizen triggered distress alarm. Urgent search and rescue requested.",
    source: "citizen_app",
    location_name: "Distress Coordinates",
    lat: state.userLocation.lat,
    lng: state.userLocation.lng
  };

  try {
    const response = await fetch(`${API_BASE_URL}/reports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (response.ok) {
      const newReport = await response.json();
      state.reports.unshift(newReport);
      renderKPIs();
      renderReports();
      renderMapMarkers();
    }
  } catch (error) {
    console.error('Failed to log automated SOS report:', error);
  }
}

function stopIronBellSOS() {
  const beacon = document.getElementById('sos-beacon');
  beacon.classList.add('hidden');

  if (state.sirenInterval) {
    clearInterval(state.sirenInterval);
    state.sirenInterval = null;
  }

  if (state.sirenOscillator) {
    state.sirenOscillator.forEach(osc => {
      try { osc.stop(); } catch (e) {}
    });
    state.sirenOscillator = null;
  }

  if (state.gainNode) {
    state.gainNode = null;
  }

  if (state.audioContext) {
    try { state.audioContext.close(); } catch (e) {}
    state.audioContext = null;
  }
}

// ==============================================================================
// CORE DATA LOADING & HANDLERS
// ==============================================================================

async function loadData() {
  try {
    const [reportsRes, resourcesRes] = await Promise.all([
      fetch(`${API_BASE_URL}/reports`),
      fetch(`${API_BASE_URL}/resources`)
    ]);

    if (!reportsRes.ok || !resourcesRes.ok) {
      throw new Error('API calls failed');
    }

    state.reports = await reportsRes.json();
    state.resources = await resourcesRes.json();

    // Render stats, lists, markers
    renderKPIs();
    renderReports();
    renderMapMarkers();
    renderNearbyServices();

  } catch (error) {
    console.error('Error fetching backend data:', error);
    showErrorMessage('Failed to load command server data.');
  }
}

// Handles submitting a new report (both Citizen Form and Authority Form)
async function handleFormSubmit(e, portal) {
  e.preventDefault();
  
  const form = e.target;
  const submitBtn = form.querySelector('button[type="submit"]');
  submitBtn.disabled = true;

  const textInput = portal === 'citizen' ? 'cit-text' : 'input-text';
  const locInput = portal === 'citizen' ? 'cit-location' : 'input-location';
  const latInput = portal === 'citizen' ? 'cit-lat' : 'input-lat';
  const lngInput = portal === 'citizen' ? 'cit-lng' : 'input-lng';

  const payload = {
    text: document.getElementById(textInput).value.trim(),
    source: portal === 'citizen' ? 'citizen_app' : document.getElementById('select-source').value,
    location_name: document.getElementById(locInput).value.trim(),
    lat: parseFloat(document.getElementById(latInput).value),
    lng: parseFloat(document.getElementById(lngInput).value)
  };

  try {
    const response = await fetch(`${API_BASE_URL}/reports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) throw new Error('Create failed');

    const newReport = await response.json();
    state.reports.unshift(newReport);

    // Refresh dashboard UI
    renderKPIs();
    renderReports();
    renderMapMarkers();

    // Reset inputs
    form.reset();
    form.classList.add('hidden');
    
    // Toggle collapse chevron back
    const chevron = form.parentNode.querySelector('.card-header i');
    if (chevron) {
      chevron.setAttribute('data-lucide', 'chevron-down');
      lucide.createIcons();
    }

    if (portal === 'authority') {
      selectReport(newReport.id);
      authorityMap.setView([newReport.lat, newReport.lng], 14);
    } else {
      citizenMap.setView([newReport.lat, newReport.lng], 14);
      L.popup()
        .setLatLng([newReport.lat, newReport.lng])
        .setContent(`<strong>Report Logged!</strong><br><span style="font-size:11px;">Your report has been successfully transmitted.</span>`)
        .openOn(citizenMap);
    }

  } catch (error) {
    alert('Failed to log report. Check coordinates and server status.');
  } finally {
    submitBtn.disabled = false;
  }
}

// Handle verify incident button clicks (Authority only)
async function handleVerifyIncident() {
  if (!state.selectedReportId) return;

  const btn = document.getElementById('btn-verify-incident');
  btn.disabled = true;

  try {
    const response = await fetch(`${API_BASE_URL}/reports/${state.selectedReportId}/verify`, {
      method: 'POST'
    });

    if (!response.ok) throw new Error();

    const updated = await response.json();

    const idx = state.reports.findIndex(r => r.id === state.selectedReportId);
    if (idx !== -1) {
      state.reports[idx] = updated;
    }

    renderKPIs();
    renderReports();
    renderMapMarkers();
    renderDetailsPanel(updated);

  } catch (error) {
    alert('Failed to verify incident.');
  } finally {
    btn.disabled = false;
  }
}

async function fetchSuggestedResources(reportId) {
  const container = document.getElementById('suggested-resources-list');
  container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';

  try {
    const response = await fetch(`${API_BASE_URL}/reports/${reportId}/suggested-resources?limit=3`);
    if (!response.ok) throw new Error();

    const resList = await response.json();
    renderSuggestedResources(resList);

  } catch (error) {
    container.innerHTML = '<p class="section-desc text-rose">Failed to load suggested units.</p>';
  }
}

// Autofill coordinates using geolocation API
function autofillCoordinates(latFieldId, lngFieldId, btnId) {
  const btn = document.getElementById(btnId);
  btn.disabled = true;

  if (!navigator.geolocation) {
    alert('Geolocation not supported.');
    btn.disabled = false;
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude.toFixed(4);
      const lng = pos.coords.longitude.toFixed(4);
      
      document.getElementById(latFieldId).value = lat;
      document.getElementById(lngFieldId).value = lng;
      
      // Update our location state coordinate
      state.userLocation = { lat: parseFloat(lat), lng: parseFloat(lng) };
      renderNearbyServices(); // Recompute distances
      
      btn.disabled = false;
    },
    (err) => {
      alert('Could not acquire location coordinates.');
      btn.disabled = false;
    },
    { timeout: 5000 }
  );
}

// ==============================================================================
// RENDERERS
// ==============================================================================

function renderKPIs() {
  const total = state.reports.length;
  const verified = state.reports.filter(r => r.credibility_score >= 70).length;
  const fires = state.reports.filter(r => r.category === 'fire').length;
  const availableRes = state.resources.filter(r => r.is_available).length;

  // Authority dashboard statistics
  const totStat = document.getElementById('stat-total-reports');
  if (totStat) totStat.innerText = total;
  
  const verStat = document.getElementById('stat-verified-reports');
  if (verStat) verStat.innerText = verified;
  
  const fireStat = document.getElementById('stat-active-fires');
  if (fireStat) fireStat.innerText = fires;
  
  const availStat = document.getElementById('stat-available-resources');
  if (availStat) availStat.innerText = availableRes;

  // Public Citizen view statistics
  const citActiveRes = document.getElementById('cit-active-resources');
  if (citActiveRes) {
    // Filter active response centers (NDRF + shelter + hospitals + police + fire)
    const activeHelpCenters = state.resources.filter(r => r.is_available && ['shelter', 'hospital', 'police_station'].includes(r.type)).length;
    citActiveRes.innerText = activeHelpCenters;
  }
}

function renderReports() {
  const container = document.getElementById('reports-list');
  if (!container) return; // not in authority dashboard currently

  container.innerHTML = '';
  const filtered = getFilteredReports();

  if (filtered.length === 0) {
    container.innerHTML = '<div class="empty-state"><i data-lucide="inbox"></i><p>No reports match filters.</p></div>';
    lucide.createIcons();
    return;
  }

  filtered.forEach(report => {
    const item = document.createElement('div');
    item.className = `report-item ${state.selectedReportId === report.id ? 'active' : ''}`;
    item.id = `report-item-${report.id}`;
    
    let scoreColor = 'bg-rose';
    if (report.credibility_score >= 70) scoreColor = 'bg-emerald';
    else if (report.credibility_score >= 40) scoreColor = 'bg-amber';

    item.innerHTML = `
      <div class="report-item-header">
        <span class="tag tag-${report.category}">${report.category}</span>
        <div class="score-pill">
          <span class="score-dot ${scoreColor}"></span>
          <span class="score-badge">${report.credibility_score}</span>
        </div>
      </div>
      <div class="report-location">${report.location_name}</div>
      <div class="report-text">${report.text}</div>
      <div class="report-footer">
        <div class="report-meta">
          <span><i data-lucide="radio"></i> ${report.source.replace('_', ' ')}</span>
          <span><i data-lucide="clock"></i> ${formatTimeAgo(report.created_at)}</span>
        </div>
      </div>
    `;

    item.addEventListener('click', () => {
      selectReport(report.id);
      authorityMap.setView([report.lat, report.lng], 14);
    });

    container.appendChild(item);
  });

  lucide.createIcons();
}

function renderMapMarkers() {
  // Clear layers on both maps
  citizenReportsLayer.clearLayers();
  authorityReportsLayer.clearLayers();
  citizenResourcesLayer.clearLayers();
  authorityResourcesLayer.clearLayers();

  const filteredReports = getFilteredReports();

  // 1. Draw Reports markers on both maps
  state.reports.forEach(report => {
    const isSelected = state.selectedReportId === report.id;
    const reportIcon = L.divIcon({
      className: `custom-marker report-marker category-${report.category} ${isSelected ? 'marker-selected' : ''}`,
      html: `
        <div class="marker-pulse"></div>
        <div class="marker-inner">
          ${CATEGORY_ICONS[report.category] || CATEGORY_ICONS['uncategorized']}
        </div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });

    // Popups
    const popupContent = `
      <div style="font-family: var(--font-sans);">
        <strong style="text-transform: capitalize;">${report.category} Incident</strong><br>
        <span style="font-size: 11px; color:#71717a;">${report.location_name}</span><br>
        <span style="font-size: 11px;">Credibility: <strong>${report.credibility_score}%</strong></span>
      </div>
    `;

    // Citizen Map Report
    const citMarker = L.marker([report.lat, report.lng], { icon: reportIcon });
    citMarker.bindPopup(popupContent);
    citizenReportsLayer.addLayer(citMarker);

    // Authority Map Report
    const authMarker = L.marker([report.lat, report.lng], { icon: reportIcon });
    authMarker.bindPopup(popupContent);
    authMarker.on('click', () => selectReport(report.id));
    authorityReportsLayer.addLayer(authMarker);
  });

  // 2. Draw Resource markers on both maps
  state.resources.forEach(res => {
    if (!res.is_available) return;

    const resourceIcon = L.divIcon({
      className: `custom-marker resource-marker ${res.type}-marker`,
      html: `
        <div class="marker-pulse"></div>
        <div class="marker-inner">
          <i data-lucide="${RESOURCE_ICONS[res.type] || 'truck'}"></i>
        </div>
      `,
      iconSize: [22, 22],
      iconAnchor: [11, 11]
    });

    const popupContent = `
      <div style="font-family: var(--font-sans);">
        <strong>${res.name}</strong><br>
        <span style="font-size:11px; text-transform: capitalize;">${res.type.replace('_', ' ')}</span>
      </div>
    `;

    // Add to Citizen Map
    const citResMarker = L.marker([res.lat, res.lng], { icon: resourceIcon });
    citResMarker.bindPopup(popupContent);
    citizenResourcesLayer.addLayer(citResMarker);

    // Add to Authority Map
    const authResMarker = L.marker([res.lat, res.lng], { icon: resourceIcon });
    authResMarker.bindPopup(popupContent);
    authorityResourcesLayer.addLayer(authResMarker);
  });

  lucide.createIcons();
}

function renderDetailsPanel(report) {
  const panel = document.getElementById('incident-details-card');
  if (!panel) return;
  panel.classList.remove('hidden');

  document.getElementById('detail-category-tag').className = `tag tag-${report.category}`;
  document.getElementById('detail-category-tag').innerText = report.category;
  document.getElementById('detail-location-name').innerText = report.location_name;
  document.getElementById('detail-text').innerText = report.text;
  document.getElementById('detail-source').innerText = report.source.replace('_', ' ');
  document.getElementById('detail-coords').innerText = `${report.lat.toFixed(4)}, ${report.lng.toFixed(4)}`;
  document.getElementById('detail-time').innerText = formatTimeAgo(report.created_at);
  document.getElementById('detail-score').innerText = `${report.credibility_score}/100`;
  document.getElementById('detail-verifications').innerText = report.verified_count;

  const label = document.getElementById('detail-label');
  label.innerText = report.credibility_label;
  label.className = `tag tag-${report.credibility_label.toLowerCase()}`;

  const bar = document.getElementById('detail-score-bar');
  bar.style.width = `${report.credibility_score}%`;
  bar.className = 'progress-bar';
  
  if (report.credibility_score >= 70) bar.classList.add('bar-emerald');
  else if (report.credibility_score >= 40) bar.classList.add('bar-amber');
  else bar.classList.add('bar-rose');

  lucide.createIcons();
}

function renderSuggestedResources(resources) {
  const container = document.getElementById('suggested-resources-list');
  if (!container) return;
  container.innerHTML = '';

  if (resources.length === 0) {
    container.innerHTML = '<p class="section-desc">No available emergency units found.</p>';
    return;
  }

  resources.forEach(res => {
    const item = document.createElement('div');
    item.className = 'resource-item';
    const iconName = RESOURCE_ICONS[res.type] || 'truck';

    item.innerHTML = `
      <div class="resource-info">
        <div class="resource-icon-badge">
          <i data-lucide="${iconName}"></i>
        </div>
        <div>
          <div class="resource-name">${res.name}</div>
          <div class="section-desc" style="text-transform: capitalize;">${res.type.replace('_', ' ')}</div>
        </div>
      </div>
      <div class="resource-distance-badge">${res.distance_km} km</div>
    `;

    container.appendChild(item);
  });

  lucide.createIcons();
}

// ==============================================================================
// HELPERS
// ==============================================================================

function selectReport(reportId) {
  state.selectedReportId = reportId;

  document.querySelectorAll('.report-item').forEach(el => el.classList.remove('active'));
  const activeListItem = document.getElementById(`report-item-${reportId}`);
  if (activeListItem) {
    activeListItem.classList.add('active');
    activeListItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  const report = state.reports.find(r => r.id === reportId);
  if (report) {
    renderDetailsPanel(report);
    fetchSuggestedResources(reportId);
  }

  renderMapMarkers();
}

function deselectReport() {
  state.selectedReportId = null;
  const card = document.getElementById('incident-details-card');
  if (card) card.classList.add('hidden');
  document.querySelectorAll('.report-item').forEach(el => el.classList.remove('active'));
  renderMapMarkers();
}

function getFilteredReports() {
  return state.reports.filter(report => {
    if (state.filters.category && report.category !== state.filters.category) return false;
    if (report.credibility_score < state.filters.minScore) return false;
    return true;
  });
}

function formatTimeAgo(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date + (now.getTimezoneOffset() * 60 * 1000); 
  const diffMinutes = Math.floor(diffMs / (1000 * 60));

  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

function showErrorMessage(message) {
  console.error(message);
}

// ==============================================================================
// SURVIVAL CHECKLIST & EXPLANATORY TOOLTIP MODALS
// ==============================================================================

const CHECKLIST_DATA = {
  flood: [
    "Prepare an emergency kit (water, canned food, flashlight, first aid, batteries).",
    "Identify local storm shelters and clear evacuation routes.",
    "Move valuable electrical appliances and paperwork to upper levels.",
    "Seal building foundations and install flood barriers or sandbags.",
    "Know how to turn off the main electricity breaker and gas valve."
  ],
  fire: [
    "Install smoke alarms on every level of your home and test them monthly.",
    "Create and practice a home fire evacuation plan with escape routes.",
    "Keep a working Class ABC fire extinguisher in the kitchen.",
    "Clear dry grass, leaves, and brush around the property boundary.",
    "Never leave cooking stoves or heating devices unattended."
  ],
  earthquake: [
    "Secure heavy shelves, television screens, and cabinets to walls.",
    "Identify safe spots in each room (under heavy tables or interior walls).",
    "Keep sturdy shoes and flashlights next to all beds.",
    "Establish a family emergency communication and reunion plan.",
    "Learn the 'Drop, Cover, and Hold On' emergency stance."
  ]
};

let activeChecklistDisaster = 'flood';

function initSurvivalChecklist() {
  const buttons = document.querySelectorAll('.guide-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const btnEl = e.currentTarget;
      buttons.forEach(b => b.classList.remove('active'));
      btnEl.classList.add('active');
      
      activeChecklistDisaster = btnEl.getAttribute('data-disaster');
      renderSurvivalChecklist();
    });
  });
}

function renderSurvivalChecklist() {
  const titleEl = document.getElementById('checklist-title');
  const container = document.getElementById('checklist-items');
  if (!container) return;
  
  container.innerHTML = '';
  
  const titleMap = {
    flood: "Flood Survival Checklist",
    fire: "Fire Survival Checklist",
    earthquake: "Earthquake Survival Checklist"
  };
  if (titleEl) titleEl.innerText = titleMap[activeChecklistDisaster] || "Disaster Prep Checklist";

  const items = CHECKLIST_DATA[activeChecklistDisaster] || [];
  
  const storageKey = `sankat_checklist_${activeChecklistDisaster}`;
  const checkedIndexes = JSON.parse(localStorage.getItem(storageKey) || '[]');

  items.forEach((text, index) => {
    const isChecked = checkedIndexes.includes(index);
    const div = document.createElement('div');
    div.className = `checklist-item ${isChecked ? 'checked' : ''}`;
    
    div.innerHTML = `
      <div class="checklist-checkbox">
        <i data-lucide="check"></i>
      </div>
      <span class="checklist-text">${text}</span>
    `;
    
    div.addEventListener('click', () => {
      toggleChecklistItem(index);
    });
    
    container.appendChild(div);
  });

  lucide.createIcons();
  updateChecklistProgress();
}

function toggleChecklistItem(index) {
  const storageKey = `sankat_checklist_${activeChecklistDisaster}`;
  let checkedIndexes = JSON.parse(localStorage.getItem(storageKey) || '[]');
  
  if (checkedIndexes.includes(index)) {
    checkedIndexes = checkedIndexes.filter(i => i !== index);
  } else {
    checkedIndexes.push(index);
  }
  
  localStorage.setItem(storageKey, JSON.stringify(checkedIndexes));
  renderSurvivalChecklist();
}

function updateChecklistProgress() {
  const items = CHECKLIST_DATA[activeChecklistDisaster] || [];
  const total = items.length;
  if (total === 0) return;
  
  const storageKey = `sankat_checklist_${activeChecklistDisaster}`;
  const checkedIndexes = JSON.parse(localStorage.getItem(storageKey) || '[]');
  const completed = checkedIndexes.length;
  
  const pct = Math.round((completed / total) * 100);
  
  const progressText = document.getElementById('checklist-progress-text');
  const progressBar = document.getElementById('checklist-progress-bar');
  
  if (progressText) progressText.innerText = `${pct}%`;
  if (progressBar) progressBar.style.width = `${pct}%`;
}

function initTooltipModal() {
  const modal = document.getElementById('info-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalText = document.getElementById('modal-text');
  
  if (!modal || !modalTitle || !modalText) return;

  const triggers = document.querySelectorAll('.tooltip-trigger');
  triggers.forEach(trigger => {
    trigger.addEventListener('click', () => {
      const label = trigger.querySelector('.w-label').innerText;
      const tooltip = trigger.getAttribute('data-tooltip');
      
      modalTitle.innerText = `${label} Details`;
      modalText.innerText = tooltip;
      modal.classList.remove('hidden');
    });
  });

  const hideModal = () => modal.classList.add('hidden');

  const closeBtn = modal.querySelector('#close-modal-btn');
  if (closeBtn) closeBtn.addEventListener('click', hideModal);
  
  const okBtn = document.getElementById('btn-modal-ok');
  if (okBtn) okBtn.addEventListener('click', hideModal);
  
  modal.addEventListener('click', (e) => {
    if (e.target === modal) hideModal();
  });
}
