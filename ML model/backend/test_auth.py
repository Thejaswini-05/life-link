"""
LifeLink Auth & RBAC Verification Script
"""

import urllib.request
import urllib.error
import json

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

print("=== 1. TEST DRIVER LOGIN ===")
status, body = post_json('/api/auth/login', {'username': 'driver', 'password': 'user123'})
print('Driver Login Status:', status, '| Role:', body['session']['role'], '| Driver Name:', body['user_profile']['full_name'])
driver_token = body['session']['token']

print("\n=== 2. TEST RBAC PROTECTION (Driver accessing Admin APIs) ===")
status, body = get_json('/api/admin/vehicles', token=driver_token)
print('Driver calling GET /api/admin/vehicles -> Status:', status, '| Detail:', body.get('detail'))
status, body = post_json('/api/drill/trigger', {'scenario': 'HEAD_ON_COLLISION'}, token=driver_token)
print('Driver calling POST /api/drill/trigger -> Status:', status, '| Detail:', body.get('detail'))

print("\n=== 3. REGISTER NEW INDIVIDUAL WITH FULL DETAILS & iOBD HARDWARE ===")
import time
_uid = int(time.time())
new_driver_data = {
    'username': f'priya_{_uid}',
    'password': 'priyapassword',
    'full_name': 'Priya Sharma',
    'phone_number': '+91-98450-12345',
    'email': f'priya_{_uid}@techcorp.com',
    'blood_group': 'B+',
    'vehicle_id': f'KA-01-MJ-{_uid % 10000:04d}',
    'vehicle_make_model': 'Mahindra XUV700 AX7 2024',
    'emergency_contact_1_name': 'Vikram Sharma (Husband)',
    'emergency_contact_1_phone': '+91-98450-11223',
    'emergency_contact_2_name': 'Dr. Anita (Physician)',
    'emergency_contact_2_phone': '+91-98450-99887',
    'obd_detector': {
        'device_name': 'V-Gate iCar Pro Bluetooth 4.0 BLE',
        'bluetooth_mac': 'E4:95:6E:4A:21:99',
        'obd_protocol': 'ISO 15765-4 CAN (11 bit, 500 kbaud)',
        'baud_rate': 115200,
        'imu_sensor_type': 'MPU-6050 6-Axis (±8g, ±500°/s)',
        'sample_rate_hz': 10
    }
}
status, reg_res = post_json('/api/auth/register', new_driver_data)
print('Registration Status:', status, '| User:', reg_res['profile']['full_name'], '| Vehicle:', reg_res['profile']['vehicle_id'])
print('Configured iOBD Device:', reg_res['profile']['obd_detector']['device_name'], '| MAC:', reg_res['profile']['obd_detector']['bluetooth_mac'])

print("\n=== 4. TEST ADMIN LOGIN & FULL FLEET LOOKUP ===")
status, admin_body = post_json('/api/auth/login', {'username': 'admin', 'password': 'admin123'})
print('Admin Login Status:', status, '| Role:', admin_body['session']['role'])
admin_token = admin_body['session']['token']

status, fleet_body = get_json('/api/admin/vehicles', token=admin_token)
print('Admin GET /api/admin/vehicles Status:', status, '| Monitored Drivers count:', len(fleet_body['vehicles']))
for v in fleet_body['vehicles']:
    obd = v.get('obd_detector', {})
    print(f"  - Vehicle {v['vehicle_id']} ({v['driver_name']}) | iOBD: {obd.get('device_name')} [MAC: {obd.get('bluetooth_mac')}]")

print("\n=== 5. ADMIN TRIGGERING MOCK DRILL ===")
status, drill_res = post_json('/api/drill/trigger', {'scenario': 'ROLLOVER_CRASH'}, token=admin_token)
print('Admin Trigger Drill Status:', status, '| Scenario:', drill_res.get('scenario'), '| Crash:', drill_res.get('detection_analysis', {}).get('is_crash'))
