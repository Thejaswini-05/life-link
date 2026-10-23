"""
LifeLink Model Test Suite & Validation Benchmark
Verifies Equations 1-5 from Diana George et al. and false alarm suppression.
"""

import sys
import os
import unittest

# Ensure root directory is on python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.model import LifeLinkCrashDetector, TelemetryFrame
from backend.emergency_manager import EmergencyManager

class TestLifeLinkModel(unittest.TestCase):
    def setUp(self):
        self.detector = LifeLinkCrashDetector(
            w1=0.4, w2=0.3, w3=0.3,
            thresh_a=3.0, thresh_dv=20.0, thresh_theta=45.0,
            thresh_T=0.68
        )
        self.emergency = EmergencyManager(countdown_seconds=30)

    def test_normal_driving(self):
        """Scenario 1: Normal highway cruise (nominal readings)."""
        frame = TelemetryFrame(
            vehicle_id="TEST-01",
            speed_kmh=80.0,
            ax=0.04, ay=0.03, az=1.0,
            gyro_x=0.5, gyro_y=0.5
        )
        res = self.detector.evaluate_frame(frame)
        self.assertFalse(res.is_crash)
        self.assertFalse(res.false_alarm_suppressed)
        self.assertLess(res.decision_score_D, 0.3)
        self.assertEqual(res.crash_severity, "NONE")

    def test_pothole_false_alarm_suppression(self):
        """
        Scenario 2: Pothole shock (A > 3.0g, but Delta_v is 0 and vehicle is upright).
        Paper Goal: Traditional systems trigger false alarm. LifeLink MUST suppress it!
        """
        # Baseline frame
        f1 = TelemetryFrame(vehicle_id="TEST-02", speed_kmh=50.0, ax=0.0, ay=0.0, az=1.0)
        self.detector.evaluate_frame(f1)
        
        # Pothole impact frame (shock spike)
        f2 = TelemetryFrame(vehicle_id="TEST-02", speed_kmh=49.0, ax=0.2, ay=0.3, az=3.4)
        res = self.detector.evaluate_frame(f2)
        
        self.assertFalse(res.is_crash, "Pothole should NOT trigger crash confirmation")
        self.assertTrue(res.false_alarm_suppressed, "Pothole should be marked as suppressed false alarm")
        self.assertLess(res.decision_score_D, 0.68)

    def test_hard_braking_false_alarm_suppression(self):
        """
        Scenario 3: Emergency hard braking (Delta_v > 20 km/h, but impact A is nominal ~1.3g).
        Paper Goal: LifeLink MUST suppress false alarm from hard braking alone!
        """
        f1 = TelemetryFrame(vehicle_id="TEST-03", speed_kmh=80.0, ax=0.0, ay=0.0, az=1.0)
        self.detector.evaluate_frame(f1)

        f2 = TelemetryFrame(vehicle_id="TEST-03", speed_kmh=42.0, ax=-1.2, ay=0.1, az=1.05)
        res = self.detector.evaluate_frame(f2)

        self.assertFalse(res.is_crash, "Hard braking alone should NOT trigger crash")
        self.assertTrue(res.false_alarm_suppressed, "Hard braking should be suppressed")

    def test_severe_head_on_collision(self):
        """
        Scenario 4: High-speed head-on crash.
        Impact A = 6.5g (>3g), Speed drops from 70 to 0 km/h (Delta_v = 70 > 20km/h).
        LifeLink MUST confirm crash and score D > T!
        """
        f1 = TelemetryFrame(vehicle_id="TEST-04", speed_kmh=70.0, ax=0.0, ay=0.0, az=1.0)
        self.detector.evaluate_frame(f1)

        f2 = TelemetryFrame(vehicle_id="TEST-04", speed_kmh=0.0, ax=-5.8, ay=1.5, az=2.0)
        res = self.detector.evaluate_frame(f2)

        self.assertTrue(res.is_crash, "Severe head-on collision MUST trigger crash = 1")
        self.assertGreater(res.decision_score_D, 0.68)
        self.assertEqual(res.crash_severity, "SEVERE_CRASH")

    def test_rollover_crash(self):
        """
        Scenario 5: Vehicle Rollover & Flip.
        Impact A = 4.5g (>3g), Tilt = 78 deg (>45 deg), Speed drops from 60 to 5 km/h.
        """
        f1 = TelemetryFrame(vehicle_id="TEST-05", speed_kmh=60.0, ax=0.0, ay=0.0, az=1.0)
        self.detector.evaluate_frame(f1)

        f2 = TelemetryFrame(
            vehicle_id="TEST-05",
            speed_kmh=5.0,
            ax=3.5, ay=4.2, az=0.3,
            gyro_x=75.0, gyro_y=35.0
        )
        res = self.detector.evaluate_frame(f2)

        self.assertTrue(res.is_crash, "Rollover crash MUST trigger crash = 1")
        self.assertGreater(res.tilt_angle_theta, 45.0)
        self.assertGreater(res.decision_score_D, 0.68)

    def test_user_confirmation_cancellation(self):
        """
        Tests Section 3.3 & user requirement:
        If user clicks button within 30s, automatic call must NOT work!
        """
        crash_data = {
            "impact_acceleration_A": 5.8,
            "speed_drop_delta_v": 50.0,
            "tilt_angle_theta": 15.0,
            "crash_severity": "SEVERE_CRASH"
        }
        loc = {"latitude": 12.9716, "longitude": 77.5946}
        
        # 1. Trigger alert
        alert = self.emergency.trigger_crash_alert("TEST-06", crash_data, loc, "Test Driver")
        self.assertEqual(alert.status, "PENDING_CONFIRMATION")
        self.assertEqual(alert.timeout_seconds, 30)

        # 2. User cancels within 30 seconds
        cancelled = self.emergency.user_cancel_alert("TEST-06", reason="Driver marked safe")
        self.assertIsNotNone(cancelled)
        self.assertEqual(cancelled.status, "CANCELLED_SAFE")
        self.assertIsNone(self.emergency.get_vehicle_alert("TEST-06"))

if __name__ == "__main__":
    unittest.main()
