"""
LifeLink Bluetooth & OBD-II Fleet Manager
Handles multi-vehicle live telemetry streams:
1. Physical Bluetooth Serial (ELM327 / HC-05 / ESP32 OBD-II Dongles on Windows COM ports)
2. Web Bluetooth / Web Serial data relay via WebSocket or REST
3. Fleet Telemetry Synthesizer providing concurrent independent live streams for each user
4. Targeted Mock Drill injection per individual vehicle
"""

import time
import math
import random
import threading
from typing import Dict, Any, Optional, Callable, List
import serial
import serial.tools.list_ports

class BluetoothOBDManager:
    def __init__(self, on_frame_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.on_frame_callback = on_frame_callback
        self.is_connected = True
        self.connection_mode = "FLEET_SIMULATOR"  # "SERIAL_BLUETOOTH", "FLEET_SIMULATOR", "WEB_BLUETOOTH"
        self.serial_port = None
        self._serial_thread = None
        self._sim_thread = None
        self._running = False
        
        # Multi-vehicle state storage: vehicle_id -> live telemetry dict
        self.vehicle_states: Dict[str, Dict[str, Any]] = {}
        
        # Initialize default drivers
        self._init_default_vehicles()

    def _init_default_vehicles(self):
        # 1. Driver 1: Alex Morgan
        self.vehicle_states["KA-05-LL-2026"] = {
            "vehicle_id": "KA-05-LL-2026",
            "driver_name": "Alex Morgan",
            "speed_kmh": 68.0,
            "rpm": 2240.0,
            "throttle_pct": 24.5,
            "engine_temp_c": 89.0,
            "ax": 0.05,
            "ay": 0.02,
            "az": 0.98,
            "gyro_x": 0.8,
            "gyro_y": 0.4,
            "gyro_z": 0.1,
            "latitude": 12.9716,
            "longitude": 77.5946,
            "network_online": True,
            "bluetooth_connected": True,
            "drill_active": False,
            "last_packet_time": time.time()
        }

        # 2. Driver 2: Priya Sharma
        self.vehicle_states["KA-01-MJ-9988"] = {
            "vehicle_id": "KA-01-MJ-9988",
            "driver_name": "Priya Sharma",
            "speed_kmh": 54.0,
            "rpm": 1850.0,
            "throttle_pct": 19.0,
            "engine_temp_c": 86.0,
            "ax": 0.03,
            "ay": -0.02,
            "az": 1.01,
            "gyro_x": 0.4,
            "gyro_y": 0.2,
            "gyro_z": 0.0,
            "latitude": 12.9785,
            "longitude": 77.5992,
            "network_online": True,
            "bluetooth_connected": True,
            "drill_active": False,
            "last_packet_time": time.time()
        }

    @property
    def current_state(self) -> Dict[str, Any]:
        """Backwards compatibility: returns primary driver state."""
        return self.vehicle_states.get("KA-05-LL-2026", list(self.vehicle_states.values())[0])

    def get_vehicle_state(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        return self.vehicle_states.get(vehicle_id)

    def register_or_update_vehicle(self, vehicle_id: str, driver_name: str, **kwargs) -> Dict[str, Any]:
        if vehicle_id not in self.vehicle_states:
            self.vehicle_states[vehicle_id] = {
                "vehicle_id": vehicle_id,
                "driver_name": driver_name,
                "speed_kmh": 60.0,
                "rpm": 2000.0,
                "throttle_pct": 20.0,
                "engine_temp_c": 88.0,
                "ax": 0.04,
                "ay": 0.02,
                "az": 1.0,
                "gyro_x": 0.5,
                "gyro_y": 0.3,
                "gyro_z": 0.1,
                "latitude": 12.9716 + (random.uniform(-0.02, 0.02)),
                "longitude": 77.5946 + (random.uniform(-0.02, 0.02)),
                "network_online": True,
                "bluetooth_connected": True,
                "drill_active": False,
                "last_packet_time": time.time()
            }
        else:
            self.vehicle_states[vehicle_id]["driver_name"] = driver_name
        self.vehicle_states[vehicle_id].update(kwargs)
        return self.vehicle_states[vehicle_id]

    def list_available_ports(self) -> List[Dict[str, str]]:
        """List active COM ports on Windows to find Bluetooth OBD scanners."""
        ports = serial.tools.list_ports.comports()
        result = []
        for p in ports:
            result.append({
                "port": p.device,
                "description": p.description,
                "hwid": p.hwid
            })
        return result

    def connect_serial_bluetooth(self, com_port: str, baudrate: int = 9600, target_vehicle_id: str = "KA-05-LL-2026") -> Dict[str, Any]:
        """Connect to a physical Bluetooth OBD-II device on Windows COM port."""
        try:
            self.stop_all()
            self.serial_port = serial.Serial(com_port, baudrate=baudrate, timeout=1.0)
            self.is_connected = True
            self.connection_mode = "SERIAL_BLUETOOTH"
            
            v = self.get_vehicle_state(target_vehicle_id)
            if v:
                v["bluetooth_connected"] = True

            self._running = True
            self._serial_thread = threading.Thread(target=self._serial_read_loop, args=(target_vehicle_id,), daemon=True)
            self._serial_thread.start()
            
            return {"status": "SUCCESS", "message": f"Connected to Bluetooth OBD device on {com_port}", "port": com_port}
        except Exception as e:
            self.connection_mode = "DISCONNECTED"
            return {"status": "ERROR", "message": str(e)}

    def start_simulated_stream(self, vehicle_id: str = "KA-05-LL-2026", scenario: str = "NORMAL_DRIVING") -> Dict[str, Any]:
        """Start realistic multi-vehicle live OBD-II telemetry simulation."""
        self._running = True
        self.is_connected = True
        self.connection_mode = "FLEET_SIMULATOR"
        
        if not self._sim_thread or not self._sim_thread.is_alive():
            self._sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self._sim_thread.start()
        return {"status": "SUCCESS", "message": "Multi-vehicle live OBD-II streams active"}

    def stop_all(self):
        self._running = False
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.serial_port = None

    def inject_drill_scenario(
        self,
        scenario_name: str,
        target_vehicle_id: Optional[str] = None,
        custom_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        ADMIN TARGETED MOCK DRILL TRIGGER:
        Simulates pseudo-accident on ONE specific user's vehicle without affecting others!
        """
        now = time.time()
        target_id = target_vehicle_id or "KA-05-LL-2026"
        
        if target_id not in self.vehicle_states:
            self.register_or_update_vehicle(target_id, "Target Driver")

        target_state = self.vehicle_states[target_id]
        target_state["drill_active"] = True
        
        if scenario_name == "HEAD_ON_COLLISION":
            # High speed drop (>20km/h), high G impact (>3g), nominal tilt (<45deg)
            target_state["speed_kmh"] = 0.0
            target_state["ax"] = -5.8  # Violent forward deceleration
            target_state["ay"] = 1.4
            target_state["az"] = 1.8
            target_state["gyro_x"] = 14.0
            target_state["gyro_y"] = 28.0
            target_state["throttle_pct"] = 0.0
            target_state["rpm"] = 650.0

        elif scenario_name == "ROLLOVER_CRASH":
            # High impact (>3g), high tilt (>45deg), speed drop
            target_state["speed_kmh"] = 5.0
            target_state["ax"] = 3.6
            target_state["ay"] = 4.8
            target_state["az"] = 0.2   # Vehicle flipped sideways/upside down
            target_state["gyro_x"] = 78.0 # Extreme roll angle
            target_state["gyro_y"] = 35.0
            target_state["throttle_pct"] = 0.0
            target_state["rpm"] = 0.0

        elif scenario_name == "POTHOLE_BUMP":
            # TEST FALSE ALARM SUPPRESSION: High G momentary spike (e.g. 3.4g vertical shock),
            # but NO speed drop, NO abnormal tilt. LifeLink must NOT trigger crash!
            target_state["ax"] = 0.4
            target_state["ay"] = 0.3
            target_state["az"] = 3.5   # Vertical jolt
            target_state["gyro_x"] = 3.0
            target_state["gyro_y"] = 2.0
            target_state["speed_kmh"] = max(35.0, target_state.get("speed_kmh", 48.0) - 1.5)

        elif scenario_name == "HARD_BRAKING":
            # TEST FALSE ALARM SUPPRESSION: Speed drops rapidly, but impact force is low (1.3g).
            target_state["speed_kmh"] = max(10.0, target_state.get("speed_kmh", 70.0) - 28.0)
            target_state["ax"] = -1.3
            target_state["ay"] = 0.1
            target_state["az"] = 1.05
            target_state["gyro_x"] = 2.5
            target_state["gyro_y"] = 4.0
            target_state["throttle_pct"] = 0.0

        elif scenario_name == "CUSTOM" and custom_params:
            for k, v in custom_params.items():
                if k in target_state:
                    target_state[k] = v

        target_state["last_packet_time"] = now
        if self.on_frame_callback:
            self.on_frame_callback(dict(target_state))

        return target_state

    def _simulation_loop(self):
        """Continuously streams realistic OBD-II frames for each active vehicle concurrently."""
        t = 0.0
        
        while self._running:
            t += 0.2
            
            for v_id, state in list(self.vehicle_states.items()):
                # Add individual vehicle noise/variation
                jitter_a = random.gauss(0, 0.04)
                jitter_s = random.gauss(0, 0.5)

                # Smooth GPS drive trajectory along a route
                offset = hash(v_id) % 100 * 0.01
                state["latitude"] += 0.00003 * math.sin(t * 0.05 + offset)
                state["longitude"] += 0.00004 * math.cos(t * 0.05 + offset)
                
                # If vehicle is in normal cruising (speed > 10 km/h)
                if state["speed_kmh"] > 10.0 and not state.get("drill_active", False):
                    base_speed = 65.0 + (hash(v_id) % 25 - 12)
                    state["speed_kmh"] = max(20.0, min(110.0, base_speed + 4.0 * math.sin(t * 0.1 + offset) + jitter_s))
                    state["rpm"] = max(1000.0, state["speed_kmh"] * 32.0 + random.uniform(-30, 30))
                    state["throttle_pct"] = max(15.0, min(40.0, 22.0 + 6.0 * math.sin(t * 0.1 + offset)))
                    
                    state["ax"] = round(0.06 * math.sin(t * 0.2 + offset) + jitter_a, 3)
                    state["ay"] = round(0.05 * math.cos(t * 0.15 + offset) + jitter_a, 3)
                    state["az"] = round(1.0 + random.gauss(0, 0.02), 3)
                    state["gyro_x"] = round(random.gauss(0, 0.6), 2)
                    state["gyro_y"] = round(random.gauss(0, 0.6), 2)
                    state["gyro_z"] = round(random.gauss(0, 0.4), 2)

                state["timestamp"] = time.time()
                state["last_packet_time"] = state["timestamp"]

                if self.on_frame_callback:
                    try:
                        self.on_frame_callback(dict(state))
                    except Exception:
                        pass

            time.sleep(0.25)

    def _serial_read_loop(self, target_vehicle_id: str):
        """Reads raw ELM327 OBD-II / Arduino lines for a specific connected vehicle."""
        v = self.get_vehicle_state(target_vehicle_id)
        while self._running and self.serial_port and self.serial_port.is_open:
            try:
                line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                if line and v:
                    self._parse_raw_telemetry_line(v, line)
            except Exception:
                time.sleep(0.1)

    def _parse_raw_telemetry_line(self, v_state: Dict[str, Any], line: str):
        try:
            parts = line.replace(";", ",").split(",")
            updated = False
            for p in parts:
                if ":" in p or "=" in p:
                    sep = ":" if ":" in p else "="
                    k, val = p.split(sep, 1)
                    k = k.strip().lower()
                    val = float(val.strip())
                    
                    if k in ["speed", "spd"]:
                        v_state["speed_kmh"] = val
                        updated = True
                    elif k in ["rpm"]:
                        v_state["rpm"] = val
                        updated = True
                    elif k in ["ax"]:
                        v_state["ax"] = val
                        updated = True
                    elif k in ["ay"]:
                        v_state["ay"] = val
                        updated = True
                    elif k in ["az"]:
                        v_state["az"] = val
                        updated = True
                    elif k in ["gx", "gyrox"]:
                        v_state["gyro_x"] = val
                        updated = True
                    elif k in ["gy", "gyroy"]:
                        v_state["gyro_y"] = val
                        updated = True

            if updated:
                v_state["timestamp"] = time.time()
                if self.on_frame_callback:
                    self.on_frame_callback(dict(v_state))
        except Exception:
            pass

bluetooth_obd = BluetoothOBDManager()
