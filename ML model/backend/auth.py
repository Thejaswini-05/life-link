"""
LifeLink Authentication & User Profile Management
Handles multi-user login, registration, role-based access control (RBAC),
driver personal details, emergency contacts, and in-depth OBD detector hardware profiles.
"""

import hashlib
import secrets
import time
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

def hash_password(password: str, salt: str = "lifelink_secure_salt") -> str:
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()

class OBDDetectorConfig(BaseModel):
    device_name: str = "ELM327-Bluetooth-v2.1"
    bluetooth_mac: str = "00:1D:A5:68:90:E4"
    obd_protocol: str = "ISO 15765-4 CAN (11 bit, 500 kbaud)"
    baud_rate: int = 38400
    imu_sensor_type: str = "MPU-6050 6-Axis (±8g, ±500°/s)"
    connection_type: str = "BLUETOOTH_SPP"  # BLUETOOTH_SPP, BLE, USB_SERIAL, SIMULATED
    sample_rate_hz: int = 5
    calibrated_az_offset: float = 0.0

class UserProfile(BaseModel):
    user_id: str
    username: str
    password_hash: str
    role: str = "user"  # "user" or "admin"
    full_name: str
    phone_number: str
    email: str
    blood_group: str = "O+"
    
    # Vehicle Details
    vehicle_id: str = "KA-05-LL-2026"
    vehicle_make_model: str = "Hyundai Creta 2024"
    
    # Emergency Contacts
    emergency_contact_1_name: str = "Sarah Morgan (Spouse)"
    emergency_contact_1_phone: str = "+91-98765-11223"
    emergency_contact_2_name: str = "Dr. Rajesh (Family Physician)"
    emergency_contact_2_phone: str = "+91-98765-99887"
    
    # In-Depth OBD Detector Specifications
    obd_detector: OBDDetectorConfig = Field(default_factory=OBDDetectorConfig)
    
    created_at: float = Field(default_factory=time.time)

class AuthManager:
    def __init__(self):
        # Store users in-memory (and can persist to JSON file)
        self.users: Dict[str, UserProfile] = {}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}  # token -> {user_id, role, username, expires}
        self._init_default_users()

    def _init_default_users(self):
        # 1. Admin Account
        admin_user = UserProfile(
            user_id="USER-ADMIN-001",
            username="admin",
            password_hash=hash_password("admin123"),
            role="admin",
            full_name="Fleet Commander Sarah",
            phone_number="+91-91100-00001",
            email="admin@lifelink.org",
            blood_group="B+",
            vehicle_id="FLEET-HQ-01",
            vehicle_make_model="Emergency Response Command Unit",
            obd_detector=OBDDetectorConfig(
                device_name="Fleet-HQ-Scanner-Pro",
                bluetooth_mac="FF:EE:DD:CC:BB:AA",
                obd_protocol="Direct Cloud Telemetry Stream"
            )
        )
        self.users["admin"] = admin_user

        # 2. Default Driver Account
        driver_user = UserProfile(
            user_id="USER-DRV-002",
            username="driver",
            password_hash=hash_password("user123"),
            role="user",
            full_name="Alex Morgan",
            phone_number="+91-98765-43210",
            email="alex.morgan@gmail.com",
            blood_group="A+",
            vehicle_id="KA-05-LL-2026",
            vehicle_make_model="Honda City ZX 2023",
            emergency_contact_1_name="Elena Morgan (Wife)",
            emergency_contact_1_phone="+91-98765-99881",
            emergency_contact_2_name="Mark Morgan (Brother)",
            emergency_contact_2_phone="+91-98765-99882",
            obd_detector=OBDDetectorConfig(
                device_name="ELM327-v2.1-Bluetooth",
                bluetooth_mac="00:1D:A5:68:90:E4",
                obd_protocol="ISO 15765-4 CAN (11 bit, 500 kbaud)",
                baud_rate=38400,
                imu_sensor_type="MPU-6050 6-Axis (±8g, ±500°/s)",
                connection_type="BLUETOOTH_SPP",
                sample_rate_hz=5
            )
        )
        self.users["driver"] = driver_user

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        user = self.users.get(username.strip().lower())
        if not user:
            return None
        
        expected_hash = hash_password(password)
        if user.password_hash != expected_hash:
            return None
        
        # Generate session token
        token = secrets.token_hex(24)
        session_info = {
            "token": token,
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
            "vehicle_id": user.vehicle_id,
            "login_time": time.time(),
            "expires_at": time.time() + (3600 * 24)  # 24 hours
        }
        self.active_sessions[token] = session_info
        return session_info

    def register_user(self, data: Dict[str, Any]):
        username = data.get("username", "").strip().lower()
        if not username:
            return False, "Username is required."
        if username in self.users:
            return False, f"Username '{username}' is already registered."
        
        password = data.get("password", "")
        if len(password) < 4:
            return False, "Password must be at least 4 characters long."

        # Parse OBD detector details
        obd_data = data.get("obd_detector", {})
        obd_config = OBDDetectorConfig(
            device_name=obd_data.get("device_name", "ELM327-Bluetooth-v2.1"),
            bluetooth_mac=obd_data.get("bluetooth_mac", "00:1D:A5:00:11:22"),
            obd_protocol=obd_data.get("obd_protocol", "ISO 15765-4 CAN (11 bit, 500 kbaud)"),
            baud_rate=int(obd_data.get("baud_rate", 38400)),
            imu_sensor_type=obd_data.get("imu_sensor_type", "MPU-6050 6-Axis (±8g)"),
            connection_type=obd_data.get("connection_type", "BLUETOOTH_SPP"),
            sample_rate_hz=int(obd_data.get("sample_rate_hz", 5))
        )

        user_id = f"USER-{int(time.time() * 1000)}"
        new_user = UserProfile(
            user_id=user_id,
            username=username,
            password_hash=hash_password(password),
            role="user",  # Self-registration is strictly role="user"
            full_name=data.get("full_name", "Registered Driver"),
            phone_number=data.get("phone_number", "+91-90000-00000"),
            email=data.get("email", f"{username}@lifelink.local"),
            blood_group=data.get("blood_group", "O+"),
            vehicle_id=data.get("vehicle_id", f"KA-01-LL-{secrets.randbelow(9000)+1000}"),
            vehicle_make_model=data.get("vehicle_make_model", "Passenger Vehicle"),
            emergency_contact_1_name=data.get("emergency_contact_1_name", "Primary Contact"),
            emergency_contact_1_phone=data.get("emergency_contact_1_phone", "+91-91122-33445"),
            emergency_contact_2_name=data.get("emergency_contact_2_name", "Secondary Contact"),
            emergency_contact_2_phone=data.get("emergency_contact_2_phone", "+91-91122-33446"),
            obd_detector=obd_config
        )

        self.users[username] = new_user
        return True, new_user

    def get_session(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        session = self.active_sessions.get(token)
        if not session:
            return None
        if time.time() > session["expires_at"]:
            del self.active_sessions[token]
            return None
        return session

    def get_user_profile(self, username: str) -> Optional[UserProfile]:
        return self.users.get(username.strip().lower())

    def update_obd_detector(self, username: str, obd_data: Dict[str, Any]) -> bool:
        user = self.users.get(username.strip().lower())
        if not user:
            return False
        
        user.obd_detector.device_name = obd_data.get("device_name", user.obd_detector.device_name)
        user.obd_detector.bluetooth_mac = obd_data.get("bluetooth_mac", user.obd_detector.bluetooth_mac)
        user.obd_detector.obd_protocol = obd_data.get("obd_protocol", user.obd_detector.obd_protocol)
        user.obd_detector.baud_rate = int(obd_data.get("baud_rate", user.obd_detector.baud_rate))
        user.obd_detector.imu_sensor_type = obd_data.get("imu_sensor_type", user.obd_detector.imu_sensor_type)
        user.obd_detector.sample_rate_hz = int(obd_data.get("sample_rate_hz", user.obd_detector.sample_rate_hz))
        return True

    def list_all_drivers(self) -> List[Dict[str, Any]]:
        """Used by Admin to lookup all registered users and their OBD detector specs."""
        results = []
        for u in self.users.values():
            results.append({
                "user_id": u.user_id,
                "username": u.username,
                "role": u.role,
                "full_name": u.full_name,
                "phone_number": u.phone_number,
                "email": u.email,
                "blood_group": u.blood_group,
                "vehicle_id": u.vehicle_id,
                "vehicle_make_model": u.vehicle_make_model,
                "emergency_contacts": [
                    {"name": u.emergency_contact_1_name, "phone": u.emergency_contact_1_phone},
                    {"name": u.emergency_contact_2_name, "phone": u.emergency_contact_2_phone}
                ],
                "obd_detector": u.obd_detector.model_dump()
            })
        return results

    def logout(self, token: str):
        if token in self.active_sessions:
            del self.active_sessions[token]

auth_manager = AuthManager()
