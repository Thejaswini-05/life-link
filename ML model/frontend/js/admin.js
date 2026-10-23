/**
 * LifeLink Admin Fleet Command & Multi-User Mock Drill Studio
 * Features:
 * - Live User Telepresence & Telemetry Inspector (View all live data for any user)
 * - Targeted Mock Drill Injection per Individual User
 * - Real-Time Multi-Vehicle Chart.js Dynamic Plotting
 * - Fleet Management & iOBD Hardware Inspection
 * - Strict Role-Based Access Control (Admin Isolation)
 */

let socket = null;
let impactChart = null;
let decisionChart = null;
const MAX_CHART_POINTS = 30;
let chartLabels = [];
let dataImpactA = [];
let dataDeltaV = [];
let dataDecisionD = [];
let dataThresholdT = [];

// Selected vehicle currently inspected in live HUD
let currentlyInspectedVehicleId = "KA-05-LL-2026";
let fleetVehiclesCache = [];

// Strict Role-Based Access Control Check
function checkAdminAuth() {
  const token = localStorage.getItem('lifelink_token');
  const role = localStorage.getItem('lifelink_role');
  if (!token || role !== 'admin') {
    window.location.href = '/login?denied=admin';
    return false;
  }
  return true;
}

function getAuthHeaders() {
  const token = localStorage.getItem('lifelink_token') || '';
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  };
}

// Initialize Real-time Charts
function initCharts() {
  const ctxImpact = document.getElementById('impactChart').getContext('2d');
  impactChart = new Chart(ctxImpact, {
    type: 'line',
    data: {
      labels: chartLabels,
      datasets: [
        {
          label: 'Impact Force A (g)',
          data: dataImpactA,
          borderColor: '#00e5ff',
          backgroundColor: 'rgba(0, 229, 255, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.3
        },
        {
          label: 'Speed Drop Δv (km/h)',
          data: dataDeltaV,
          borderColor: '#ffab00',
          borderWidth: 1.8,
          borderDash: [4, 4],
          fill: false,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { display: false },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#8899b5', font: { family: 'JetBrains Mono' } },
          min: 0,
          suggestedMax: 8
        }
      },
      plugins: {
        legend: { labels: { color: '#f0f4fc', font: { family: 'Outfit', size: 11 } } }
      }
    }
  });

  const ctxDecision = document.getElementById('decisionChart').getContext('2d');
  decisionChart = new Chart(ctxDecision, {
    type: 'line',
    data: {
      labels: chartLabels,
      datasets: [
        {
          label: 'Decision Score (D)',
          data: dataDecisionD,
          borderColor: '#7c4dff',
          backgroundColor: 'rgba(124, 77, 255, 0.15)',
          borderWidth: 2.2,
          fill: true,
          tension: 0.3
        },
        {
          label: 'Threshold T (0.68)',
          data: dataThresholdT,
          borderColor: '#ff1744',
          borderWidth: 1.5,
          borderDash: [5, 5],
          pointRadius: 0,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { display: false },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#8899b5', font: { family: 'JetBrains Mono' } },
          min: 0,
          max: 1.0
        }
      },
      plugins: {
        legend: { labels: { color: '#f0f4fc', font: { family: 'Outfit', size: 11 } } }
      }
    }
  });

  const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
  updateChartsTheme(currentTheme);
}

function updateChartsTheme(theme) {
  const isLight = theme === 'light';
  const gridColor = isLight ? 'rgba(211, 47, 47, 0.1)' : 'rgba(255, 255, 255, 0.05)';
  const tickColor = isLight ? '#5e4348' : '#8899b5';
  const labelColor = isLight ? '#190a0c' : '#f0f4fc';

  if (impactChart) {
    impactChart.options.scales.y.grid.color = gridColor;
    impactChart.options.scales.y.ticks.color = tickColor;
    impactChart.options.plugins.legend.labels.color = labelColor;
    impactChart.update();
  }
  if (decisionChart) {
    decisionChart.options.scales.y.grid.color = gridColor;
    decisionChart.options.scales.y.ticks.color = tickColor;
    decisionChart.options.plugins.legend.labels.color = labelColor;
    decisionChart.update();
  }
}

function resetChartData() {
  chartLabels = [];
  dataImpactA = [];
  dataDeltaV = [];
  dataDecisionD = [];
  dataThresholdT = [];
  if (impactChart) {
    impactChart.data.labels = chartLabels;
    impactChart.data.datasets[0].data = dataImpactA;
    impactChart.data.datasets[1].data = dataDeltaV;
    impactChart.update();
  }
  if (decisionChart) {
    decisionChart.data.labels = chartLabels;
    decisionChart.data.datasets[0].data = dataDecisionD;
    decisionChart.data.datasets[1].data = dataThresholdT;
    decisionChart.update();
  }
}

function pushChartData(timeStr, impactA, deltaV, decisionD, threshT) {
  chartLabels.push(timeStr);
  dataImpactA.push(impactA);
  dataDeltaV.push(deltaV);
  dataDecisionD.push(decisionD);
  dataThresholdT.push(threshT || 0.68);

  if (chartLabels.length > MAX_CHART_POINTS) {
    chartLabels.shift();
    dataImpactA.shift();
    dataDeltaV.shift();
    dataDecisionD.shift();
    dataThresholdT.shift();
  }

  if (impactChart && decisionChart) {
    impactChart.update('none');
    decisionChart.update('none');
  }
}

// Switch Inspected Vehicle
function selectInspectedVehicle(vehicleId) {
  currentlyInspectedVehicleId = vehicleId;
  resetChartData();

  // Update target selector in Drill panel to match
  const selectDrill = document.getElementById('selectTargetDrillVehicle');
  if (selectDrill) selectDrill.value = vehicleId;

  const chartTarget = document.getElementById('chartTargetLabel');
  if (chartTarget) chartTarget.innerText = vehicleId;

  // Update pill buttons active state
  document.querySelectorAll('.user-pill-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.vid === vehicleId);
  });

  // Update Driver Profile details in Telepresence header
  const matched = fleetVehiclesCache.find(v => v.vehicle_id === vehicleId);
  if (matched) {
    document.getElementById('inspectDriverName').innerText = matched.driver_name;
    document.getElementById('inspectVehicleId').innerText = `(${matched.vehicle_id})`;
    document.getElementById('inspectVehicleTag').innerText = matched.vehicle_id;
    document.getElementById('inspectCarModel').innerText = `${matched.vehicle_make_model || 'Vehicle'} • Blood: ${matched.blood_group || 'O+'} • Phone: ${matched.phone_number || 'N/A'}`;

    const obd = matched.obd_detector || {};
    document.getElementById('inspectObdName').innerText = obd.device_name || 'ELM327-Bluetooth';
    document.getElementById('inspectObdMac').innerText = obd.bluetooth_mac || '00:1D:A5:68:90:E4';
    document.getElementById('inspectObdProtocol').innerText = obd.obd_protocol || 'CAN Bus';
    document.getElementById('inspectObdBaud').innerText = obd.baud_rate || 38400;
    document.getElementById('inspectObdRate').innerText = `${obd.sample_rate_hz || 5} Hz`;
  }
}

function onTargetDrillChanged(vehicleId) {
  selectInspectedVehicle(vehicleId);
}

// WebSocket Connection to receive multi-vehicle telemetry
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/live/admin-console`;

  socket = new WebSocket(wsUrl);

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'TELEMETRY_UPDATE' || data.type === 'INITIAL_STATE') {
        const fleet = data.fleet || {};
        
        // Find telemetry for currently inspected vehicle
        const inspectedData = fleet[currentlyInspectedVehicleId] || (fleet[Object.keys(fleet)[0]]);
        if (inspectedData) {
          renderInspectedTelemetry(inspectedData.telemetry, inspectedData.analysis, inspectedData.active_alert);
          
          const nowStr = new Date().toLocaleTimeString();
          pushChartData(
            nowStr,
            inspectedData.analysis.impact_acceleration_A,
            inspectedData.analysis.speed_drop_delta_v,
            inspectedData.analysis.decision_score_D,
            inspectedData.analysis.metrics_breakdown?.thresh_T || 0.68
          );
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  socket.onclose = () => {
    setTimeout(initWebSocket, 2000);
  };
}

// Render Inspected Vehicle Telemetry in Live HUD
function renderInspectedTelemetry(telemetry, analysis, activeAlert) {
  if (!telemetry) return;

  // Speedometer
  const speed = Math.round(telemetry.speed_kmh || 0);
  document.getElementById('inspectSpeedNum').innerText = speed;
  const speedCirc = 534;
  const speedPct = Math.min(1.0, speed / 160.0);
  const speedOffset = speedCirc - (speedPct * speedCirc);
  const speedRing = document.getElementById('inspectSpeedGaugeRing');
  speedRing.style.strokeDashoffset = speedOffset;
  speedRing.style.stroke = speed > 100 ? 'var(--accent-warning)' : 'var(--accent-cyan)';

  // Engine
  document.getElementById('inspectRpmVal').innerText = Math.round(telemetry.rpm || 0);
  document.getElementById('inspectThrottleVal').innerText = `${Math.round(telemetry.throttle_pct || 0)}%`;
  document.getElementById('inspectCoolantVal').innerText = `${Math.round(telemetry.engine_temp_c || 88)}°C`;

  // Accelerometer
  const ax = telemetry.ax || 0;
  const ay = telemetry.ay || 0;
  const az = telemetry.az || 1;
  document.getElementById('inspectAxVal').innerText = `${ax > 0 ? '+' : ''}${ax.toFixed(2)}g`;
  document.getElementById('inspectAyVal').innerText = `${ay > 0 ? '+' : ''}${ay.toFixed(2)}g`;
  document.getElementById('inspectAzVal').innerText = `${az > 0 ? '+' : ''}${az.toFixed(2)}g`;

  document.getElementById('inspectAxBar').style.width = `${Math.min(100, Math.abs(ax) * 20)}%`;
  document.getElementById('inspectAyBar').style.width = `${Math.min(100, Math.abs(ay) * 20)}%`;
  document.getElementById('inspectAzBar').style.width = `${Math.min(100, Math.abs(az) * 20)}%`;

  // Impact G-Force
  const impactA = analysis ? analysis.impact_acceleration_A : Math.sqrt(ax * ax + ay * ay + az * az);
  document.getElementById('inspectImpactNum').innerText = impactA.toFixed(2);
  const gCirc = 534;
  const gPct = Math.min(1.0, impactA / 8.0);
  const gOffset = gCirc - (gPct * gCirc);
  const gRing = document.getElementById('inspectImpactGaugeRing');
  gRing.style.strokeDashoffset = gOffset;
  gRing.style.stroke = impactA > 3.0 ? 'var(--accent-danger)' : '#00e676';

  // Multi-condition metrics
  if (analysis) {
    const dv = analysis.speed_drop_delta_v;
    document.getElementById('inspectDeltaVNum').innerText = dv.toFixed(1);
    document.getElementById('inspectDeltaVBar').style.width = `${Math.min(100, (dv / 50) * 100)}%`;
    const cardDV = document.getElementById('cardInspectDeltaV');
    const tagDV = document.getElementById('inspectDeltaVStatus');
    if (dv > 20.0) {
      tagDV.innerText = "CRITICAL DROP (>20 km/h)";
      tagDV.style.color = "var(--accent-danger)";
      cardDV.classList.add("danger");
    } else {
      tagDV.innerText = "NOMINAL";
      tagDV.style.color = "var(--text-dim)";
      cardDV.classList.remove("danger");
    }

    const theta = analysis.tilt_angle_theta;
    document.getElementById('inspectTiltNum').innerText = theta.toFixed(1);
    document.getElementById('inspectTiltBar').style.width = `${Math.min(100, (theta / 90) * 100)}%`;
    const cardTilt = document.getElementById('cardInspectTilt');
    const tagTilt = document.getElementById('inspectTiltStatus');
    if (theta > 45.0) {
      tagTilt.innerText = "ROLLOVER FLIP (>45°)";
      tagTilt.style.color = "var(--accent-danger)";
      cardTilt.classList.add("danger");
    } else {
      tagTilt.innerText = "UPRIGHT (<45°)";
      tagTilt.style.color = "var(--text-dim)";
      cardTilt.classList.remove("danger");
    }

    const D = analysis.decision_score_D;
    document.getElementById('inspectDecisionDNum').innerText = D.toFixed(3);
    document.getElementById('inspectDecisionDBar').style.width = `${Math.min(100, D * 100)}%`;
    const tagD = document.getElementById('inspectDecisionDStatus');
    if (D > 0.68) {
      tagD.innerText = "CRASH THRESHOLD EXCEEDED";
      tagD.style.color = "var(--accent-danger)";
    } else {
      tagD.innerText = "NORMAL CRUISE (< 0.68)";
      tagD.style.color = "var(--accent-green)";
    }
  }

  // Safety Status Badge
  const safetyBadge = document.getElementById('inspectSafetyBadge');
  if (activeAlert && activeAlert.status === 'PENDING_CONFIRMATION') {
    safetyBadge.innerHTML = `<span class="status-dot" style="background:#ff1744;"></span> CRASH DETECTED (${Math.ceil(activeAlert.time_remaining_sec)}s COUNTDOWN)`;
    safetyBadge.style.background = 'rgba(255, 23, 68, 0.2)';
    safetyBadge.style.color = 'var(--accent-danger)';
  } else if (activeAlert && activeAlert.status === 'DISPATCHED_EMERGENCY') {
    safetyBadge.innerHTML = `<span class="status-dot" style="background:#ff1744;"></span> EMERGENCY DISPATCHED (AI CALL ACTIVE)`;
    safetyBadge.style.background = 'rgba(255, 23, 68, 0.3)';
    safetyBadge.style.color = '#ff5252';
  } else if (analysis && analysis.false_alarm_suppressed) {
    safetyBadge.innerHTML = `<span class="status-dot" style="background:#ffab00;"></span> FALSE ALARM SUPPRESSED`;
    safetyBadge.style.background = 'rgba(255, 171, 0, 0.15)';
    safetyBadge.style.color = 'var(--accent-warning)';
  } else {
    safetyBadge.innerHTML = `<span class="status-dot"></span> NORMAL MONITORING`;
    safetyBadge.style.background = 'rgba(0, 230, 118, 0.15)';
    safetyBadge.style.color = 'var(--accent-green)';
  }
}

// Load Fleet Vehicles & Build Driver Selectors
async function loadFleetVehicles() {
  try {
    const res = await fetch('/api/admin/vehicles', {
      headers: getAuthHeaders()
    });

    if (res.status === 401 || res.status === 403) {
      window.location.href = '/login?denied=admin';
      return;
    }

    const data = await res.json();
    const tbody = document.getElementById('fleetTableBody');
    const badge = document.getElementById('fleetCountBadge');
    const pillsList = document.getElementById('driverPillsList');
    const selectDrill = document.getElementById('selectTargetDrillVehicle');

    tbody.innerHTML = '';
    pillsList.innerHTML = '';
    selectDrill.innerHTML = '';

    fleetVehiclesCache = data.vehicles || [];
    if (badge) badge.innerText = `${fleetVehiclesCache.length} Vehicles Registered`;

    fleetVehiclesCache.forEach(v => {
      // 1. Add to pills
      const pill = document.createElement('button');
      pill.className = `user-pill-btn ${v.vehicle_id === currentlyInspectedVehicleId ? 'active' : ''}`;
      pill.dataset.vid = v.vehicle_id;
      pill.innerText = `${v.driver_name.split(' ')[0]} (${v.vehicle_id})`;
      pill.onclick = () => selectInspectedVehicle(v.vehicle_id);
      pillsList.appendChild(pill);

      // 2. Add to drill select
      const opt = document.createElement('option');
      opt.value = v.vehicle_id;
      opt.innerText = `${v.driver_name} - ${v.vehicle_id} (${v.vehicle_make_model || 'Vehicle'})`;
      if (v.vehicle_id === currentlyInspectedVehicleId) opt.selected = true;
      selectDrill.appendChild(opt);

      // 3. Add to table row
      let badgeClass = 'rgba(0, 230, 118, 0.15); color: var(--accent-green)';
      let statusText = 'NORMAL DRIVING';

      if (v.status === 'CRASH_ALERT') {
        badgeClass = 'rgba(255, 23, 68, 0.2); color: var(--accent-danger)';
        statusText = 'CRASH (30s COUNTDOWN)';
      } else if (v.status === 'DISPATCHED') {
        badgeClass = 'rgba(255, 23, 68, 0.3); color: #ff5252';
        statusText = 'EMERGENCY DISPATCHED';
      }

      const obd = v.obd_detector || {};

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>
          <div style="font-family: var(--font-mono); font-weight:700; color: #fff; font-size: 0.95rem;">${v.vehicle_id}</div>
          <div style="font-size: 0.82rem; color: var(--text-muted);">${v.driver_name} &bull; <span class="chip" style="padding: 1px 4px; font-size: 0.7rem;">${v.blood_group || 'O+'}</span></div>
          <div style="font-size: 0.75rem; color: var(--text-dim);">${v.vehicle_make_model || 'Car'} | ${v.phone_number || ''}</div>
        </td>
        <td>
          <div style="font-family: var(--font-mono); color: var(--accent-cyan); font-weight: 600;">${obd.device_name || 'ELM327-Bluetooth'}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">MAC: ${obd.bluetooth_mac || '00:1D:A5:--'}</div>
          <div style="font-size: 0.72rem; color: var(--text-dim);">${obd.obd_protocol || 'CAN Bus'} &bull; ${obd.baud_rate || 38400} baud</div>
          <div style="font-size: 0.72rem; color: #ffab00;">IMU: ${obd.imu_sensor_type || 'MPU-6050'}</div>
        </td>
        <td style="font-family: var(--font-mono);">
          <div style="font-weight: 700; color: #fff;">${Math.round(v.speed_kmh)} km/h</div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${v.latitude.toFixed(4)}, ${v.longitude.toFixed(4)}</div>
        </td>
        <td>
          <span class="status-badge" style="background: ${badgeClass}">
            <span class="status-dot"></span> ${statusText}
          </span>
        </td>
        <td>
          <div style="display: flex; gap: 0.4rem;">
            <button class="btn btn-outline" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="selectInspectedVehicle('${v.vehicle_id}')">
              🎯 Inspect Live
            </button>
            <button class="btn btn-primary" style="padding: 0.3rem 0.6rem; font-size: 0.75rem; background: linear-gradient(135deg, #ff1744, #d50000);" onclick="quickDrillOnUser('${v.vehicle_id}')">
              ⚡ Drill
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    // Refresh telemetry inspector header
    selectInspectedVehicle(currentlyInspectedVehicleId);
  } catch (e) {
    console.error("Error loading fleet:", e);
  }
}

// Quick drill on a specific user from table
function quickDrillOnUser(vehicleId) {
  selectInspectedVehicle(vehicleId);
  triggerTargetedDrill('HEAD_ON_COLLISION');
}

// Trigger Targeted Mock Drill (Per User)
async function triggerTargetedDrill(scenario) {
  const targetId = document.getElementById('selectTargetDrillVehicle')?.value || currentlyInspectedVehicleId;
  const targetUser = fleetVehiclesCache.find(v => v.vehicle_id === targetId)?.driver_name || targetId;

  try {
    const res = await fetch('/api/drill/trigger', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        scenario: scenario,
        vehicle_id: targetId
      })
    });

    if (res.status === 401 || res.status === 403) {
      alert("Access Denied: Admin authorization required to trigger mock drills.");
      window.location.href = '/login?denied=admin';
      return;
    }

    const result = await res.json();
    console.log("[Drill Injected]:", result);

    const analysis = result.detection_analysis;
    let summary = `Target Driver: ${targetUser} (${targetId})\nScenario: ${scenario}\n`;
    if (analysis.is_crash) {
      summary += `CRASH DETECTED (${analysis.crash_severity})!\nDecision D: ${analysis.decision_score_D} > Threshold T\nImpact: ${analysis.impact_acceleration_A}g, Speed Drop: ${analysis.speed_drop_delta_v}km/h, Tilt: ${analysis.tilt_angle_theta}°\n\nInitiated 30-Second Confirmation window ONLY on ${targetUser}'s In-Car HUD!\nOther drivers remain in normal driving condition.`;
    } else if (analysis.false_alarm_suppressed) {
      summary += `FALSE ALARM SUPPRESSED!\nReason: ${analysis.suppression_reason}\nMulti-condition validation successfully prevented erroneous dispatch on ${targetUser}'s vehicle!`;
    } else {
      summary += `Conditions evaluated as normal.`;
    }
    alert(summary);

    loadFleetVehicles();
    loadBlackBoxLogs();
  } catch (e) {
    alert("Error triggering drill: " + e.message);
  }
}

// Load Black-Box Incident Logs
async function loadBlackBoxLogs() {
  try {
    const res = await fetch('/api/blackbox/history', {
      headers: getAuthHeaders()
    });

    if (res.status === 401 || res.status === 403) return;

    const data = await res.json();
    const container = document.getElementById('blackboxLogList');
    const logs = data.incident_logs || [];

    if (logs.length === 0) {
      container.innerHTML = `
        <div style="font-size: 0.85rem; color: var(--text-muted); text-align: center; padding: 2rem 0;">
          No crashes recorded yet. Click a Mock Drill above to generate and freeze flight telemetry!
        </div>
      `;
      return;
    }

    container.innerHTML = '';
    logs.forEach(log => {
      const timeStr = new Date(log.timestamp * 1000).toLocaleTimeString();
      const meta = log.metadata?.analysis || {};
      const card = document.createElement('div');
      card.style.cssText = `
        background: rgba(18, 24, 38, 0.7);
        border: 1px solid var(--border-glass);
        border-left: 3px solid var(--accent-danger);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-size: 0.82rem;
      `;
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.35rem;">
          <span style="font-family: var(--font-mono); font-weight: 700; color: #fff;">${log.incident_id}</span>
          <span style="color: var(--text-muted); font-size: 0.75rem;">${timeStr}</span>
        </div>
        <div style="color: #ffcdd2; margin-bottom: 0.25rem;">
          <strong>Vehicle:</strong> ${log.vehicle_id} &bull; <strong>Trigger:</strong> ${log.trigger_type}
        </div>
        <div style="font-family: var(--font-mono); color: var(--accent-cyan); font-size: 0.75rem;">
          Impact: ${meta.impact_acceleration_A || 0}g | Δv: ${meta.speed_drop_delta_v || 0} km/h | Tilt: ${meta.tilt_angle_theta || 0}° | D: ${meta.decision_score_D || 0}
        </div>
        <div style="font-size: 0.72rem; color: var(--text-dim); margin-top: 0.25rem;">
          Preserved ${log.frames_count} high-frequency telemetry frames for forensic analysis.
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    console.error("Error loading blackbox logs:", e);
  }
}

// Update Calibration Sliders
function updateSliderLabels() {
  document.getElementById('valLabelW1').innerText = parseFloat(document.getElementById('sliderW1').value).toFixed(2);
  document.getElementById('valLabelW2').innerText = parseFloat(document.getElementById('sliderW2').value).toFixed(2);
  document.getElementById('valLabelW3').innerText = parseFloat(document.getElementById('sliderW3').value).toFixed(2);
  document.getElementById('valLabelT').innerText = parseFloat(document.getElementById('sliderT').value).toFixed(2);
  document.getElementById('valLabelThreshA').innerText = `${parseFloat(document.getElementById('sliderThreshA').value).toFixed(2)}g`;
  document.getElementById('valLabelThreshDV').innerText = `${document.getElementById('sliderThreshDV').value} km/h`;
}

async function saveConfig() {
  const w1 = parseFloat(document.getElementById('sliderW1').value);
  const w2 = parseFloat(document.getElementById('sliderW2').value);
  const w3 = parseFloat(document.getElementById('sliderW3').value);
  const thresh_T = parseFloat(document.getElementById('sliderT').value);
  const thresh_a = parseFloat(document.getElementById('sliderThreshA').value);
  const thresh_dv = parseFloat(document.getElementById('sliderThreshDV').value);

  try {
    const res = await fetch('/api/admin/config', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ w1, w2, w3, thresh_T, thresh_a, thresh_dv })
    });
    if (res.status === 401 || res.status === 403) {
      alert("Access Denied: Admin authorization required to update model config.");
      return;
    }
    const data = await res.json();
    alert("Model weights and decision thresholds updated successfully!\n" + JSON.stringify(data.config, null, 2));
  } catch (e) {
    alert("Error updating config: " + e.message);
  }
}

async function logoutAdmin() {
  const token = localStorage.getItem('lifelink_token');
  try {
    if (token) {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: getAuthHeaders()
      });
    }
  } catch (e) {}
  localStorage.clear();
  window.location.href = '/login';
}

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  if (!checkAdminAuth()) return;

  initCharts();
  initWebSocket();
  loadFleetVehicles();
  loadBlackBoxLogs();

  // Poll fleet table every 5s
  setInterval(loadFleetVehicles, 5000);
});
