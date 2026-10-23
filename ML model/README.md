# LifeLink: Multi-Parameter Crash Detection with Adaptive False Alarm Suppression

LifeLink is an intelligent, strictly **post-accident detection and autonomous emergency response system** designed based on the research paper by *Diana George, Benaka Santhosha S, Shreyas R, Tejovarshini, Thejaswini M, and Sujay Kumar S (Department of CSE, Dayananda Sagar University, Bangalore)*.

The system continuously ingests live data from an **in-vehicle OBD-II detector and 3-axis IMU Bluetooth module**, employs **multi-condition validation** to filter out benign false positives (such as severe potholes, road bumps, and emergency hard braking), and manages a **timed 30-second driver safety confirmation protocol** with autonomous **AI Voice emergency dispatch calling**, **proximity alerts**, and **offline SMS cellular fallback**.

---

## 🔬 Mathematical Decision Model & Theoretical Formulation

LifeLink operates **strictly post-accident** (evaluating whether a crash has actually taken place, eliminating pre-crash prediction false alarms). It combines multiple sensor streams into a single weighted decision score:

### 1. Total Impact Force Magnitude ($A$)
Calculated from 3-axis accelerometer readings:
$$A = \sqrt{a_x^2 + a_y^2 + a_z^2}$$
* **Threshold**: $A > 3.0\text{g}$ (Paper Table 1). Sharp acceleration spikes indicate an impact.

### 2. Sudden Speed Variation ($\Delta v$)
Calculated from instantaneous OBD-II vehicle speed differential:
$$\Delta v = v_{t-1} - v_t$$
* **Threshold**: $\Delta v > 20.0\text{ km/h}$ sudden deceleration drop within a rolling collision window.

### 3. Abnormal Vehicle Tilt / Rollover Angle ($\theta$)
Calculated from orientation/gyroscope angular axes:
$$\theta = \tan^{-1}\left(\frac{y}{x}\right)$$
* **Threshold**: $\theta > 45.0^\circ$ (Paper Table 1). Identifies rollover, side ditch roll, or overturned vehicle orientation.

### 4. Weighted Multi-Parameter Decision Score ($D$)
$$D = w_1 A_{\text{norm}} + w_2 \Delta v_{\text{norm}} + w_3 \theta_{\text{norm}}$$
* **Weights** (Paper Table 2):
  * $w_1 = 0.4$ (Impact Acceleration — High importance)
  * $w_2 = 0.3$ (Speed Change $\Delta v$ — Medium importance)
  * $w_3 = 0.3$ (Tilt Angle $\theta$ — Medium importance)

### 5. Multi-Condition Validation Decision Rule
$$\text{crash} = \begin{cases} 1 & \text{if } D > T \\ 0 & \text{otherwise} \end{cases}$$
Where $T = 0.68$ is the critical decision threshold.
* **Adaptive False Alarm Suppression**: A single isolated parameter spike (e.g., hitting a pothole with $A > 3\text{g}$ while speed is maintained and tilt is $0^\circ$; or hard emergency braking with $\Delta v > 20\text{ km/h}$ while impact is nominal $1.2\text{g}$) is **automatically filtered out**, lowering the false positive rate from **18% down to ~4%** and raising detection accuracy to **96%**.

---

## 🔒 Multi-User Role-Based Access Control (RBAC) & Dedicated Login

LifeLink includes a secure authentication and driver onboarding system ([login.html](file:///c:/Users/mthej/OneDrive/Desktop/ML%20model/frontend/login.html)):
* **Driver Account**:
  * Default Credentials: `driver` / `user123`
  * Role: `user`
  * **Strict Admin Isolation**: Regular users **cannot access the Admin Portal** or execute mock drills. If a user attempts to visit `/admin` or invoke `/api/admin/*` / `/api/drill/trigger`, they are blocked with `403 Forbidden` and redirected to login.
* **Fleet Administrator Account**:
  * Default Credentials: `admin` / `admin123`
  * Role: `admin`
  * Full access to Fleet Telemetry, Driver Profiles, iOBD hardware inspections, Mock Drill Studio, and Model Weight Tuning.

---

## 🚗 In-Depth iOBD Detector & Sensor Input Specifications

When an individual signs up or configures their car in the Driver HUD, LifeLink asks for and records full vehicle and hardware telemetry parameters:
1. **Driver Personal Details**: Full Name, Phone Number, Email, Blood Group (for emergency medical dispatch).
2. **Vehicle Identification**: Vehicle Registration Number (e.g. `KA-05-LL-2026`), Make & Model.
3. **Emergency Contacts**: Primary and Secondary Contact Names and Phone Numbers (used by the autonomous AI voice caller and GSM SMS fallback).
4. **iOBD Detector Hardware Parameters**:
   * **OBD-II Device Model**: e.g., `ELM327 Bluetooth v2.1`, `VGate iCar Pro Bluetooth 4.0 BLE`, `Custom ESP32 OBD-II`.
   * **Bluetooth MAC / Device UUID**: e.g., `00:1D:A5:68:90:E4` for pairing directly via Web Bluetooth or Windows Serial COM ports.
   * **OBD Bus Protocol**: `ISO 15765-4 CAN (11 bit, 500 kbaud)`, `ISO 15765-4 CAN (29 bit)`, `ISO 9141-2`, `Automatic (ATSP0)`.
   * **Serial Baud Rate**: `38400 baud`, `9600 baud`, `115200 baud`.
   * **IMU Sensor Type**: `MPU-6050 6-Axis (±8g, ±500°/s)`, `ADXL345 (±16g)`, `Smartphone Embedded Gyro & Accelerometer`.
   * **Sampling Frequency**: 5 Hz (200 ms interval) or 10 Hz (100 ms interval).

---

## 🛠️ System Architecture & File Structure

```
c:\Users\mthej\OneDrive\Desktop\ML model\
├── backend/
│   ├── config.py             # Paper weights (w1=0.4, w2=0.3, w3=0.3), thresholds, timer settings
│   ├── model.py              # LifeLinkCrashDetector engine implementing Equations 1-5 & suppression logic
│   ├── emergency_manager.py  # 30-sec confirmation timer, AI voice caller, proximity alerts, SMS fallback
│   ├── blackbox.py           # Pre-incident & post-incident telemetry flight recorder
│   ├── bluetooth_manager.py  # Windows COM serial reader, Web Bluetooth relay, and telemetry synthesizer
│   ├── server.py             # FastAPI backend with REST endpoints, WebSockets, and static file serving
│   └── test_model.py         # Automated unit test suite verifying benchmarks from research paper
├── frontend/
│   ├── index.html            # System Gateway & Research Performance Overview
│   ├── user.html             # Driver Portal: Live OBD-II HUD, G-force meters, 30s confirmation modal, AI voice caller
│   ├── admin.html            # Admin Portal: Fleet overview, Mock Drill Studio, Chart.js live plots, model calibrator
│   ├── css/
│   │   └── style.css         # High-end automotive dark-mode glassmorphic design system
│   └── js/
│       ├── user.js           # Driver HUD WebSocket client, Web Audio siren, Web Speech AI voice, Bluetooth pairing
│       └── admin.js          # Admin Studio client, mock drill triggers, Chart.js telemetry graphs, weight tuning
├── sample_data/
│   └── simulated_crashes.json# Benchmark scenarios from the paper (Normal, Pothole, Hard Braking, Rollover, Head-On)
├── requirements.txt          # Python dependencies (fastapi, uvicorn, pydantic, pyserial, websockets)
├── run.py                    # Server launch script
└── README.md
```

---

## 🚀 Running the System

### 1. Installation
Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Start the Server
Launch the FastAPI server:
```bash
python run.py
```
Or directly using Uvicorn:
```bash
uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Web Interfaces
Open your browser to:
* **System Gateway**: [http://localhost:8000/](http://localhost:8000/)
* **Driver In-Car HUD**: [http://localhost:8000/user](http://localhost:8000/user)
* **Admin Fleet & Mock Drill Studio**: [http://localhost:8000/admin](http://localhost:8000/admin)
* **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Testing Multi-User Live Telepresence & Targeted Mock Drills

1. **Open Driver A (Alex Morgan) HUD**:
   - Open [http://localhost:8000/login](http://localhost:8000/login) in Window 1 and log in as `driver` / `user123`.
   - Driver A HUD shows vehicle `KA-05-LL-2026` cruising at ~70 km/h.
2. **Open Admin Studio**:
   - Open [http://localhost:8000/login](http://localhost:8000/login) in Window 2 and log in as `admin` / `admin123`.
3. **Inspect Live Data for Each User Directly in Admin Portal**:
   - Click the driver switcher chips in the Telepresence header: `[Alex (KA-05-LL-2026)]` or `[Priya (KA-01-MJ-9988)]`.
   - The Admin Portal's live gauges (speedometer, RPM, 3-axis accelerometer vector $a_x, a_y, a_z$, impact force $A$, tilt $\theta$, and Chart.js graphs) instantly stream the live telemetry of that selected user!
4. **Trigger a Targeted Mock Drill on a Specific Driver**:
   - In the Admin Mock Drill Studio, select **"Target Driver: Priya Sharma (KA-01-MJ-9988)"**.
   - Click **"Drill: Severe Head-On Collision"**.
   - **Observe User Isolation**:
     - Priya's car experiences the crash ($A = 6.2g$, speed drops to $0$).
     - Alex Morgan's car (`KA-05-LL-2026`) in Window 1 **remains completely unaffected**, continuing normal driving cruise at 70 km/h with zero false sirens!
     - Only the targeted user's HUD triggers the 30-second confirmation countdown and emergency dispatch.
5. **Driver Cancels Alert**:
   - The targeted driver clicks **"I AM SAFE / FALSE ALARM (CANCEL CALL)"**.
   - Emergency dispatch is aborted, the siren silences, and the event is recorded in the Black-Box archives.

---

## 📡 Connecting Physical Bluetooth OBD-II Hardware

LifeLink supports two methods for reading real OBD-II car modules:
1. **Web Bluetooth API / Web Serial**: In Chrome or Edge, click **"Pair Bluetooth OBD"** on the Driver HUD to connect directly to standard Bluetooth ELM327 dongles or ESP32/HC-05 sensor boards.
2. **Windows Virtual Serial COM Port**: If your Bluetooth OBD scanner is paired in Windows Bluetooth settings under a COM port (e.g., `COM3`, `COM4`), click **"Serial COM Ports"** on the Driver HUD to stream real OBD-II telemetry directly into the backend.
