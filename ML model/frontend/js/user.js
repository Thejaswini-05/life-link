/**
 * LifeLink Driver In-Car HUD & Crash Confirmation Logic
 * Handles real-time WebSocket telemetry, gauges, Web Bluetooth pairing,
 * 30-second crash confirmation modal, and autonomous AI voice emergency calling.
 */

let socket = null;
let currentVehicleId = "KA-05-LL-2026";
let audioContext = null;
let sirenOscillator = null;
let sirenGain = null;
let isSirenPlaying = false;
let speechUtterance = null;
let lastAlertId = null;

// Audio Siren Synthesizer using Web Audio API
function startSiren() {
  if (isSirenPlaying) return;
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    audioContext = new AudioContext();
    
    sirenOscillator = audioContext.createOscillator();
    sirenGain = audioContext.createGain();

    sirenOscillator.type = 'sawtooth';
    sirenOscillator.frequency.setValueAtTime(450, audioContext.currentTime);

    // Siren frequency sweep up and down
    const now = audioContext.currentTime;
    for (let i = 0; i < 30; i++) {
      sirenOscillator.frequency.linearRampToValueAtTime(880, now + (i * 0.8) + 0.4);
      sirenOscillator.frequency.linearRampToValueAtTime(450, now + (i * 0.8) + 0.8);
    }

    sirenGain.gain.setValueAtTime(0.15, audioContext.currentTime);
    sirenOscillator.connect(sirenGain);
    sirenGain.connect(audioContext.destination);
    
    sirenOscillator.start();
    isSirenPlaying = true;
  } catch (e) {
    console.warn("Web Audio autoplay prevented or unavailable:", e);
  }
}

function stopSiren() {
  if (!isSirenPlaying) return;
  try {
    if (sirenOscillator) {
      sirenOscillator.stop();
      sirenOscillator.disconnect();
    }
    if (audioContext && audioContext.state !== 'closed') {
      audioContext.close();
    }
  } catch (e) {
    console.warn("Error stopping siren:", e);
  }
  isSirenPlaying = false;
}

// Autonomous AI Voice Call Generator using Web Speech Synthesis API
function speakAIVoice(scriptText) {
  if (!('speechSynthesis' in window)) {
    console.warn("Speech synthesis not supported in this browser.");
    return;
  }

  // Cancel any prior speech
  window.speechSynthesis.cancel();

  speechUtterance = new SpeechSynthesisUtterance(scriptText);
  speechUtterance.rate = 0.95; // Clear emergency cadence
  speechUtterance.pitch = 1.05; // Urgent AI tone
  speechUtterance.volume = 1.0;

  // Pick suitable English voice if available
  const voices = window.speechSynthesis.getVoices();
  const alertVoice = voices.find(v => v.lang.includes('en') && (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Zira') || v.name.includes('Samantha')));
  if (alertVoice) {
    speechUtterance.voice = alertVoice;
  }

  const box = document.getElementById('aiVoiceBox');
  if (box) box.classList.add('speaking');

  speechUtterance.onend = () => {
    if (box) box.classList.remove('speaking');
  };

  window.speechSynthesis.speak(speechUtterance);
}

// WebSocket Connection
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/live/driver-hud`;

  socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    console.log("[WebSocket] Connected to LifeLink real-time telemetry stream.");
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'TELEMETRY_UPDATE' || data.type === 'INITIAL_STATE') {
        let myData = null;
        if (data.fleet && data.fleet[currentVehicleId]) {
          myData = data.fleet[currentVehicleId];
        } else if (data.telemetry && (data.telemetry.vehicle_id === currentVehicleId || !data.fleet)) {
          myData = { telemetry: data.telemetry, analysis: data.analysis, active_alert: data.active_alert };
        } else if (data.fleet) {
          // If logged in vehicle not yet in fleet map, fallback to first
          myData = data.fleet[Object.keys(data.fleet)[0]];
        }
        
        if (myData) {
          renderTelemetry(myData.telemetry, myData.analysis, myData.active_alert);
        }
      } else if (data.type === 'ALERT_CANCELLED') {
        if (!data.vehicle_id || data.vehicle_id === currentVehicleId) {
          handleAlertCancelled(data);
        }
      }
    } catch (e) {
      console.error("Error parsing WS frame:", e);
    }
  };

  socket.onclose = () => {
    console.log("[WebSocket] Disconnected. Reconnecting in 2s...");
    setTimeout(initWebSocket, 2000);
  };
}

// Render Telemetry & Decision Engine HUD
function renderTelemetry(telemetry, analysis, activeAlert) {
  if (!telemetry) return;

  const vehicleId = telemetry.vehicle_id || currentVehicleId;
  const driverName = telemetry.driver_name || "Driver";
  document.getElementById('vehicleIdLabel').innerText = `${vehicleId} (${driverName})`;

  // 1. Speedometer Gauge (0 to 180 km/h)
  const speed = Math.round(telemetry.speed_kmh || 0);
  document.getElementById('speedDisplayNum').innerText = speed;
  const speedCircumference = 534; // 2 * PI * 85
  const speedPct = Math.min(1.0, speed / 160.0);
  const speedOffset = speedCircumference - (speedPct * speedCircumference);
  const speedGauge = document.getElementById('speedGaugeRing');
  speedGauge.style.strokeDashoffset = speedOffset;
  if (speed > 100) {
    speedGauge.style.stroke = 'var(--accent-warning)';
  } else {
    speedGauge.style.stroke = 'var(--accent-cyan)';
  }

  // Engine metrics
  document.getElementById('rpmDisplayVal').innerText = Math.round(telemetry.rpm || 0);
  document.getElementById('throttleDisplayVal').innerText = `${Math.round(telemetry.throttle_pct || 0)}%`;
  document.getElementById('coolantDisplayVal').innerText = `${Math.round(telemetry.engine_temp_c || 88)}°C`;

  // GPS Coordinates
  if (telemetry.latitude && telemetry.longitude) {
    document.getElementById('gpsCoordsText').innerText = `${telemetry.latitude.toFixed(4)}° N, ${telemetry.longitude.toFixed(4)}° E`;
  }

  // 2. Accelerometer 3-Axis & Magnitude A (Equation 1)
  const ax = telemetry.ax || 0;
  const ay = telemetry.ay || 0;
  const az = telemetry.az || 1;
  document.getElementById('axVal').innerText = `${ax > 0 ? '+' : ''}${ax.toFixed(2)}g`;
  document.getElementById('ayVal').innerText = `${ay > 0 ? '+' : ''}${ay.toFixed(2)}g`;
  document.getElementById('azVal').innerText = `${az > 0 ? '+' : ''}${az.toFixed(2)}g`;

  document.getElementById('axBar').style.width = `${Math.min(100, Math.abs(ax) * 20)}%`;
  document.getElementById('ayBar').style.width = `${Math.min(100, Math.abs(ay) * 20)}%`;
  document.getElementById('azBar').style.width = `${Math.min(100, Math.abs(az) * 20)}%`;

  const impactA = analysis ? analysis.impact_acceleration_A : Math.sqrt(ax * ax + ay * ay + az * az);
  document.getElementById('gForceDisplayNum').innerText = impactA.toFixed(2);
  const gCircumference = 534;
  const gPct = Math.min(1.0, impactA / 8.0);
  const gOffset = gCircumference - (gPct * gCircumference);
  const gGauge = document.getElementById('gForceGaugeRing');
  gGauge.style.strokeDashoffset = gOffset;
  if (impactA > 3.0) {
    gGauge.style.stroke = 'var(--accent-danger)';
  } else {
    gGauge.style.stroke = 'var(--accent-green)';
  }

  // 3. Multi-Condition Parameters
  if (analysis) {
    // Delta v
    const dv = analysis.speed_drop_delta_v;
    document.getElementById('valDeltaV').innerText = dv.toFixed(1);
    document.getElementById('barDeltaV').style.width = `${Math.min(100, (dv / 50) * 100)}%`;
    const tagDV = document.getElementById('tagDeltaVStatus');
    const cardDV = document.getElementById('cardSpeedDrop');
    if (dv > 20.0) {
      tagDV.innerText = "CRITICAL BRAKE/DROP (>20 km/h)";
      tagDV.style.color = "var(--accent-danger)";
      cardDV.classList.add("danger");
    } else {
      tagDV.innerText = "NOMINAL";
      tagDV.style.color = "var(--text-dim)";
      cardDV.classList.remove("danger");
    }

    // Tilt theta
    const theta = analysis.tilt_angle_theta;
    document.getElementById('valTilt').innerText = theta.toFixed(1);
    document.getElementById('barTilt').style.width = `${Math.min(100, (theta / 90) * 100)}%`;
    const tagTilt = document.getElementById('tagTiltStatus');
    const cardTilt = document.getElementById('cardTilt');
    if (theta > 45.0) {
      tagTilt.innerText = "ROLLOVER DETECTED (>45°)";
      tagTilt.style.color = "var(--accent-danger)";
      cardTilt.classList.add("danger");
    } else {
      tagTilt.innerText = "UPRIGHT (<45°)";
      tagTilt.style.color = "var(--text-dim)";
      cardTilt.classList.remove("danger");
    }

    // Decision D
    const D = analysis.decision_score_D;
    document.getElementById('valDecisionD').innerText = D.toFixed(3);
    document.getElementById('barDecisionD').style.width = `${Math.min(100, D * 100)}%`;
    const tagD = document.getElementById('tagDecisionStatus');
    if (D > 0.68) {
      tagD.innerText = "CRITICAL THRESHOLD HIT";
      tagD.style.color = "var(--accent-danger)";
    } else {
      tagD.innerText = "SAFE (< 0.68)";
      tagD.style.color = "var(--accent-green)";
    }

    // Crash State & False Alarm Suppression
    const crashStateEl = document.getElementById('valCrashState');
    const crashBarEl = document.getElementById('barCrashState');
    const suppressionEl = document.getElementById('valSuppressionReason');

    if (analysis.is_crash) {
      crashStateEl.innerText = `${analysis.crash_severity.replace('_', ' ')}`;
      crashStateEl.style.color = 'var(--accent-danger)';
      crashBarEl.style.background = 'var(--accent-danger)';
      suppressionEl.innerText = `Multi-condition confirmed: A=${impactA.toFixed(1)}g, Δv=${dv.toFixed(1)}km/h, θ=${theta.toFixed(1)}°`;
      suppressionEl.style.color = '#ff8a80';
    } else if (analysis.false_alarm_suppressed) {
      crashStateEl.innerText = "ALARM SUPPRESSED";
      crashStateEl.style.color = 'var(--accent-warning)';
      crashBarEl.style.background = 'var(--accent-warning)';
      suppressionEl.innerText = analysis.suppression_reason || "Single trigger filtered (pothole/braking)";
      suppressionEl.style.color = 'var(--accent-warning)';
    } else {
      crashStateEl.innerText = "SAFE CRUISE";
      crashStateEl.style.color = 'var(--accent-green)';
      crashBarEl.style.background = 'var(--accent-green)';
      suppressionEl.innerText = "All conditions within nominal boundaries";
      suppressionEl.style.color = 'var(--text-dim)';
    }
  }

  // 4. Handle Active Emergency Alerts & 30-Second Countdown
  handleEmergencyState(activeAlert);
}

// 30-Second Confirmation & Emergency Management
function handleEmergencyState(activeAlert) {
  const modal = document.getElementById('crashModalOverlay');
  const dispatchBanner = document.getElementById('dispatchedEmergencyBanner');
  const driverBadge = document.getElementById('driverStatusBadge');

  if (activeAlert && activeAlert.status === 'PENDING_CONFIRMATION') {
    // 30-second countdown in progress!
    modal.style.display = 'flex';
    dispatchBanner.style.display = 'none';

    driverBadge.innerHTML = `<span class="status-dot" style="background:#ff1744;"></span> CRASH DETECTED (30s TIMER)`;
    driverBadge.style.color = 'var(--accent-danger)';
    driverBadge.style.background = 'rgba(255,23,68,0.15)';
    driverBadge.style.borderColor = 'rgba(255,23,68,0.4)';

    startSiren();

    // Update countdown circle & number
    const rem = Math.max(0, Math.ceil(activeAlert.time_remaining_sec));
    document.getElementById('countdownNumber').innerText = rem;

    // Circle circumference = 2 * PI * 55 = 345.5
    const circle = document.getElementById('countdownCircle');
    const totalCirc = 345.5;
    const progressOffset = totalCirc - ((rem / 30.0) * totalCirc);
    circle.style.strokeDashoffset = progressOffset;

  } else if (activeAlert && activeAlert.status === 'DISPATCHED_EMERGENCY') {
    // Timer expired without user response!
    modal.style.display = 'none';
    stopSiren();
    dispatchBanner.style.display = 'block';

    driverBadge.innerHTML = `<span class="status-dot" style="background:#ff1744;"></span> AI CALL DISPATCHED`;
    driverBadge.style.color = 'var(--accent-danger)';

    // Play AI voice emergency call if this is a newly dispatched alert
    if (lastAlertId !== activeAlert.alert_id) {
      lastAlertId = activeAlert.alert_id;
      document.getElementById('aiVoiceTranscript').innerText = activeAlert.ai_voice_script;
      speakAIVoice(activeAlert.ai_voice_script);
    }

  } else {
    // Safe or no active alert
    modal.style.display = 'none';
    dispatchBanner.style.display = 'none';
    stopSiren();

    driverBadge.innerHTML = `<span class="status-dot"></span> NORMAL MONITORING`;
    driverBadge.style.color = 'var(--accent-green)';
    driverBadge.style.background = 'rgba(0,230,118,0.12)';
    driverBadge.style.borderColor = 'rgba(0,230,118,0.3)';
  }
}

// User clicks "I AM SAFE / FALSE ALARM (CANCEL CALL)"
async function onUserConfirmSafe() {
  try {
    const res = await fetch('/api/emergency/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        vehicle_id: currentVehicleId,
        user_status: "SAFE"
      })
    });
    const result = await res.json();
    console.log("[Confirmation]:", result);

    stopSiren();
    if (speechUtterance && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    document.getElementById('crashModalOverlay').style.display = 'none';
    alert("Emergency alert cancelled. You have confirmed you are safe. Automatic emergency calling is aborted.");
  } catch (e) {
    console.error("Error cancelling alert:", e);
  }
}

function handleAlertCancelled(data) {
  stopSiren();
  document.getElementById('crashModalOverlay').style.display = 'none';
  document.getElementById('dispatchedEmergencyBanner').style.display = 'none';
}

// Web Bluetooth API Integration (Connect physical ELM327 / HC-05 / ESP32 OBD dongle)
async function pairWebBluetooth() {
  if (!navigator.bluetooth) {
    // Fallback prompt for browsers without Web Bluetooth
    const com = prompt("Web Bluetooth is supported in Chrome/Edge. Or enter Windows Virtual COM port (e.g. COM3):", "COM3");
    if (com) {
      connectSerialPort(com);
    }
    return;
  }

  try {
    const device = await navigator.bluetooth.requestDevice({
      acceptAllDevices: true,
      optionalServices: ['generic_access', '0000fff0-0000-1000-8000-00805f9b34fb']
    });

    console.log("[Web Bluetooth] Connected to:", device.name);
    document.getElementById('btStatusText').innerText = `PAIRED: ${device.name || "OBD-II Dongle"}`;
    document.getElementById('bluetoothPill').className = "connection-pill pill-connected";
    alert(`Successfully paired with Bluetooth OBD Device: ${device.name || "OBD-II Device"}`);
  } catch (err) {
    console.warn("Bluetooth pair cancelled:", err);
  }
}

// Windows Serial / COM Port connector
async function connectSerialPort(portName) {
  try {
    const res = await fetch('/api/bluetooth/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ port: portName, baudrate: 9600 })
    });
    const data = await res.json();
    if (data.status === 'SUCCESS') {
      document.getElementById('btStatusText').innerText = `SERIAL COM: ${portName}`;
      alert(data.message);
    } else {
      alert(`Serial connection message: ${data.message}`);
    }
  } catch (e) {
    alert("Failed to connect to COM port: " + e.message);
  }
}

async function showComPortsModal() {
  try {
    const res = await fetch('/api/bluetooth/ports');
    const data = await res.json();
    const ports = data.ports || [];
    let msg = "Available Serial / Bluetooth COM Ports on System:\n";
    if (ports.length === 0) {
      msg += "No physical COM ports found. Using High-Fidelity Simulator.\n";
    } else {
      ports.forEach(p => {
        msg += `- ${p.port}: ${p.description}\n`;
      });
    }
    const chosen = prompt(msg + "\nEnter COM port to connect (e.g., COM3, COM4):", ports[0]?.port || "COM3");
    if (chosen) {
      connectSerialPort(chosen);
    }
  } catch (e) {
    console.error(e);
  }
}

// Authentication & Profile Setup
function checkAuthAndLoadProfile() {
  const token = localStorage.getItem('lifelink_token');
  if (!token) {
    window.location.href = '/login';
    return;
  }

  const userJson = localStorage.getItem('lifelink_user');
  if (userJson) {
    try {
      const u = JSON.parse(userJson);
      currentVehicleId = u.vehicle_id || "KA-05-LL-2026";
      
      const bName = document.getElementById('bannerDriverName');
      if (bName) bName.innerText = u.full_name || u.username;

      const bVeh = document.getElementById('bannerVehicleInfo');
      if (bVeh) bVeh.innerText = `${u.vehicle_id} (${u.vehicle_make_model || "Car"})`;

      const bEm = document.getElementById('bannerEmergencyContact');
      if (bEm) bEm.innerText = u.emergency_contact_1 || u.emergency_contact_1_phone || "911 / 112";

      if (u.obd_detector) {
        const bObd = document.getElementById('bannerObdName');
        if (bObd) bObd.innerText = u.obd_detector.device_name;

        const bMac = document.getElementById('bannerObdMac');
        if (bMac) bMac.innerText = u.obd_detector.bluetooth_mac;

        // Prefill modal fields
        if (document.getElementById('modalObdName')) document.getElementById('modalObdName').value = u.obd_detector.device_name;
        if (document.getElementById('modalObdMac')) document.getElementById('modalObdMac').value = u.obd_detector.bluetooth_mac;
        if (document.getElementById('modalObdProtocol')) document.getElementById('modalObdProtocol').value = u.obd_detector.obd_protocol;
        if (document.getElementById('modalObdBaud')) document.getElementById('modalObdBaud').value = u.obd_detector.baud_rate;
        if (document.getElementById('modalObdImu')) document.getElementById('modalObdImu').value = u.obd_detector.imu_sensor_type;
        if (document.getElementById('modalObdRate')) document.getElementById('modalObdRate').value = u.obd_detector.sample_rate_hz;
      }
    } catch (e) {
      console.warn("Error loading stored profile:", e);
    }
  }
}

// iOBD Modal Controls
function openObdModal() {
  document.getElementById('obdModalOverlay').style.display = 'flex';
}

function closeObdModal() {
  document.getElementById('obdModalOverlay').style.display = 'none';
}

async function handleUpdateObd(e) {
  e.preventDefault();
  const token = localStorage.getItem('lifelink_token');
  const payload = {
    device_name: document.getElementById('modalObdName').value,
    bluetooth_mac: document.getElementById('modalObdMac').value,
    obd_protocol: document.getElementById('modalObdProtocol').value,
    baud_rate: parseInt(document.getElementById('modalObdBaud').value),
    imu_sensor_type: document.getElementById('modalObdImu').value,
    sample_rate_hz: parseInt(document.getElementById('modalObdRate').value)
  };

  try {
    const res = await fetch('/api/auth/obd-config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      alert("iOBD Detector specifications updated successfully!");
      document.getElementById('bannerObdName').innerText = payload.device_name;
      document.getElementById('bannerObdMac').innerText = payload.bluetooth_mac;
      closeObdModal();
    } else {
      alert("Failed to update: " + (data.detail || "Error"));
    }
  } catch (err) {
    alert("Error updating iOBD config: " + err.message);
  }
}

async function logoutUser() {
  const token = localStorage.getItem('lifelink_token');
  try {
    if (token) {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
    }
  } catch (e) {}
  localStorage.clear();
  window.location.href = '/login';
}

// Wire Event Listeners on DOM Load
document.addEventListener('DOMContentLoaded', () => {
  checkAuthAndLoadProfile();
  initWebSocket();

  // "I AM SAFE" button in 30-sec modal
  document.getElementById('btnUserSafe').addEventListener('click', onUserConfirmSafe);

  // Bluetooth pair button
  document.getElementById('btnPairBluetooth').addEventListener('click', pairWebBluetooth);

  // Serial COM port button
  document.getElementById('btnComPorts').addEventListener('click', showComPortsModal);

  // Open iOBD Config Modal
  const btnOpenObd = document.getElementById('btnOpenObdConfig');
  if (btnOpenObd) btnOpenObd.addEventListener('click', openObdModal);

  // Replay voice button
  document.getElementById('btnReplayVoice').addEventListener('click', () => {
    const transcript = document.getElementById('aiVoiceTranscript').innerText;
    speakAIVoice(transcript);
  });
});
