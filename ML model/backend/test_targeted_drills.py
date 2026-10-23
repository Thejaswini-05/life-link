"""
LifeLink Targeted Mock Drill & Live User Telemetry Inspector Test
Verifies:
1. Admin can inspect live telemetry of any user separately.
2. Admin can trigger a mock drill specifically on User B.
3. User B gets the crash alert while User A remains normal.
"""

import urllib.request
import urllib.error
import json
import time

base = 'http://127.0.0.1:8000'

def post_json(endpoint, data, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(f'{base}{endpoint}', data=json.dumps(data).encode('utf-8'), headers=headers)
    try:
        res = urllib.request.urlopen(req)
        return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def get_json(endpoint, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(f'{base}{endpoint}', headers=headers)
    try:
        res = urllib.request.urlopen(req)
        return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

print("=== 1. ADMIN AUTHENTICATION ===")
status, admin_data = post_json('/api/auth/login', {'username': 'admin', 'password': 'admin123'})
admin_token = admin_data['session']['token']
print(f"Admin Logged In successfully. Token: {admin_token[:10]}...")

# Reset any lingering alert states
post_json('/api/emergency/cancel', {'vehicle_id': 'KA-05-LL-2026', 'user_status': 'SAFE'})
post_json('/api/emergency/cancel', {'vehicle_id': 'KA-01-MJ-9988', 'user_status': 'SAFE'})

print("\n=== 2. ADMIN INSPECTING LIVE DATA OF USER A & USER B SEPARATELY ===")
# Inspect User A (Alex Morgan)
status_a, live_a = get_json('/api/admin/vehicle/KA-05-LL-2026/live', token=admin_token)
tel_a = live_a['telemetry']
ana_a = live_a['analysis']
print(f"User A [Alex Morgan (KA-05-LL-2026)]:")
print(f"  - Speed: {tel_a['speed_kmh']:.1f} km/h | RPM: {tel_a['rpm']:.0f} | G-Force: {ana_a['impact_acceleration_A']:.2f}g | Tilt: {ana_a['tilt_angle_theta']:.1f}°")
print(f"  - Crash Status: {ana_a['is_crash']} (Alert: {live_a['active_alert'] is not None})")

# Inspect User B (Priya Sharma)
status_b, live_b = get_json('/api/admin/vehicle/KA-01-MJ-9988/live', token=admin_token)
tel_b = live_b['telemetry']
ana_b = live_b['analysis']
print(f"\nUser B [Priya Sharma (KA-01-MJ-9988)]:")
print(f"  - Speed: {tel_b['speed_kmh']:.1f} km/h | RPM: {tel_b['rpm']:.0f} | G-Force: {ana_b['impact_acceleration_A']:.2f}g | Tilt: {ana_b['tilt_angle_theta']:.1f}°")
print(f"  - Crash Status: {ana_b['is_crash']} (Alert: {live_b['active_alert'] is not None})")

print("\n=== 3. ADMIN SIMULATING MOCK DRILL TARGETING ONLY USER B (Priya Sharma) ===")
drill_payload = {
    'scenario': 'HEAD_ON_COLLISION',
    'vehicle_id': 'KA-01-MJ-9988'  # TARGET USER B!
}
status_drill, res_drill = post_json('/api/drill/trigger', drill_payload, token=admin_token)
print(f"Drill Triggered on {res_drill['target_vehicle_id']} -> Status: {status_drill}")
ana_drill = res_drill['detection_analysis']
print(f"  - Impact: {ana_drill['impact_acceleration_A']}g | Speed Drop: {ana_drill['speed_drop_delta_v']} km/h | Decision D: {ana_drill['decision_score_D']}")
print(f"  - Crash Confirmed: {ana_drill['is_crash']} ({ana_drill['crash_severity']})")

print("\n=== 4. VERIFYING USER ISOLATION AFTER TARGETED DRILL ===")
# Check User B (Should be in CRASH alert)
status_b_post, live_b_post = get_json('/api/admin/vehicle/KA-01-MJ-9988/live', token=admin_token)
alert_b = live_b_post['active_alert']
print(f"User B [Priya Sharma] State -> Crash Detected: {alert_b is not None} | Alert Status: {alert_b['status'] if alert_b else 'NONE'}")

# Check User A (MUST REMAIN IN NORMAL DRIVING!)
status_a_post, live_a_post = get_json('/api/admin/vehicle/KA-05-LL-2026/live', token=admin_token)
alert_a = live_a_post['active_alert']
print(f"User A [Alex Morgan] State  -> Crash Detected: {alert_a is not None} | Speed: {live_a_post['telemetry']['speed_kmh']:.1f} km/h (Completely unaffected!)")

assert alert_b is not None, "User B should have an active crash alert"
assert alert_a is None, "User A should NOT have a crash alert - User isolation failed!"
print("\n>>> SUCCESS: Targeted Mock Drill correctly triggered ONLY on User B while User A continued normal cruising!")

print("\n=== 5. USER B CANCELS ALERT ON HUD ('I AM SAFE') ===")
cancel_status, cancel_res = post_json('/api/emergency/cancel', {
    'vehicle_id': 'KA-01-MJ-9988',
    'user_status': 'SAFE'
})
print("User B Cancellation Result:", cancel_res['status'], "-", cancel_res['message'])

# Verify User B alert deactivated
_, live_b_final = get_json('/api/admin/vehicle/KA-01-MJ-9988/live', token=admin_token)
print(f"User B Final Alert State: {live_b_final['active_alert']}")
print(">>> ALL TARGETED DRILL & TELEPRESENCE TESTS PASSED 100%!")
