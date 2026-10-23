"""
LifeLink: Multi-Parameter Crash Detection & Decision Model
Strictly Post-Accident Detection Engine with Multi-Condition Validation
and Adaptive False Alarm Suppression (Diana George et al.)
"""

import math
import time
from typing import Dict, Any, Optional, Tuple, List
from pydantic import BaseModel, Field

class TelemetryFrame(BaseModel):
    vehicle_id: str = "KA-05-LL-2026"
    timestamp: float = Field(default_factory=time.time)
    speed_kmh: float = 0.0          # Current OBD-II vehicle speed (km/h)
    rpm: float = 0.0                # OBD-II Engine RPM
    throttle_pct: float = 0.0       # Throttle position %
    engine_temp_c: float = 88.0     # Coolant temperature
    ax: float = 0.0                 # Accelerometer X (g)
    ay: float = 0.0                 # Accelerometer Y (g)
    az: float = 1.0                 # Accelerometer Z (g, 1.0 = resting 1g gravity)
    gyro_x: float = 0.0             # Gyroscope roll rate / angular tilt component
    gyro_y: float = 0.0             # Gyroscope pitch rate
    gyro_z: float = 0.0             # Gyroscope yaw rate
    latitude: float = 12.9716       # GPS Latitude
    longitude: float = 77.5946      # GPS Longitude
    network_online: bool = True     # Connection status for offline hybrid fallback

class CrashAnalysisResult(BaseModel):
    is_crash: bool
    confidence: float
    decision_score_D: float
    impact_acceleration_A: float
    speed_drop_delta_v: float
    tilt_angle_theta: float
    validation_passed_count: int
    false_alarm_suppressed: bool
    suppression_reason: Optional[str] = None
    crash_severity: str            # "NONE", "MINOR_INCIDENT", "MODERATE_CRASH", "SEVERE_CRASH"
    metrics_breakdown: Dict[str, Any]
    formula_audit: Dict[str, str]

class LifeLinkCrashDetector:
    """
    LifeLink Multi-Condition Post-Accident Validation Engine.
    
    Equations:
    (1) A = sqrt(ax^2 + ay^2 + az^2)
    (2) Delta_v = v_{t-1} - v_t
    (3) D = w1 * A_norm + w2 * Delta_v_norm + w3 * Theta_norm
    (4) crash = 1 if D > T, 0 otherwise
    (5) Theta = arctan(y / x) (Tilt angle from orientation/gravity vector)
    """

    def __init__(
        self,
        w1: float = 0.4,
        w2: float = 0.3,
        w3: float = 0.3,
        thresh_a: float = 3.0,
        thresh_dv: float = 20.0,
        thresh_theta: float = 45.0,
        thresh_T: float = 0.68
    ):
        self.w1 = w1
        self.w2 = w2
        self.w3 = w3
        self.thresh_a = thresh_a
        self.thresh_dv = thresh_dv
        self.thresh_theta = thresh_theta
        self.thresh_T = thresh_T
        
        # Keep track of previous frames per vehicle to compute instantaneous speed variation Delta_v
        self._history: Dict[str, List[TelemetryFrame]] = {}

    def update_config(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k) and v is not None:
                setattr(self, k, float(v))

    def get_config(self) -> Dict[str, float]:
        return {
            "w1": self.w1,
            "w2": self.w2,
            "w3": self.w3,
            "thresh_a": self.thresh_a,
            "thresh_dv": self.thresh_dv,
            "thresh_theta": self.thresh_theta,
            "thresh_T": self.thresh_T,
        }

    def compute_impact_acceleration(self, ax: float, ay: float, az: float) -> float:
        """Equation (1): A = sqrt(ax^2 + ay^2 + az^2)"""
        return math.sqrt(ax * ax + ay * ay + az * az)

    def compute_speed_drop(self, vehicle_id: str, current_speed: float) -> float:
        """
        Equation (2): Delta_v = v_{t-1} - v_t
        Measures sudden deceleration caused by impact with obstacle/vehicle.
        """
        history = self._history.get(vehicle_id, [])
        if not history:
            return 0.0
        
        # Look back up to 1-2 seconds in rolling window for deceleration peak
        prev_frame = history[-1]
        delta_v = prev_frame.speed_kmh - current_speed
        
        # Look back across last 3 frames to capture abrupt stop over 0.5 - 1.5s
        if len(history) >= 2:
            max_prior_speed = max(f.speed_kmh for f in history[-3:])
            delta_v = max(delta_v, max_prior_speed - current_speed)
            
        return max(0.0, delta_v)

    def compute_tilt_angle(self, ax: float, ay: float, az: float, gyro_x: float, gyro_y: float) -> float:
        """
        Equation (5): theta = arctan(y / x)
        Paper specification:
        'To determine the abnormal orientation, Tilt Angle equation (5) is used:
         theta = arctan(y / x), where x, y are the gyroscope axis values.
         This equation is used to define a non-nominal orientation of the vehicle,
         such as if it is overturned or canted during an accident.'
        """
        # Gyroscope angular rate / orientation angle (Equation 5)
        if abs(gyro_x) > 0.001 or abs(gyro_y) > 0.001:
            # Gyroscopic tilt / rollover angle
            gyro_tilt = math.sqrt(gyro_x * gyro_x + gyro_y * gyro_y)
            return min(180.0, gyro_tilt)

        # Static post-impact orientation when vehicle has come to a stop or is upside down:
        # If az is flipped (e.g. upside down az < 0 or resting on side with horizontal gravity)
        # Note: only apply static gravity when vehicle is not experiencing high dynamic deceleration
        if az < 0.2:  # Overturned / rolled onto its side or roof
            horizontal = math.sqrt(ax * ax + ay * ay)
            return min(180.0, math.atan2(horizontal, max(0.01, abs(az))) * (180.0 / math.pi))

        return 0.0

    def evaluate_frame(self, frame: TelemetryFrame) -> CrashAnalysisResult:
        """
        Evaluates a live incoming telemetry frame for post-accident verification.
        Applies Multi-Condition Validation and Adaptive Weighted Decision Model.
        """
        # 1. Compute individual parameters
        A = self.compute_impact_acceleration(frame.ax, frame.ay, frame.az)
        delta_v = self.compute_speed_drop(frame.vehicle_id, frame.speed_kmh)
        theta = self.compute_tilt_angle(frame.ax, frame.ay, frame.az, frame.gyro_x, frame.gyro_y)

        # 2. Condition checks (Table 1)
        cond_A = A > self.thresh_a
        cond_dv = delta_v > self.thresh_dv
        cond_theta = theta > self.thresh_theta

        validations_passed = sum([1 if cond_A else 0, 1 if cond_dv else 0, 1 if cond_theta else 0])

        # 3. Normalized score for weighted fusion (Equation 3: D = w1*A_norm + w2*Delta_v_norm + w3*theta_norm)
        # Normalization scale:
        # A: 1.0g (normal) -> 3.0g (threshold) -> 7.0g+ (severe)
        norm_A = min(1.0, max(0.0, (A - 1.0) / (6.0 - 1.0)))
        # delta_v: 0 -> 20 km/h (threshold) -> 60 km/h (severe)
        norm_dv = min(1.0, max(0.0, delta_v / 50.0))
        # theta: 0 -> 45 deg (threshold) -> 90 deg (complete rollover)
        norm_theta = min(1.0, max(0.0, theta / 90.0))

        # Weight assignment: w1=0.4 (impact), w2=0.3 (speed drop), w3=0.3 (tilt)
        D = (self.w1 * norm_A) + (self.w2 * norm_dv) + (self.w3 * norm_theta)

        # 4. Multi-Condition Validation & False Alarm Suppression
        # Critical Paper Principle:
        # A single trigger alone (e.g. hitting a pothole with momentary A>3g, or hard braking with delta_v>20km/h)
        # MUST be filtered out to eliminate false positives.
        # An accident is confirmed ONLY when multiple corroborating parameters validate the crash event!
        
        is_crash = False
        false_alarm_suppressed = False
        suppression_reason = None
        
        if D > self.thresh_T:
            # Check multi-condition safety guard:
            # A crash must either have high impact (A > thresh) AND significant speed drop OR vehicle rollover tilt.
            if cond_A and (cond_dv or cond_theta):
                is_crash = True
            elif cond_dv and cond_theta and A > 2.0:
                # Moderate impact coupled with severe roll and sudden stop
                is_crash = True
            else:
                # High score caused by a single extreme anomaly without corroboration
                false_alarm_suppressed = True
                suppression_reason = (
                    "Single-trigger anomaly filtered by Multi-Condition Validation. "
                    f"A={A:.2f}g, Delta_v={delta_v:.1f}km/h, Theta={theta:.1f} deg. "
                    "Insufficient corroborated multi-sensor conditions."
                )
        else:
            # Even if a single condition triggered, check if false alarm was actively suppressed
            if cond_A and not (cond_dv or cond_theta):
                false_alarm_suppressed = True
                suppression_reason = f"Pothole/bump shock ({A:.2f}g) suppressed: vehicle speed maintained ({delta_v:.1f} km/h drop) and tilt upright ({theta:.1f}°)."
            elif cond_dv and not (cond_A or cond_theta):
                false_alarm_suppressed = True
                suppression_reason = f"Emergency hard braking ({delta_v:.1f} km/h drop) suppressed: impact force nominal ({A:.2f}g) and no rollover ({theta:.1f}°)."

        # Determine severity
        if not is_crash:
            severity = "NONE"
        elif A > 6.0 or theta > 70.0 or delta_v > 45.0:
            severity = "SEVERE_CRASH"
        elif A > 4.5 or delta_v > 30.0 or theta > 55.0:
            severity = "MODERATE_CRASH"
        else:
            severity = "MINOR_INCIDENT"

        confidence = round(min(0.99, max(0.50, D * 1.15)) if is_crash else round(1.0 - D, 2), 2)

        # Update vehicle history (keep last 30 frames)
        if frame.vehicle_id not in self._history:
            self._history[frame.vehicle_id] = []
        self._history[frame.vehicle_id].append(frame)
        if len(self._history[frame.vehicle_id]) > 30:
            self._history[frame.vehicle_id].pop(0)

        return CrashAnalysisResult(
            is_crash=is_crash,
            confidence=confidence,
            decision_score_D=round(D, 3),
            impact_acceleration_A=round(A, 2),
            speed_drop_delta_v=round(delta_v, 1),
            tilt_angle_theta=round(theta, 1),
            validation_passed_count=validations_passed,
            false_alarm_suppressed=false_alarm_suppressed,
            suppression_reason=suppression_reason,
            crash_severity=severity,
            metrics_breakdown={
                "A_norm": round(norm_A, 3),
                "delta_v_norm": round(norm_dv, 3),
                "theta_norm": round(norm_theta, 3),
                "w1_A": round(self.w1 * norm_A, 3),
                "w2_dv": round(self.w2 * norm_dv, 3),
                "w3_theta": round(self.w3 * norm_theta, 3),
                "thresh_T": self.thresh_T,
                "cond_A_met": cond_A,
                "cond_dv_met": cond_dv,
                "cond_theta_met": cond_theta
            },
            formula_audit={
                "eq1_impact": f"A = sqrt({frame.ax:.2f}^2 + {frame.ay:.2f}^2 + {frame.az:.2f}^2) = {A:.2f}g (> {self.thresh_a}g: {cond_A})",
                "eq2_speed_drop": f"Delta_v = v_(t-1) - v_t = {delta_v:.1f} km/h (> {self.thresh_dv} km/h: {cond_dv})",
                "eq5_tilt": f"Theta = arctan(y/x) = {theta:.1f} deg (> {self.thresh_theta} deg: {cond_theta})",
                "eq3_weighted_score": f"D = {self.w1}*{norm_A:.2f} + {self.w2}*{norm_dv:.2f} + {self.w3}*{norm_theta:.2f} = {D:.3f}",
                "eq4_decision_rule": f"crash = 1 if D ({D:.3f}) > T ({self.thresh_T}) -> {'CRASH CONFIRMED' if is_crash else 'NORMAL / SUPPRESSED'}"
            }
        )

detector = LifeLinkCrashDetector()
