"""
LifeLink Configuration
Multi-Parameter Crash Detection with Adaptive False Alarm Suppression
Reference: Diana George et al., Dayananda Sagar University
"""

import os
from pydantic import BaseModel, Field
from typing import Dict, Any

class ModelConfig(BaseModel):
    # Parameter weights (Table 2 in paper)
    weight_acceleration: float = Field(default=0.4, description="Weight w1 for Acceleration (High importance)")
    weight_speed_change: float = Field(default=0.3, description="Weight w2 for Speed Change (Medium importance)")
    weight_tilt_angle: float = Field(default=0.3, description="Weight w3 for Tilt Angle (Medium importance)")
    
    # Sensor thresholds (Table 1 in paper)
    threshold_acceleration_g: float = Field(default=3.0, description="Impact acceleration threshold in g (> 3g)")
    threshold_speed_drop_kmh: float = Field(default=20.0, description="Sudden deceleration threshold in km/h (> 20 km/h)")
    threshold_tilt_degrees: float = Field(default=45.0, description="Vehicle abnormal tilt threshold in degrees (> 45 deg)")
    
    # Decision score threshold T (Equation 4: crash = 1 if D > T)
    threshold_decision_score_T: float = Field(default=0.68, description="Combined decision threshold T")
    
    # User Confirmation Timer (Section 3.3 in paper)
    user_confirmation_timeout_sec: int = Field(default=30, description="Fixed 30-second user confirmation countdown")
    
    # Proximity Alert Radius
    proximity_radius_km: float = Field(default=5.0, description="Radius in km for notifying nearby drivers/helpers")

    # Emergency Services AI Dispatch configuration
    emergency_contact_number: str = "911 / 112 (National Emergency Dispatch)"
    default_vehicle_id: str = "KA-05-LL-2026"
    default_driver_name: str = "Alex Morgan"

CONFIG = ModelConfig()
