// Global Application State
let appState = {
  activeTab: 'cockpit',
  overview: null,
  activities: [],
  filteredActivities: [],
  activeFilter: 'all',
  trends: [],
  profile: null,
  zones: null,
  trendDays: 90,
  charts: {
    miniTrend: null,
    bigTrend: null,
    volumeBar: null,
    modalHr: null,
    modalAltitude: null
  },
  modalMap: null
};

// Initialization on DOM Load
document.addEventListener('DOMContentLoaded', async () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  
  await loadUserProfile();
  await loadOverview();
  await loadActivities();
  await loadTrendData(90);
  await loadSettings();
  await loadZones();

  // Check URL query params for Strava callback
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('sync') === 'success') {
    showToast('🎉 Strava erfolgreich verknüpft! Aktivitäten wurden importiert.', 'info');
    window.history.replaceState({}, document.title, window.location.pathname);
    switchTab('activities');
  } else if (urlParams.get('sync') === 'error' || urlParams.get('sync') === 'token_error') {
    showToast('Fehler bei der Strava-Autorisierung. Bitte prüfe Client ID und Secret.', 'error');
    window.history.replaceState({}, document.title, window.location.pathname);
  }
});

// Toast notification helper
function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  const toastMsg = document.getElementById('toast-msg');
  const toastIcon = document.getElementById('toast-icon');

  toastMsg.textContent = message;
  toast.classList.remove('translate-y-20', 'opacity-0');
  toast.classList.add('translate-y-0', 'opacity-100');

  setTimeout(() => {
    toast.classList.remove('translate-y-0', 'opacity-100');
    toast.classList.add('translate-y-20', 'opacity-0');
  }, 4000);
}

// Tab Switching
function switchTab(tabId) {
  appState.activeTab = tabId;

  // Toggle content containers
  document.querySelectorAll('.tab-content').forEach(el => {
    el.classList.add('hidden');
  });
  const target = document.getElementById(`tab-${tabId}`);
  if (target) target.classList.remove('hidden');

  // Toggle button states
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('text-cyan-400', 'bg-slate-800/90', 'shadow-sm');
    btn.classList.add('text-slate-400');
  });

  const activeBtn = document.getElementById(`tab-btn-${tabId}`);
  if (activeBtn) {
    activeBtn.classList.remove('text-slate-400');
    activeBtn.classList.add('text-cyan-400', 'bg-slate-800/90', 'shadow-sm');
  }

  // Resize charts on tab activation
  if (tabId === 'trends' && appState.charts.bigTrend) {
    appState.charts.bigTrend.resize();
    if (appState.charts.volumeBar) appState.charts.volumeBar.resize();
  }
  if (tabId === 'cockpit' && appState.charts.miniTrend) {
    appState.charts.miniTrend.resize();
  }

  if (window.lucide) lucide.createIcons();
}

// 1. Load Overview Data (Cockpit)
async function loadOverview() {
  try {
    const res = await fetch('/api/overview');
    if (!res.ok) throw new Error('Fehler beim Laden des Überblicks');
    const data = await res.json();
    appState.overview = data;
    renderOverview(data);
  } catch (err) {
    console.error(err);
    showToast('Konnte Übersichtsdaten nicht laden.', 'error');
  }
}

function renderOverview(data) {
  // KPIs
  document.getElementById('kpi-total-km').textContent = data.total_km_7d;
  document.getElementById('kpi-run-km').textContent = `🏃 ${data.total_km_run_7d} km`;
  document.getElementById('kpi-ride-km').textContent = `🚴 ${data.total_km_ride_7d} km`;
  document.getElementById('kpi-total-hours').textContent = data.total_hours_7d;
  document.getElementById('kpi-total-elevation').textContent = `${data.total_elevation_7d} hm Höhenmeter`;

  // TSB / Form
  const tsbVal = data.current_tsb > 0 ? `+${data.current_tsb}` : data.current_tsb;
  document.getElementById('kpi-current-tsb').textContent = tsbVal;
  document.getElementById('kpi-current-ctl').textContent = data.current_ctl;
  document.getElementById('kpi-current-atl').textContent = data.current_atl;
  document.getElementById('kpi-tsb-status').textContent = data.tsb_status;

  // Nav badge
  document.getElementById('nav-tsb-text').textContent = `TSB: ${tsbVal} (${data.tsb_status})`;

  // VO2max
  document.getElementById('kpi-vo2max').textContent = data.estimated_vo2max;

  // Race predictions
  document.getElementById('pred-5k').textContent = data.predicted_5k;
  document.getElementById('pred-10k').textContent = data.predicted_10k;
  document.getElementById('pred-hm').textContent = data.predicted_hm;
  document.getElementById('pred-marathon').textContent = data.predicted_marathon;

  // Today's Suggestion
  const sugg = data.today_suggestion;
  if (sugg) {
    document.getElementById('sugg-title').textContent = sugg.title;
    document.getElementById('sugg-desc').textContent = sugg.description;
    document.getElementById('sugg-badge-readiness').textContent = sugg.today_readiness;
    document.getElementById('sugg-badge-type').textContent = sugg.workout_type;
    document.getElementById('sugg-target-duration').textContent = `${sugg.duration_min} Min ${sugg.target_distance_km ? '/ ' + sugg.target_distance_km + ' km' : ''}`;
    document.getElementById('sugg-target-hr').textContent = sugg.target_hr_range;
    document.getElementById('sugg-target-pace').textContent = sugg.target_pace_or_power;

    const focusContainer = document.getElementById('sugg-focus-container');
    focusContainer.innerHTML = '';
    (sugg.focus_points || []).forEach(pt => {
      const el = document.createElement('div');
      el.className = 'text-xs text-slate-300 bg-slate-900/60 border border-slate-800/80 rounded-lg p-2.5 flex items-start space-x-2';
      el.innerHTML = `<span class="text-cyan-400 font-bold">•</span><span>${pt}</span>`;
      focusContainer.appendChild(el);
    });
  }

  // Render recent activities snippet in Cockpit
  renderRecentActivitiesSnippet(data.recent_activities || []);
  if (window.lucide) lucide.createIcons();
}

function renderRecentActivitiesSnippet(acts) {
  const container = document.getElementById('recent-activities-list');
  if (!container) return;
  container.innerHTML = '';

  if (acts.length === 0) {
    container.innerHTML = '<div class="text-xs text-slate-500 text-center py-6">Keine Aktivitäten gefunden.</div>';
    return;
  }

  acts.slice(0, 5).forEach(act => {
    const isRun = act.sport_type === 'Run';
    const icon = isRun ? '🏃' : '🚴';
    const dateStr = new Date(act.start_date).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
    const metricStr = isRun ? `${act.avg_pace_min_km || '--'} /km` : `${act.avg_speed_kmh} km/h`;

    const card = document.createElement('div');
    card.className = 'flex items-center justify-between p-3 rounded-xl bg-slate-900/70 hover:bg-slate-800/80 border border-slate-800 cursor-pointer transition';
    card.onclick = () => openActivityDetail(act.id);

    card.innerHTML = `
      <div class="flex items-center space-x-3 min-w-0">
        <span class="text-lg">${icon}</span>
        <div class="min-w-0">
          <div class="text-xs font-bold text-white truncate">${act.title}</div>
          <div class="text-[11px] text-slate-400 font-mono">${dateStr} • ${act.distance_km} km</div>
        </div>
      </div>
      <div class="text-right flex-shrink-0">
        <div class="text-xs font-bold text-cyan-400 font-mono">${metricStr}</div>
        <div class="text-[11px] text-rose-400 font-mono">${act.avg_hr ? act.avg_hr + ' bpm' : '--'}</div>
      </div>
    `;
    container.appendChild(card);
  });
}

// 2. Load Trend Timeline Data
async function loadTrendData(days = 90) {
  appState.trendDays = days;
  
  // Highlight active button
  [30, 60, 90, 180].forEach(d => {
    const btn = document.getElementById(`range-${d}`);
    if (btn) {
      if (d === days) {
        btn.className = 'px-3 py-1.5 rounded-md bg-slate-800 text-cyan-400 font-semibold shadow-sm transition';
      } else {
        btn.className = 'px-3 py-1.5 rounded-md text-slate-400 hover:text-white transition';
      }
    }
  });

  try {
    const res = await fetch(`/api/trends?days=${days}`);
    if (!res.ok) throw new Error('Fehler beim Laden der Trenddaten');
    const data = await res.json();
    appState.trends = data;

    renderBigTrendChart(data);
    renderVolumeChart(data);
    renderMiniTrendChart(data.slice(-30));
  } catch (err) {
    console.error(err);
  }
}

function renderMiniTrendChart(data) {
  const ctx = document.getElementById('mini-trend-chart');
  if (!ctx) return;

  const labels = data.map(d => d.date.split('-').slice(1).join('.'));
  const ctlValues = data.map(d => d.ctl);
  const tsbValues = data.map(d => d.tsb);

  if (appState.charts.miniTrend) {
    appState.charts.miniTrend.destroy();
  }

  appState.charts.miniTrend = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Fitness (CTL)',
          data: ctlValues,
          borderColor: '#8b5cf6',
          backgroundColor: 'rgba(139, 92, 246, 0.1)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 0
        },
        {
          label: 'Form (TSB)',
          data: tsbValues,
          borderColor: '#10b981',
          borderWidth: 2,
          tension: 0.3,
          pointRadius: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
        tooltip: {
          backgroundColor: '#0f172a',
          titleColor: '#e2e8f0',
          borderColor: '#334155',
          borderWidth: 1
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#64748b', maxTicksLimit: 7 } },
        y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748b' } }
      }
    }
  });
}

function renderBigTrendChart(data) {
  const ctx = document.getElementById('big-trend-chart');
  if (!ctx) return;

  const labels = data.map(d => d.date.split('-').slice(1).join('.'));
  const ctlValues = data.map(d => d.ctl);
  const atlValues = data.map(d => d.atl);
  const tsbValues = data.map(d => d.tsb);
  const loadValues = data.map(d => d.load);

  if (appState.charts.bigTrend) {
    appState.charts.bigTrend.destroy();
  }

  appState.charts.bigTrend = new Chart(ctx, {
    data: {
      labels: labels,
      datasets: [
        {
          type: 'bar',
          label: 'Täglicher TSS (Reiz)',
          data: loadValues,
          backgroundColor: 'rgba(6, 182, 212, 0.25)',
          hoverBackgroundColor: 'rgba(6, 182, 212, 0.6)',
          yAxisID: 'y1',
          borderRadius: 2,
          order: 4
        },
        {
          type: 'line',
          label: 'Fitness (CTL 42d)',
          data: ctlValues,
          borderColor: '#8b5cf6',
          borderWidth: 2.5,
          tension: 0.3,
          pointRadius: 0,
          yAxisID: 'y',
          order: 2
        },
        {
          type: 'line',
          label: 'Ermüdung (ATL 7d)',
          data: atlValues,
          borderColor: '#f43f5e',
          borderWidth: 2,
          tension: 0.3,
          pointRadius: 0,
          yAxisID: 'y',
          order: 1
        },
        {
          type: 'line',
          label: 'Form / Balance (TSB)',
          data: tsbValues,
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.05)',
          fill: true,
          borderWidth: 2,
          tension: 0.25,
          pointRadius: 0,
          yAxisID: 'y',
          order: 3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#94a3b8', font: { size: 12, family: 'JetBrains Mono' } }
        },
        tooltip: {
          backgroundColor: '#0f172a',
          titleColor: '#f1f5f9',
          bodyColor: '#cbd5e1',
          borderColor: '#334155',
          borderWidth: 1,
          padding: 10
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.03)' },
          ticks: { color: '#64748b', maxTicksLimit: 12 }
        },
        y: {
          position: 'left',
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8' },
          title: { display: true, text: 'CTL / ATL / TSB', color: '#64748b' }
        },
        y1: {
          position: 'right',
          grid: { display: false },
          ticks: { color: '#06b6d4' },
          title: { display: true, text: 'Tages-TSS', color: '#06b6d4' },
          min: 0,
          max: 200
        }
      }
    }
  });
}

function renderVolumeChart(data) {
  const ctx = document.getElementById('volume-bar-chart');
  if (!ctx) return;

  // Aggregate by weekly buckets
  const weeklyMap = {};
  data.forEach(d => {
    // Rough week grouping (every 7 days)
    const dt = new Date(d.date);
    const weekStart = new Date(dt.setDate(dt.getDate() - dt.getDay() + 1)).toISOString().split('T')[0];
    if (!weeklyMap[weekStart]) {
      weeklyMap[weekStart] = { run: 0, ride: 0 };
    }
    weeklyMap[weekStart].run += d.km_run;
    weeklyMap[weekStart].ride += d.km_ride;
  });

  const weeks = Object.keys(weeklyMap).sort();
  const labels = weeks.map(w => 'KW ' + w.split('-').slice(1).join('.'));
  const runData = weeks.map(w => Math.round(weeklyMap[w].run));
  const rideData = weeks.map(w => Math.round(weeklyMap[w].ride));

  if (appState.charts.volumeBar) {
    appState.charts.volumeBar.destroy();
  }

  appState.charts.volumeBar = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: '🏃 Laufen (km)',
          data: runData,
          backgroundColor: '#06b6d4',
          borderRadius: 4
        },
        {
          label: '🚴 Radfahren (km)',
          data: rideData,
          backgroundColor: '#6366f1',
          borderRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { color: '#64748b' } },
        y: { stacked: true, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748b' } }
      },
      plugins: {
        legend: { labels: { color: '#94a3b8' } }
      }
    }
  });
}

// 3. Load & Render Activities Tab
async function loadActivities() {
  try {
    const res = await fetch('/api/activities?limit=100');
    if (!res.ok) throw new Error('Fehler beim Laden');
    const acts = await res.json();
    appState.activities = acts;
    filterActivities(appState.activeFilter);
  } catch (err) {
    console.error(err);
  }
}

function filterActivities(sport) {
  appState.activeFilter = sport;

  // Update filter button styling
  ['all', 'run', 'ride'].forEach(s => {
    const btn = document.getElementById(`filter-${s}`);
    if (btn) {
      if (s === sport.toLowerCase()) {
        btn.className = 'act-filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-cyan-400 border border-cyan-500/30';
      } else {
        btn.className = 'act-filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white bg-slate-900 border border-slate-800';
      }
    }
  });

  let filtered = appState.activities;
  if (sport !== 'all') {
    filtered = filtered.filter(a => a.sport_type.toLowerCase() === sport.toLowerCase());
  }
  appState.filteredActivities = filtered;

  document.getElementById('activities-count').textContent = `${filtered.length} Einheiten`;
  renderActivitiesGrid(filtered);
}

function renderActivitiesGrid(acts) {
  const container = document.getElementById('activities-grid');
  if (!container) return;
  container.innerHTML = '';

  if (acts.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-12 text-center text-slate-500">
        Keine Aktivitäten in diesem Filter gefunden.
      </div>
    `;
    return;
  }

  acts.forEach(act => {
    const isRun = act.sport_type === 'Run';
    const icon = isRun ? '🏃' : '🚴';
    const dateStr = new Date(act.start_date).toLocaleDateString('de-DE', {
      weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric'
    });
    const durMins = Math.round(act.moving_time_seconds / 60);
    const paceStr = isRun ? `${act.avg_pace_min_km || '--'} min/km` : `${act.avg_speed_kmh} km/h`;

    // Source badge
    let sourceBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300">Strava</span>`;
    if (act.source === 'huawei') {
      sourceBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-red-500/20 text-red-400 border border-red-500/30">Huawei Health</span>`;
    } else if (act.source === 'demo') {
      sourceBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">Demo</span>`;
    }

    const card = document.createElement('div');
    card.className = 'glass-card rounded-xl p-5 border border-slate-800 hover:border-slate-700 cursor-pointer transition flex flex-col justify-between space-y-4';
    card.onclick = () => openActivityDetail(act.id);

    card.innerHTML = `
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-2.5">
          <div class="w-9 h-9 rounded-xl ${isRun ? 'bg-cyan-500/10 text-cyan-400' : 'bg-indigo-500/10 text-indigo-400'} flex items-center justify-center text-lg">
            ${icon}
          </div>
          <div>
            <h4 class="text-sm font-bold text-white line-clamp-1">${act.title}</h4>
            <span class="text-[11px] text-slate-400 font-mono">${dateStr}</span>
          </div>
        </div>
        ${sourceBadge}
      </div>

      <div class="grid grid-cols-3 gap-2 py-2 border-y border-slate-800/80 text-center font-mono">
        <div>
          <div class="text-[10px] text-slate-500 uppercase">Distanz</div>
          <div class="text-sm font-bold text-white">${act.distance_km} km</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500 uppercase">Dauer</div>
          <div class="text-sm font-bold text-white">${durMins} Min</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500 uppercase">${isRun ? 'Pace' : 'Speed'}</div>
          <div class="text-sm font-bold text-cyan-400">${paceStr}</div>
        </div>
      </div>

      <div class="flex items-center justify-between text-xs text-slate-400 font-mono">
        <span>❤️ Ø ${act.avg_hr || '--'} bpm</span>
        <span>⛰️ ${act.elevation_gain_m} hm</span>
        <span class="text-slate-300 font-bold">TSS ${act.tss || '--'}</span>
      </div>
    `;
    container.appendChild(card);
  });
}

// 4. Activity Detail Modal
async function openActivityDetail(actId) {
  try {
    const res = await fetch(`/api/activities/${actId}`);
    if (!res.ok) throw new Error('Aktivität nicht gefunden');
    const act = await res.json();

    const isRun = act.sport_type === 'Run';
    document.getElementById('modal-sport-icon').textContent = isRun ? '🏃' : '🚴';
    document.getElementById('modal-title').textContent = act.title;
    document.getElementById('modal-date').textContent = new Date(act.start_date).toLocaleString('de-DE');
    document.getElementById('modal-source-badge').textContent = act.source.toUpperCase();

    document.getElementById('modal-dist').textContent = `${act.distance_km} km`;
    const durM = Math.floor(act.moving_time_seconds / 60);
    const durS = act.moving_time_seconds % 60;
    document.getElementById('modal-time').textContent = `${durM}:${durS < 10 ? '0' : ''}${durS} Std:Min`;
    document.getElementById('modal-pace').textContent = isRun ? `${act.avg_pace_min_km || '--'} min/km` : `${act.avg_speed_kmh} km/h`;
    document.getElementById('modal-hr').textContent = act.avg_hr ? `${act.avg_hr} bpm (Max: ${act.max_hr || '--'})` : '--';

    document.getElementById('modal-elev').textContent = `${act.elevation_gain_m} m`;
    document.getElementById('modal-cadence').textContent = act.avg_cadence ? `${act.avg_cadence} ${isRun ? 'spm' : 'rpm'}` : '--';
    document.getElementById('modal-tss').textContent = `${act.tss || '--'} Stress`;

    // HR Zones bar
    const hrBar = document.getElementById('modal-hr-bar');
    hrBar.innerHTML = '';
    if (act.hr_zones) {
      const totalSec = Object.values(act.hr_zones).reduce((a, b) => a + b, 0) || 1;
      const colors = ['#10b981', '#06b6d4', '#3b82f6', '#f59e0b', '#ef4444'];
      ['z1', 'z2', 'z3', 'z4', 'z5'].forEach((zKey, idx) => {
        const sec = act.hr_zones[zKey] || 0;
        const pct = Math.round((sec / totalSec) * 100);
        if (pct > 0) {
          const seg = document.createElement('div');
          seg.style.width = `${pct}%`;
          seg.style.backgroundColor = colors[idx];
          seg.className = 'h-full transition-all';
          seg.title = `${zKey.toUpperCase()}: ${Math.round(sec / 60)} Min (${pct}%)`;
          hrBar.appendChild(seg);
        }
      });
      document.getElementById('modal-hr-zones-section').classList.remove('hidden');
    } else {
      document.getElementById('modal-hr-zones-section').classList.add('hidden');
    }

    // Splits table
    const splitsSection = document.getElementById('modal-splits-section');
    const splitsTbody = document.getElementById('modal-splits-tbody');
    splitsTbody.innerHTML = '';

    if (act.splits && act.splits.length > 0) {
      splitsSection.classList.remove('hidden');
      act.splits.forEach(s => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/40 text-slate-300';
        tr.innerHTML = `
          <td class="py-1.5 px-3 font-bold text-white">Km ${s.km}</td>
          <td class="py-1.5 px-3 text-cyan-400">${s.pace_formatted} /km</td>
          <td class="py-1.5 px-3 text-rose-400">${s.avg_hr ? s.avg_hr + ' bpm' : '--'}</td>
          <td class="py-1.5 px-3 text-slate-400">${s.elevation_diff > 0 ? '+' : ''}${s.elevation_diff || 0} m</td>
        `;
        splitsTbody.appendChild(tr);
      });
    } else {
      splitsSection.classList.add('hidden');
    }

    // Show modal first so Leaflet and Chart.js have visible container dimensions
    document.getElementById('activity-modal').classList.remove('hidden');
    if (window.lucide) lucide.createIcons();

    // Fetch detailed streams from API (GPS, HR, Altitude, Velocity)
    try {
      const streamRes = await fetch(`/api/activities/${actId}/streams`);
      if (streamRes.ok) {
        const sData = await streamRes.json();
        if (sData.available) {
          // 1. Map
          let latlngs = sData.latlng;
          if ((!latlngs || latlngs.length === 0) && sData.polyline) {
            latlngs = decodePolyline(sData.polyline);
          }
          renderActivityMap(latlngs);

          // 2. HR Chart
          const timeSec = sData.time || [];
          renderModalHrChart(timeSec, sData.heartrate);

          // 3. Altitude & Speed Chart
          renderModalAltitudeChart(timeSec, sData.altitude, sData.velocity_smooth, act.sport_type);
        } else {
          renderActivityMap(null);
          renderModalHrChart([], null);
          renderModalAltitudeChart([], null, null, act.sport_type);
        }
      } else {
        renderActivityMap(null);
        renderModalHrChart([], null);
        renderModalAltitudeChart([], null, null, act.sport_type);
      }
    } catch (e) {
      console.warn("Could not fetch streams:", e);
      renderActivityMap(null);
      renderModalHrChart([], null);
      renderModalAltitudeChart([], null, null, act.sport_type);
    }

  } catch (err) {
    console.error(err);
    showToast('Aktivitätsdetails konnten nicht geladen werden', 'error');
  }
}

function closeActivityModal() {
  document.getElementById('activity-modal').classList.add('hidden');
  if (appState.modalMap) {
    appState.modalMap.remove();
    appState.modalMap = null;
  }
  if (appState.charts.modalHr) {
    appState.charts.modalHr.destroy();
    appState.charts.modalHr = null;
  }
  if (appState.charts.modalAltitude) {
    appState.charts.modalAltitude.destroy();
    appState.charts.modalAltitude = null;
  }
}

// Polyline decoder for Google/Strava encoded polylines
function decodePolyline(str, precision) {
  var index = 0,
      lat = 0,
      lng = 0,
      coordinates = [],
      shift = 0,
      result = 0,
      byte = null,
      latitude_change,
      longitude_change,
      factor = Math.pow(10, Number.isInteger(precision) ? precision : 5);

  while (index < str.length) {
    byte = null; shift = 0; result = 0;
    do {
      byte = str.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    latitude_change = ((result & 1) ? ~(result >> 1) : (result >> 1));

    shift = 0; result = 0;
    do {
      byte = str.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    longitude_change = ((result & 1) ? ~(result >> 1) : (result >> 1));

    lat += latitude_change;
    lng += longitude_change;
    coordinates.push([lat / factor, lng / factor]);
  }
  return coordinates;
}

// Render interactive Leaflet route map
function renderActivityMap(latlngs) {
  const fallback = document.getElementById('modal-map-fallback');
  const statusEl = document.getElementById('modal-map-status');

  if (!latlngs || latlngs.length === 0) {
    if (appState.modalMap) {
      appState.modalMap.remove();
      appState.modalMap = null;
    }
    fallback.classList.remove('hidden');
    statusEl.textContent = 'Keine GPS-Punkte';
    return;
  }

  fallback.classList.add('hidden');
  statusEl.textContent = `${latlngs.length} GPS-Punkte`;

  if (appState.modalMap) {
    appState.modalMap.remove();
    appState.modalMap = null;
  }

  // Initialize Leaflet map
  appState.modalMap = L.map('modal-map', {
    zoomControl: true,
    attributionControl: false
  });

  // Dark-themed OpenStreetMap tiles via CartoDB
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    subdomains: 'abcd'
  }).addTo(appState.modalMap);

  // Draw glowing cyan route line
  const polyline = L.polyline(latlngs, {
    color: '#06b6d4',
    weight: 4,
    opacity: 0.9,
    lineJoin: 'round'
  }).addTo(appState.modalMap);

  // Add Start (Emerald) and Finish (Rose) circle markers
  const startPt = latlngs[0];
  const endPt = latlngs[latlngs.length - 1];

  L.circleMarker(startPt, {
    radius: 6,
    fillColor: '#10b981',
    color: '#ffffff',
    weight: 2,
    fillOpacity: 1
  }).addTo(appState.modalMap).bindPopup('Start');

  L.circleMarker(endPt, {
    radius: 6,
    fillColor: '#f43f5e',
    color: '#ffffff',
    weight: 2,
    fillOpacity: 1
  }).addTo(appState.modalMap).bindPopup('Ziel');

  // Fit bounds to the route
  appState.modalMap.fitBounds(polyline.getBounds(), { padding: [25, 25] });

  setTimeout(() => {
    if (appState.modalMap) appState.modalMap.invalidateSize();
  }, 250);
}

// Render Heart Rate Stream Chart
function renderModalHrChart(timeSec, hrData) {
  const ctx = document.getElementById('modal-hr-chart');
  if (!ctx) return;

  if (appState.charts.modalHr) {
    appState.charts.modalHr.destroy();
    appState.charts.modalHr = null;
  }

  if (!hrData || hrData.length === 0) {
    document.getElementById('modal-hr-chart-container').classList.add('hidden');
    return;
  }
  document.getElementById('modal-hr-chart-container').classList.remove('hidden');

  // Subsample if too many points (> 300) for smooth rendering
  let finalTimes = timeSec;
  let finalHr = hrData;
  if (hrData.length > 300) {
    const step = Math.ceil(hrData.length / 300);
    finalTimes = timeSec.filter((_, i) => i % step === 0);
    finalHr = hrData.filter((_, i) => i % step === 0);
  }

  const labels = finalTimes.map(t => {
    const mins = Math.floor(t / 60);
    const secs = t % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  });

  const validHrs = hrData.filter(h => typeof h === 'number');
  const maxHr = validHrs.length > 0 ? Math.max(...validHrs) : '--';
  document.getElementById('modal-hr-max-label').textContent = `Max: ${maxHr} bpm`;

  appState.charts.modalHr = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Herzfrequenz (bpm)',
        data: finalHr,
        borderColor: '#f43f5e',
        backgroundColor: 'rgba(244, 63, 94, 0.12)',
        fill: true,
        tension: 0.25,
        borderWidth: 2,
        pointRadius: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0f172a',
          titleColor: '#e2e8f0',
          borderColor: '#334155',
          borderWidth: 1,
          callbacks: {
            label: (c) => ` Puls: ${c.parsed.y} bpm`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#64748b', maxTicksLimit: 8, font: { size: 10 } }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 } }
        }
      }
    }
  });
}

// Render Altitude and Speed Stream Chart
function renderModalAltitudeChart(timeSec, altitudeData, velocityData, sportType) {
  const ctx = document.getElementById('modal-altitude-chart');
  if (!ctx) return;

  if (appState.charts.modalAltitude) {
    appState.charts.modalAltitude.destroy();
    appState.charts.modalAltitude = null;
  }

  const hasAlt = altitudeData && altitudeData.length > 0;
  const hasVel = velocityData && velocityData.length > 0;

  if (!hasAlt && !hasVel) {
    document.getElementById('modal-altitude-chart-container').classList.add('hidden');
    return;
  }
  document.getElementById('modal-altitude-chart-container').classList.remove('hidden');

  // Subsample
  const dataLen = (altitudeData || velocityData).length;
  let finalTimes = timeSec;
  let finalAlt = altitudeData;
  let finalVel = velocityData;

  if (dataLen > 300) {
    const step = Math.ceil(dataLen / 300);
    finalTimes = timeSec.filter((_, i) => i % step === 0);
    if (hasAlt) finalAlt = altitudeData.filter((_, i) => i % step === 0);
    if (hasVel) finalVel = velocityData.filter((_, i) => i % step === 0);
  }

  const labels = finalTimes.map(t => {
    const mins = Math.floor(t / 60);
    return `${mins} min`;
  });

  const datasets = [];

  if (hasAlt) {
    datasets.push({
      type: 'line',
      label: 'Höhe (m)',
      data: finalAlt,
      borderColor: '#f59e0b',
      backgroundColor: 'rgba(245, 158, 11, 0.1)',
      fill: true,
      tension: 0.2,
      borderWidth: 1.8,
      pointRadius: 0,
      yAxisID: 'yAlt'
    });
  }

  if (hasVel) {
    // velocity m/s -> km/h
    const speedKmh = finalVel.map(v => v ? Math.round(v * 3.6 * 10) / 10 : 0);
    datasets.push({
      type: 'line',
      label: sportType === 'Run' ? 'Geschwindigkeit (km/h)' : 'Tempo (km/h)',
      data: speedKmh,
      borderColor: '#06b6d4',
      borderWidth: 1.5,
      tension: 0.3,
      pointRadius: 0,
      yAxisID: 'yVel'
    });
  }

  appState.charts.modalAltitude = new Chart(ctx, {
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 10 } } },
        tooltip: {
          backgroundColor: '#0f172a',
          titleColor: '#e2e8f0',
          borderColor: '#334155',
          borderWidth: 1
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#64748b', maxTicksLimit: 8, font: { size: 10 } }
        },
        yAlt: {
          position: 'left',
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#f59e0b', font: { size: 10 } },
          title: { display: true, text: 'Höhe (m)', color: '#f59e0b' }
        },
        yVel: {
          position: 'right',
          grid: { display: false },
          ticks: { color: '#06b6d4', font: { size: 10 } },
          title: { display: true, text: 'km/h', color: '#06b6d4' }
        }
      }
    }
  });
}

// 5. AI Coach Chat
async function sendCoachMessage() {
  const input = document.getElementById('coach-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  appendChatMessage('user', text);

  // Send request
  try {
    const btn = document.getElementById('coach-send-btn');
    btn.disabled = true;
    btn.classList.add('opacity-50');

    const res = await fetch('/api/coach/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });

    if (!res.ok) throw new Error('Coach-Fehler');
    const data = await res.json();
    appendChatMessage('ai', data.response, data.notice);
  } catch (err) {
    appendChatMessage('ai', 'Entschuldigung, beim Verarbeiten ist ein Fehler aufgetreten. Bitte versuche es erneut.');
  } finally {
    const btn = document.getElementById('coach-send-btn');
    btn.disabled = false;
    btn.classList.remove('opacity-50');
  }
}

function askCoachPrompt(promptText) {
  document.getElementById('coach-input').value = promptText;
  sendCoachMessage();
}

function appendChatMessage(sender, text, notice = null) {
  const log = document.getElementById('coach-chat-log');
  const msgDiv = document.createElement('div');
  
  if (sender === 'user') {
    msgDiv.className = 'flex items-start justify-end space-x-3';
    msgDiv.innerHTML = `
      <div class="chat-bubble-user rounded-2xl rounded-tr-sm p-4 text-sm text-white leading-relaxed max-w-2xl shadow-md">
        ${escapeHtml(text)}
      </div>
      <div class="w-8 h-8 rounded-lg bg-cyan-600 flex items-center justify-center flex-shrink-0 text-white font-bold text-xs">
        DU
      </div>
    `;
  } else {
    // Format simple markdown (bold, lists)
    let formatted = escapeHtml(text)
      .replace(/### (.*?)\n/g, '<h4 class="font-bold text-white text-base mt-2 mb-1">$1</h4>')
      .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>')
      .replace(/\*(.*?)\*/g, '<em class="text-cyan-300">$1</em>')
      .replace(/\n- (.*?)/g, '<li class="ml-4 list-disc text-slate-300">$1</li>')
      .replace(/\n\n/g, '<br><br>');

    msgDiv.className = 'flex items-start space-x-3';
    msgDiv.innerHTML = `
      <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center flex-shrink-0 shadow-md">
        <i data-lucide="bot" class="w-4 h-4 text-white"></i>
      </div>
      <div class="chat-bubble-ai rounded-2xl rounded-tl-sm p-4 text-sm text-slate-200 leading-relaxed max-w-2xl">
        ${formatted}
        ${notice ? `<div class="mt-3 pt-2 border-t border-slate-800 text-[11px] text-amber-400 font-mono">${notice}</div>` : ''}
      </div>
    `;
  }

  log.appendChild(msgDiv);
  log.scrollTop = log.scrollHeight;
  if (window.lucide) lucide.createIcons();
}

function escapeHtml(string) {
  return String(string).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// 6. Settings, Profile & Synchronization
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    document.getElementById('strava-client-id').value = data.strava_client_id || '';
    if (data.strava_last_sync) {
      document.getElementById('sync-last-time').textContent = data.strava_last_sync;
    }
    const demoInd = document.getElementById('demo-indicator');
    if (demoInd) {
      demoInd.style.display = data.demo_mode ? 'flex' : 'none';
    }
  } catch (err) {
    console.error(err);
  }
}

async function saveStravaSettings(notify = true) {
  const clientId = document.getElementById('strava-client-id').value.trim();
  const secret = document.getElementById('strava-client-secret').value.trim();

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strava_client_id: clientId,
        strava_client_secret: secret
      })
    });
    if (res.ok && notify) {
      showToast('Client ID & Secret erfolgreich gespeichert!');
    }
    return res.ok;
  } catch (err) {
    if (notify) showToast('Fehler beim Speichern der Einstellungen', 'error');
    return false;
  }
}

async function connectWithStrava() {
  const clientId = document.getElementById('strava-client-id').value.trim();
  const secret = document.getElementById('strava-client-secret').value.trim();

  if (!clientId || !secret) {
    showToast('Bitte zuerst Strava Client ID und Secret eingeben!', 'error');
    return;
  }

  showToast('Bereite Strava-Verbindung vor...');
  await saveStravaSettings(false);

  try {
    const res = await fetch('/api/strava/auth-url');
    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || 'Fehler beim Abrufen der Strava-URL', 'error');
      return;
    }
    const data = await res.json();
    if (data.url) {
      window.location.href = data.url;
    }
  } catch (err) {
    showToast('Fehler beim Verbinden mit Strava', 'error');
  }
}

async function triggerQuickSync() {
  const icon = document.getElementById('sync-icon');
  if (icon) icon.classList.add('animate-spin');

  try {
    const res = await fetch('/api/sync/strava', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast(`Sync erfolgreich! ${data.synced_count} Aktivitäten aktualisiert (inkl. ${data.huawei_detected} von Huawei Health).`);
      await loadOverview();
      await loadActivities();
      await loadTrendData(appState.trendDays);
      await loadSettings();
    } else {
      showToast(data.error || 'Sync fehlgeschlagen', 'error');
    }
  } catch (err) {
    showToast('Netzwerkfehler beim Strava-Sync', 'error');
  } finally {
    if (icon) icon.classList.remove('animate-spin');
  }
}

async function handleFileUpload(file) {
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);

  showToast(`Lade ${file.name} hoch...`);
  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Erfolgreich importiert: ${data.activity.title}`);
      await loadOverview();
      await loadActivities();
      await loadTrendData(appState.trendDays);
    } else {
      showToast(data.detail || 'Fehler beim Upload', 'error');
    }
  } catch (err) {
    showToast('Fehler beim Verarbeiten der Datei', 'error');
  }
}

async function resetDemoData() {
  if (!confirm('Möchtest du die Datenbank auf die 60-Tage Demo-Daten zurücksetzen?')) return;
  try {
    const res = await fetch('/api/demo/reset', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast(`${data.count} authentische Demo-Aktivitäten geladen!`);
      await loadOverview();
      await loadActivities();
      await loadTrendData(appState.trendDays);
      await loadSettings();
    }
  } catch (err) {
    showToast('Fehler beim Zurücksetzen', 'error');
  }
}

// 7. Profile & Zones
async function loadUserProfile() {
  try {
    const res = await fetch('/api/profile');
    const p = await res.json();
    appState.profile = p;

    document.getElementById('prof-name').value = p.athlete_name;
    document.getElementById('prof-max-hr').value = p.max_hr;
    document.getElementById('prof-rest-hr').value = p.resting_hr;
    document.getElementById('prof-threshold-pace').value = p.threshold_pace_sec;
    document.getElementById('prof-ftp').value = p.ftp_watts;
    document.getElementById('prof-weight').value = p.weight_kg;
    document.getElementById('prof-target-km').value = p.weekly_target_km;
  } catch (err) {
    console.error(err);
  }
}

async function saveUserProfile() {
  const profile = {
    athlete_name: document.getElementById('prof-name').value,
    max_hr: parseInt(document.getElementById('prof-max-hr').value) || 190,
    resting_hr: parseInt(document.getElementById('prof-rest-hr').value) || 52,
    threshold_pace_sec: parseInt(document.getElementById('prof-threshold-pace').value) || 280,
    ftp_watts: parseInt(document.getElementById('prof-ftp').value) || 240,
    weight_kg: parseFloat(document.getElementById('prof-weight').value) || 72.0,
    weekly_target_km: parseFloat(document.getElementById('prof-target-km').value) || 40.0,
    primary_sport: 'Multisport'
  };

  const geminiKey = document.getElementById('settings-gemini-key').value.trim();
  if (geminiKey) {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gemini_api_key: geminiKey })
    });
  }

  try {
    const res = await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile)
    });
    if (res.ok) {
      showToast('Profil und Zonen erfolgreich aktualisiert!');
      await loadZones();
      await loadOverview();
    }
  } catch (err) {
    showToast('Fehler beim Speichern des Profils', 'error');
  }
}

async function loadZones() {
  try {
    const res = await fetch('/api/zones');
    const zones = await res.json();
    appState.zones = zones;

    const list = document.getElementById('hr-zones-list');
    if (!list) return;
    list.innerHTML = '';

    const zoneKeys = ['z1', 'z2', 'z3', 'z4', 'z5'];
    zoneKeys.forEach(k => {
      const z = zones[k];
      const div = document.createElement('div');
      div.className = 'flex items-center justify-between p-3.5 rounded-xl bg-slate-900/80 border border-slate-800';
      div.innerHTML = `
        <div class="flex items-center space-x-3">
          <div class="w-3.5 h-10 rounded-full" style="background-color: ${z.color}"></div>
          <div>
            <div class="text-sm font-bold text-white flex items-center space-x-2">
              <span>${k.toUpperCase()}: ${z.name}</span>
            </div>
            <div class="text-xs text-slate-400">${z.desc}</div>
          </div>
        </div>
        <div class="text-right font-mono">
          <div class="text-sm font-bold text-white">${z.min} - ${z.max} bpm</div>
          <div class="text-[11px] text-slate-500">Pulsbereich</div>
        </div>
      `;
      list.appendChild(div);
    });
  } catch (err) {
    console.error(err);
  }
}
