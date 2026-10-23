"""
LifeLink Emergency Response & Confirmation Manager
Handles 30-second user confirmation countdown, AI voice emergency call generation,
proximity-based alerts, and offline SMS fallback.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field

class EmergencyAlertState(BaseModel):
    alert_id: str
    vehicle_id: str
    created_at: float
    timeout_seconds: int = 30
    status: str = "PENDING_CONFIRMATION"  # PENDING_CONFIRMATION, CANCELLED_SAFE, DISPATCHED_EMERGENCY
    cancelled_at: Optional[float] = None
    dispatched_at: Optional[float] = None
    crash_metrics: Dict[str, Any]
    location: Dict[str, float]
    ai_voice_script: str = ""
    proximity_alerts_sent: List[Dict[str, Any]] = []
    sms_payload: Dict[str, Any] = {}
    time_remaining_sec: float = 30.0

class EmergencyManager:
    def __init__(self, countdown_seconds: int = 30):
        self.countdown_seconds = countdown_seconds
        self.active_alerts: Dict[str, EmergencyAlertState] = {}
        self.alert_history: List[EmergencyAlertState] = []
        self._listeners: List[Callable] = []
        
        # Simulated nearby registered emergency vehicles/good samaritans for proximity alerts (Section 3.6)
        self.registered_proximity_responders = [
            {"id": "RESP-01", "name": "Highway Patrol Unit 4", "distance_km": 1.2, "phone": "+91-98765-43210", "type": "Police"},
            {"id": "RESP-02", "name": "City General Ambulance #8", "distance_km": 2.4, "phone": "+91-98765-43211", "type": "Ambulance"},
            {"id": "RESP-03", "name": "Registered Nearby Driver (Ashok)", "distance_km": 0.6, "phone": "+91-98765-43212", "type": "Civilian Volunteer"},
        ]

    def register_listener(self, callback: Callable):
        self._listeners.append(callback)

    def trigger_crash_alert(
        self,
        vehicle_id: str,
        crash_result: Dict[str, Any],
        location: Dict[str, float],
        driver_name: str = "Alex Morgan"
    ) -> EmergencyAlertState:
        """
        Initiates 30-second confirmation window when crash is detected.
        """
        alert_id = f"ALERT-{int(time.time() * 1000)}"
        now = time.time()
        
        # Build AI Voice emergency speech transcript (Section 3.4)
        lat = location.get("latitude", 12.9716)
        lon = location.get("longitude", 77.5946)
        a_impact = crash_result.get("impact_acceleration_A", 0.0)
        dv = crash_result.get("speed_drop_delta_v", 0.0)
        theta = crash_result.get("tilt_angle_theta", 0.0)
        severity = crash_result.get("crash_severity", "CRASH")
        
        ai_script = (
            f"EMERGENCY PRIORITY ALERT. LifeLink Automated Crash Detection System reporting a confirmed "
            f"post-collision incident for vehicle registration {vehicle_id}, driver {driver_name}. "
            f"Incident location: Latitude {lat:.4f}, Longitude {lon:.4f}. "
            f"Crash Telemetry: Impact force {a_impact:.1f} Gs, deceleration drop {dv:.1f} kilometers per hour, "
            f"vehicle orientation tilt {theta:.1f} degrees. Severity level: {severity}. "
            f"The driver did not respond within the mandatory 30-second safety confirmation window. "
            f"Immediate emergency dispatch and paramedic deployment required."
        )

        # Proximity Alerts (Section 3.6)
        proximity_alerts = []
        for resp in self.registered_proximity_responders:
            proximity_alerts.append({
                "responder_id": resp["id"],
                "name": resp["name"],
                "distance_km": resp["distance_km"],
                "alert_status": "QUEUED",
                "message": f"CRITICAL: Crash detected {resp['distance_km']} km from you at [{lat:.4f}, {lon:.4f}]. Assistance requested."
            })

        # Offline SMS payload (Section 3.5)
        sms_body = (
            f"SOS! LIFELINK CRASH ALERT: Car {vehicle_id} in {severity}. "
            f"G-Force: {a_impact}g, Drop: {dv}km/h, Tilt: {theta}deg. "
            f"Location: https://maps.google.com/?q={lat},{lon} "
            f"Emergency dispatch notified."
        )

        alert = EmergencyAlertState(
            alert_id=alert_id,
            vehicle_id=vehicle_id,
            created_at=now,
            timeout_seconds=self.countdown_seconds,
            status="PENDING_CONFIRMATION",
            crash_metrics=crash_result,
            location=location,
            ai_voice_script=ai_script,
            proximity_alerts_sent=proximity_alerts,
            sms_payload={
                "recipient": "911 / 112 / +91-91122-33445",
                "message": sms_body,
                "offline_channel": "GSM_SMS_FALLBACK_ACTIVE",
                "timestamp": now
            },
            time_remaining_sec=float(self.countdown_seconds)
        )

        self.active_alerts[vehicle_id] = alert
        return alert

    def user_cancel_alert(self, vehicle_id: str, reason: str = "User confirmed safe") -> Optional[EmergencyAlertState]:
        """
        If user clicks "I am Safe" within the 30s window, cancel automatic call!
        """
        alert = self.active_alerts.get(vehicle_id)
        if not alert:
            return None
        
        if alert.status == "PENDING_CONFIRMATION":
            alert.status = "CANCELLED_SAFE"
            alert.cancelled_at = time.time()
            # Mark proximity alerts as cancelled
            for p in alert.proximity_alerts_sent:
                p["alert_status"] = "CANCELLED_DRIVER_OK"
            
            # Archive alert
            self.alert_history.insert(0, alert)
            del self.active_alerts[vehicle_id]
            return alert
        
        return alert

    def dispatch_emergency(self, vehicle_id: str) -> Optional[EmergencyAlertState]:
        """
        Called when 30 seconds expires without user cancelling.
        """
        alert = self.active_alerts.get(vehicle_id)
        if not alert:
            return None
        
        alert.status = "DISPATCHED_EMERGENCY"
        alert.dispatched_at = time.time()
        alert.time_remaining_sec = 0.0
        
        for p in alert.proximity_alerts_sent:
            p["alert_status"] = "DISPATCHED"
            
        self.alert_history.insert(0, alert)
        return alert

    def check_timeouts(self) -> List[EmergencyAlertState]:
        """
        Updates remaining time and auto-dispatches if 30s exceeded.
        """
        dispatched = []
        now = time.time()
        
        for vehicle_id, alert in list(self.active_alerts.items()):
            if alert.status == "PENDING_CONFIRMATION":
                elapsed = now - alert.created_at
                rem = max(0.0, self.countdown_seconds - elapsed)
                alert.time_remaining_sec = round(rem, 1)
                
                if rem <= 0:
                    self.dispatch_emergency(vehicle_id)
                    dispatched.append(alert)
                    
        return dispatched

    def get_vehicle_alert(self, vehicle_id: str) -> Optional[EmergencyAlertState]:
        return self.active_alerts.get(vehicle_id)

emergency_manager = EmergencyManager(countdown_seconds=30)
