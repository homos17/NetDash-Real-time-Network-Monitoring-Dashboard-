import requests
import xml.etree.ElementTree as ET

# إعدادات الراوتر
ROUTER_URL = "http://192.168.8.1"
USERNAME = "FUKE U_5G"
PASSWORD = "abdozzxxcv"  # غيرها بالباسورد الحقيقي

session = requests.Session()

# ======== Step 1: Get the initial token ========
def get_login_token():
    url = f"{ROUTER_URL}/html/index.html"
    resp = session.get(url)
    token = session.cookies.get('__RequestVerificationToken')
    return token

# ======== Step 2: Login to router ========
def login(username, password):
    token = get_login_token()

    # هواوي بتطلب الباسورد يكون Base64 + مشفر
    import base64
    from hashlib import sha256
    hashed_pwd = sha256(password.encode()).hexdigest().upper()
    encoded = base64.b64encode(hashed_pwd.encode()).decode()

    headers = {
        "__RequestVerificationToken": token,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<request>
<Username>{username}</Username>
<Password>{encoded}</Password>
<password_type>4</password_type>
</request>"""

    url = f"{ROUTER_URL}/api/user/login"
    resp = session.post(url, data=payload, headers=headers)
    if resp.status_code == 200 and "OK" in resp.text:
        print("[+] Login success.")
        return True
    else:
        print("[-] Login failed.")
        return False

# ======== Step 3: Get connected devices ========
def get_connected_devices():
    url = f"{ROUTER_URL}/api/lan/HostInfo"
    resp = session.get(url)
    root = ET.fromstring(resp.text)

    devices = []
    for host in root.findall("Hosts/Host"):
        device = {
            "name": host.findtext("HostName"),
            "ip": host.findtext("IPAddress"),
            "mac": host.findtext("MACAddress"),
            "connection_type": host.findtext("AssociatedDevice")  # true = wireless
        }
        devices.append(device)

    return devices

# ======== Main function ========
if login(USERNAME, PASSWORD):
    devices = get_connected_devices()
    print("\n[+] Connected Devices:\n")
    for dev in devices:
        print(f"Name: {dev['name']}")
        print(f"IP: {dev['ip']}")
        print(f"MAC: {dev['mac']}")
        print(f"Type: {'Wireless' if dev['connection_type'] == '1' else 'Wired'}")
        print("-" * 30)
