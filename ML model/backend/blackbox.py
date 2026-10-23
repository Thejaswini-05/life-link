"""
LifeLink Black-Box Flight Recorder / Telemetry Logger
Maintains pre-incident and post-incident rolling telemetry buffers
for crash forensics and post-mortem analysis (Diana George et al., Section 3.7)
"""

import time
import json
import os
from typing import List, Dict, Any, Optional
from collections import deque

class TelemetryBlackBox:
    def __init__(self, buffer_size: int = 100):
        # Rolling buffer for pre-incident telemetry (last 100 frames ~ 10-30 seconds)
        self.buffer_size = buffer_size
        self._buffers: Dict[str, deque] = {}
        self.incident_logs: List[Dict[str, Any]] = []

    def record_frame(self, frame_dict: Dict[str, Any], analysis_dict: Dict[str, Any]):
        vehicle_id = frame_dict.get("vehicle_id", "DEFAULT")
        if vehicle_id not in self._buffers:
            self._buffers[vehicle_id] = deque(maxlen=self.buffer_size)
        
        entry = {
            "timestamp": frame_dict.get("timestamp", time.time()),
            "speed_kmh": frame_dict.get("speed_kmh", 0.0),
            "rpm": frame_dict.get("rpm", 0.0),
            "throttle_pct": frame_dict.get("throttle_pct", 0.0),
            "engine_temp_c": frame_dict.get("engine_temp_c", 88.0),
            "ax": frame_dict.get("ax", 0.0),
            "ay": frame_dict.get("ay", 0.0),
            "az": frame_dict.get("az", 1.0),
            "impact_A": analysis_dict.get("impact_acceleration_A", 0.0),
            "speed_drop_dv": analysis_dict.get("speed_drop_delta_v", 0.0),
            "tilt_theta": analysis_dict.get("tilt_angle_theta", 0.0),
            "decision_D": analysis_dict.get("decision_score_D", 0.0),
            "is_crash": analysis_dict.get("is_crash", False),
            "false_alarm_suppressed": analysis_dict.get("false_alarm_suppressed", False)
        }
        self._buffers[vehicle_id].append(entry)

    def freeze_incident_log(self, vehicle_id: str, trigger_type: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a permanent incident log packaging the pre-incident telemetry sequence
        for forensic replay and post-mortem analysis.
        """
        buffer_copy = list(self._buffers.get(vehicle_id, []))
        incident_id = f"INC-{int(time.time() * 1000)}"
        
        record = {
            "incident_id": incident_id,
            "vehicle_id": vehicle_id,
            "timestamp": time.time(),
            "trigger_type": trigger_type,
            "metadata": metadata,
            "frames_count": len(buffer_copy),
            "telemetry_history": buffer_copy
        }
        self.incident_logs.insert(0, record)
        return record

    def get_recent_frames(self, vehicle_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        buf = list(self._buffers.get(vehicle_id, []))
        return buf[-limit:] if buf else []

    def get_incident_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.incident_logs[:limit]

black_box = TelemetryBlackBox()
