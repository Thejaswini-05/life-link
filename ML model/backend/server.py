"""
LifeLink FastAPI Backend Server
Integrates Multi-Parameter Decision Engine, Bluetooth & OBD-II streaming,
30-Second User Confirmation Protocol, Role-Based Access Control, and Admin Mock Drill Studio.
"""

import os
import time
import json
import asyncio
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from backend.config import CONFIG
from backend.model import detector, TelemetryFrame, CrashAnalysisResult
from backend.emergency_manager import emergency_manager, EmergencyAlertState
from backend.blackbox import black_box
from backend.bluetooth_manager import bluetooth_obd
from backend.auth import auth_manager, UserProfile, OBDDetectorConfig

# Active connected web client sockets
connected_websockets: List[WebSocket] = []

async def broadcast_ws(payload: Dict[str, Any]):
    """Broadcast real-time telemetry or alert to all connected UI clients."""
    disconnected = []
    for ws in connected_websockets:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in connected_websockets:
            connected_websockets.remove(ws)

def on_live_telemetry_frame(frame_data: Dict[str, Any]):
    """
    Called whenever a new live frame is received from Bluetooth, OBD-II, or simulator.
    Processes frame through the LifeLink Crash Detector strictly post-accident!
    """
    try:
        frame = TelemetryFrame(**frame_data)
        analysis: CrashAnalysisResult = detector.evaluate_frame(frame)
        analysis_dict = analysis.model_dump()
        
        # Log to rolling black box
        black_box.record_frame(frame_data, analysis_dict)
        
        # Check if crash detected
        active_alert = emergency_manager.get_vehicle_alert(frame.vehicle_id)
        
        if analysis.is_crash and not active_alert:
            # Trigger the mandatory 30-second user confirmation countdown!
            alert = emergency_manager.trigger_crash_alert(
                vehicle_id=frame.vehicle_id,
                crash_result=analysis_dict,
                location={"latitude": frame.latitude, "longitude": frame.longitude},
                driver_name=bluetooth_obd.current_state.get("driver_name", "Alex Morgan")
            )
            # Freeze blackbox telemetry log for forensic post-mortem
            black_box.freeze_incident_log(
                vehicle_id=frame.vehicle_id,
                trigger_type="CONFIRMED_CRASH_DETECTED",
                metadata={"analysis": analysis_dict, "alert_id": alert.alert_id}
            )
            
        elif analysis.false_alarm_suppressed:
            # Log false alarm suppression event for admin analysis
            pass

    except Exception as e:
        print(f"[Telemetry Error]: {e}")

# Wire Bluetooth manager callback
bluetooth_obd.on_frame_callback = on_live_telemetry_frame

# Background task for checking 30-second emergency timeouts & broadcasting live fleet updates
async def background_monitoring_loop():
    while True:
        try:
            # 1. Check countdown timeouts across all active vehicles
            dispatched = emergency_manager.check_timeouts()
            for disp in dispatched:
                print(f"[EMERGENCY DISPATCHED] Vehicle {disp.vehicle_id} - AI Voice Call initiated!")
            
            # 2. Compile live telemetry & analysis for all active vehicles concurrently
            fleet_payload = {}
            for v_id, v_state in list(bluetooth_obd.vehicle_states.items()):
                frame = TelemetryFrame(**v_state)
                analysis = detector.evaluate_frame(frame).model_dump()
                alert = emergency_manager.get_vehicle_alert(v_id)
                fleet_payload[v_id] = {
                    "telemetry": v_state,
                    "analysis": analysis,
                    "active_alert": alert.model_dump() if alert else None
                }

            primary_id = "KA-05-LL-2026"
            primary_data = fleet_payload.get(primary_id, list(fleet_payload.values())[0] if fleet_payload else None)

            payload = {
                "type": "TELEMETRY_UPDATE",
                "timestamp": time.time(),
                "fleet": fleet_payload,
                "telemetry": primary_data["telemetry"] if primary_data else {},
                "analysis": primary_data["analysis"] if primary_data else {},
                "active_alert": primary_data["active_alert"] if primary_data else None,
                "connection": {
                    "mode": bluetooth_obd.connection_mode,
                    "connected": bluetooth_obd.is_connected
                }
            }
            await broadcast_ws(payload)
        except Exception as e:
            pass
        
        await asyncio.sleep(0.25)  # 4 Hz UI updates

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start simulated live stream by default so user can immediately see live telemetry
    bluetooth_obd.start_simulated_stream("KA-05-LL-2026", "NORMAL_DRIVING")
    monitor_task = asyncio.create_task(background_monitoring_loop())
    yield
    # Shutdown
    bluetooth_obd.stop_all()
    monitor_task.cancel()

app = FastAPI(
    title="LifeLink Crash Detection Backend",
    description="Multi-Parameter Crash Detection with Adaptive False Alarm Suppression",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Auth Dependencies & RBAC -----------------

def get_current_session(
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
) -> Optional[Dict[str, Any]]:
    active_tok = None
    if authorization and authorization.startswith("Bearer "):
        active_tok = authorization.split("Bearer ")[1].strip()
    elif x_token:
        active_tok = x_token.strip()
    elif token:
        active_tok = token.strip()
        
    if not active_tok:
        return None
    return auth_manager.get_session(active_tok)

def require_admin(session: Optional[Dict[str, Any]] = Depends(get_current_session)):
    """
    CRITICAL SECURITY RULE:
    The user must NOT be able to access the admin portal or execute admin actions.
    Fleet administrator role is strictly verified!
    """
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in as an administrator."
        )
    if session.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Access Denied: Drivers are restricted to the Driver HUD. Admin portal access is unauthorized."
        )
    return session

def require_auth(session: Optional[Dict[str, Any]] = Depends(get_current_session)):
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in to access this portal."
        )
    return session

# ----------------- Authentication Endpoints -----------------

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    session = auth_manager.authenticate(req.username, req.password)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    
    # Retrieve user profile and OBD detector configuration
    user = auth_manager.get_user_profile(req.username)
    
    # Sync active vehicle ID with bluetooth OBD manager
    if user and user.role != "admin":
        bluetooth_obd.current_state["vehicle_id"] = user.vehicle_id
        bluetooth_obd.current_state["driver_name"] = user.full_name

    return {
        "status": "SUCCESS",
        "session": session,
        "user_profile": {
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "phone_number": user.phone_number,
            "email": user.email,
            "blood_group": user.blood_group,
            "vehicle_id": user.vehicle_id,
            "vehicle_make_model": user.vehicle_make_model,
            "emergency_contact_1": f"{user.emergency_contact_1_name} ({user.emergency_contact_1_phone})",
            "emergency_contact_2": f"{user.emergency_contact_2_name} ({user.emergency_contact_2_phone})",
            "obd_detector": user.obd_detector.model_dump()
        }
    }

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    phone_number: str
    email: Optional[str] = None
    blood_group: Optional[str] = "O+"
    vehicle_id: str
    vehicle_make_model: str
    emergency_contact_1_name: str
    emergency_contact_1_phone: str
    emergency_contact_2_name: Optional[str] = "Secondary Contact"
    emergency_contact_2_phone: Optional[str] = "+91-91122-33446"
    obd_detector: Optional[Dict[str, Any]] = None

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    success, result = auth_manager.register_user(req.model_dump())
    if not success:
        raise HTTPException(status_code=400, detail=result)
    
    # Automatically authenticate newly registered user
    session = auth_manager.authenticate(req.username, req.password)
    return {
        "status": "SUCCESS",
        "message": f"Driver profile for {req.full_name} and OBD detector successfully registered!",
        "session": session,
        "profile": result.model_dump(exclude={"password_hash"})
    }

@app.get("/api/auth/me")
async def get_my_profile(session: Dict[str, Any] = Depends(require_auth)):
    user = auth_manager.get_user_profile(session["username"])
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found.")
    return {
        "user": user.model_dump(exclude={"password_hash"}),
        "role": user.role
    }

class OBDUpdateRequest(BaseModel):
    device_name: str
    bluetooth_mac: str
    obd_protocol: str
    baud_rate: int
    imu_sensor_type: str
    sample_rate_hz: int

@app.post("/api/auth/obd-config")
async def update_my_obd_config(req: OBDUpdateRequest, session: Dict[str, Any] = Depends(require_auth)):
    updated = auth_manager.update_obd_detector(session["username"], req.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Failed to update OBD detector configuration.")
    return {
        "status": "SUCCESS",
        "message": "OBD Detector specifications updated successfully.",
        "obd_detector": req.model_dump()
    }

@app.post("/api/auth/logout")
async def logout(session: Optional[Dict[str, Any]] = Depends(get_current_session)):
    if session:
        auth_manager.logout(session["token"])
    return {"status": "SUCCESS", "message": "Logged out successfully."}

# ----------------- Telemetry & Sensor Endpoints -----------------

@app.get("/api/status")
async def get_system_status():
    v_id = bluetooth_obd.current_state.get("vehicle_id", "KA-05-LL-2026")
    alert = emergency_manager.get_vehicle_alert(v_id)
    return {
        "system": "LifeLink",
        "version": "1.0.0",
        "status": "OPERATIONAL",
        "connection_mode": bluetooth_obd.connection_mode,
        "is_bluetooth_connected": bluetooth_obd.is_connected,
        "current_vehicle": v_id,
        "active_alert": alert.model_dump() if alert else None,
        "config": detector.get_config()
    }

class TelemetryPayload(BaseModel):
    speed_kmh: float
    rpm: Optional[float] = 2000.0
    ax: float
    ay: float
    az: float
    gyro_x: Optional[float] = 0.0
    gyro_y: Optional[float] = 0.0
    gyro_z: Optional[float] = 0.0
    latitude: Optional[float] = 12.9716
    longitude: Optional[float] = 77.5946
    vehicle_id: Optional[str] = "KA-05-LL-2026"
    driver_name: Optional[str] = "Alex Morgan"

@app.post("/api/telemetry")
async def ingest_telemetry(payload: TelemetryPayload):
    """Direct live telemetry ingestion from Web Bluetooth, Mobile device, or IoT unit."""
    data = payload.model_dump()
    data["timestamp"] = time.time()
    
    # Update state
    bluetooth_obd.current_state.update(data)
    bluetooth_obd.is_connected = True
    bluetooth_obd.connection_mode = "CLIENT_STREAM"
    
    # Evaluate immediately
    frame = TelemetryFrame(**data)
    analysis = detector.evaluate_frame(frame)
    on_live_telemetry_frame(data)
    
    return {
        "status": "PROCESSED",
        "analysis": analysis.model_dump()
    }

@app.get("/api/bluetooth/ports")
async def get_com_ports():
    """List host serial and Bluetooth COM ports."""
    return {"ports": bluetooth_obd.list_available_ports()}

class SerialConnectRequest(BaseModel):
    port: str
    baudrate: int = 9600

@app.post("/api/bluetooth/connect")
async def connect_bluetooth_serial(req: SerialConnectRequest):
    """Connect to a Bluetooth OBD-II device on Windows COM port."""
    res = bluetooth_obd.connect_serial_bluetooth(req.port, req.baudrate)
    return res

class SimulateRequest(BaseModel):
    action: str  # "START" or "STOP"
    vehicle_id: Optional[str] = "KA-05-LL-2026"
    scenario: Optional[str] = "NORMAL_DRIVING"

@app.post("/api/bluetooth/simulate")
async def toggle_simulation(req: SimulateRequest):
    if req.action.upper() == "START":
        res = bluetooth_obd.start_simulated_stream(req.vehicle_id or "KA-05-LL-2026", req.scenario or "NORMAL_DRIVING")
        return res
    else:
        bluetooth_obd.stop_all()
        return {"status": "STOPPED", "message": "Simulation stopped"}

# ----------------- Emergency Confirmation & Cancellation -----------------

class UserConfirmationRequest(BaseModel):
    vehicle_id: str
    user_status: str  # "SAFE" or "CANCEL"

@app.post("/api/emergency/cancel")
async def cancel_emergency_alert(req: UserConfirmationRequest):
    """
    CRITICAL USER REQUIREMENT:
    If crash is detected, there is a popup in the UI. If the user clicks the button
    before 30s, the automatic call function MUST NOT WORK / CANCELLED!
    """
    res = emergency_manager.user_cancel_alert(req.vehicle_id, reason="User marked SAFE on UI popup")
    if res:
        v_state = bluetooth_obd.get_vehicle_state(req.vehicle_id)
        if v_state:
            v_state["drill_active"] = False
            v_state["speed_kmh"] = 45.0
            v_state["ax"] = 0.05
            v_state["ay"] = 0.02
            v_state["az"] = 0.98
            v_state["gyro_x"] = 0.0
            v_state["gyro_y"] = 0.0
        
        await broadcast_ws({
            "type": "ALERT_CANCELLED",
            "vehicle_id": req.vehicle_id,
            "alert": res.model_dump(),
            "message": f"Driver {req.vehicle_id} confirmed safe. Automatic emergency call successfully deactivated."
        })
        return {"status": "SUCCESS", "message": "Emergency alert deactivated by user confirmation.", "alert": res.model_dump()}
    else:
        return {"status": "NOT_FOUND", "message": "No active pending confirmation found for this vehicle."}

@app.get("/api/emergency/current")
async def get_current_emergency(vehicle_id: Optional[str] = None):
    v_id = vehicle_id or "KA-05-LL-2026"
    alert = emergency_manager.get_vehicle_alert(v_id)
    return {
        "active_alert": alert.model_dump() if alert else None,
        "history": [a.model_dump() for a in emergency_manager.alert_history[:10]]
    }

# ----------------- Admin Restricted Endpoints -----------------

class MockDrillRequest(BaseModel):
    scenario: str  # "HEAD_ON_COLLISION", "ROLLOVER_CRASH", "POTHOLE_BUMP", "HARD_BRAKING", "CUSTOM"
    vehicle_id: Optional[str] = "KA-05-LL-2026"  # Target individual user's car!
    custom_params: Optional[Dict[str, Any]] = None

@app.post("/api/drill/trigger")
async def trigger_mock_drill(req: MockDrillRequest, admin_session: Dict[str, Any] = Depends(require_admin)):
    """
    ADMIN TARGETED MOCK DRILL FEATURE:
    Triggers pseudo-accident or false-alarm scenarios on a SPECIFIC chosen user/vehicle!
    """
    target_id = req.vehicle_id or "KA-05-LL-2026"
    injected_state = bluetooth_obd.inject_drill_scenario(
        req.scenario,
        target_vehicle_id=target_id,
        custom_params=req.custom_params
    )
    
    # Run immediate detection on target vehicle
    frame = TelemetryFrame(**injected_state)
    analysis = detector.evaluate_frame(frame)
    on_live_telemetry_frame(injected_state)
    
    return {
        "status": "DRILL_INJECTED",
        "scenario": req.scenario,
        "target_vehicle_id": target_id,
        "injected_state": injected_state,
        "detection_analysis": analysis.model_dump()
    }

@app.get("/api/admin/vehicle/{vehicle_id}/live")
async def get_single_vehicle_live(vehicle_id: str, admin_session: Dict[str, Any] = Depends(require_admin)):
    """Admin Inspector: Retrieves full real-time telemetry, model analysis, and iOBD parameters for a specific driver."""
    v_state = bluetooth_obd.get_vehicle_state(vehicle_id)
    if not v_state:
        # Check if registered user exists and auto-register into live fleet simulator
        registered_drivers = auth_manager.list_all_drivers()
        matched = next((d for d in registered_drivers if d["vehicle_id"] == vehicle_id), None)
        if matched:
            v_state = bluetooth_obd.register_or_update_vehicle(vehicle_id, matched["full_name"])
        else:
            raise HTTPException(status_code=404, detail="Vehicle not found in fleet.")

    frame = TelemetryFrame(**v_state)
    analysis = detector.evaluate_frame(frame).model_dump()
    alert = emergency_manager.get_vehicle_alert(vehicle_id)
    user = next((u for u in auth_manager.users.values() if u.vehicle_id == vehicle_id), None)

    return {
        "vehicle_id": vehicle_id,
        "driver_profile": user.model_dump(exclude={"password_hash"}) if user else None,
        "telemetry": v_state,
        "analysis": analysis,
        "active_alert": alert.model_dump() if alert else None
    }

class ConfigUpdateRequest(BaseModel):
    w1: Optional[float] = None
    w2: Optional[float] = None
    w3: Optional[float] = None
    thresh_a: Optional[float] = None
    thresh_dv: Optional[float] = None
    thresh_theta: Optional[float] = None
    thresh_T: Optional[float] = None

@app.post("/api/admin/config")
async def update_model_config(req: ConfigUpdateRequest, admin_session: Dict[str, Any] = Depends(require_admin)):
    params = req.model_dump(exclude_unset=True)
    detector.update_config(**params)
    return {"status": "UPDATED", "config": detector.get_config()}

@app.get("/api/admin/vehicles")
async def get_admin_vehicles(admin_session: Dict[str, Any] = Depends(require_admin)):
    """
    Fleet overview of all monitored vehicles, driver profiles, and OBD detector specs.
    Strictly restricted to Admin!
    """
    registered_drivers = auth_manager.list_all_drivers()
    v_id = bluetooth_obd.current_state.get("vehicle_id", "KA-05-LL-2026")
    active_alert = emergency_manager.get_vehicle_alert(v_id)
    
    fleet_vehicles = []
    for d in registered_drivers:
        if d["role"] == "admin":
            continue
        is_current = (d["vehicle_id"] == v_id)
        fleet_vehicles.append({
            "vehicle_id": d["vehicle_id"],
            "driver_name": d["full_name"],
            "phone_number": d["phone_number"],
            "blood_group": d["blood_group"],
            "vehicle_make_model": d["vehicle_make_model"],
            "emergency_contacts": d["emergency_contacts"],
            "obd_detector": d["obd_detector"],
            "status": ("CRASH_ALERT" if (active_alert and active_alert.status == "PENDING_CONFIRMATION") 
                      else ("DISPATCHED" if (active_alert and active_alert.status == "DISPATCHED_EMERGENCY") else "NORMAL_DRIVING")) if is_current else "NORMAL_DRIVING",
            "speed_kmh": bluetooth_obd.current_state.get("speed_kmh", 0.0) if is_current else 52.0,
            "latitude": bluetooth_obd.current_state.get("latitude", 12.9716) if is_current else 12.9785,
            "longitude": bluetooth_obd.current_state.get("longitude", 77.5946) if is_current else 77.5992,
            "network_online": True,
            "connection_mode": bluetooth_obd.connection_mode if is_current else "CLOUD_SYNC",
            "active_alert_id": active_alert.alert_id if (is_current and active_alert) else None
        })
    
    return {
        "vehicles": fleet_vehicles,
        "responders": emergency_manager.registered_proximity_responders
    }

@app.get("/api/blackbox/history")
async def get_blackbox_logs(admin_session: Dict[str, Any] = Depends(require_admin)):
    return {
        "incident_logs": black_box.get_incident_logs(15),
        "recent_telemetry": black_box.get_recent_frames(bluetooth_obd.current_state.get("vehicle_id", "KA-05-LL-2026"), 30)
    }

# ----------------- WebSocket Real-Time Stream -----------------

@app.websocket("/ws/live/{client_id}")
async def websocket_telemetry(websocket: WebSocket, client_id: str):
    await websocket.accept()
    connected_websockets.append(websocket)
    try:
        # Send initial snapshot
        v_state = bluetooth_obd.current_state
        initial_frame = TelemetryFrame(**v_state)
        analysis = detector.evaluate_frame(initial_frame).model_dump()
        active_alert = emergency_manager.get_vehicle_alert(v_state.get("vehicle_id", "KA-05-LL-2026"))
        
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "telemetry": v_state,
            "analysis": analysis,
            "active_alert": active_alert.model_dump() if active_alert else None,
            "config": detector.get_config()
        })
        
        while True:
            # Keep socket open and accept incoming client commands
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "PING":
                    await websocket.send_json({"type": "PONG", "time": time.time()})
            except Exception:
                pass
    except WebSocketDisconnect:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)
    except Exception:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)

# ----------------- Static UI Files & Routing -----------------

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
async def root_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/login")
async def login_page():
    return FileResponse(os.path.join(frontend_dir, "login.html"))

@app.get("/user")
async def user_page():
    return FileResponse(os.path.join(frontend_dir, "user.html"))

@app.get("/admin")
async def admin_page():
    return FileResponse(os.path.join(frontend_dir, "admin.html"))
