import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URI = "http://localhost:58000/api/v1"
USERNAME = "cisco"
PASSWORD = "cisco123!"

def get_service_ticket():
    headers = {"Content-Type": "application/json"}
    data = json.dumps({"username": USERNAME, "password": PASSWORD})
    resp = requests.post(f"{BASE_URI}/ticket", data=data, headers=headers)
    resp.raise_for_status()

    
    return resp.json()["response"]["serviceTicket"]

def get_devices():
    ticket = get_service_ticket()
    headers = {"X-Auth-Token": ticket}
    resp = requests.get(f"{BASE_URI}/network-device", headers=headers, verify=False)
    resp.raise_for_status()
    devices_data = []

    for device in resp.json()["response"]:
        status = device.get("reachabilityStatus", "N/A")

        # ✅ تنبيه لو الجهاز Unreachable
        if status.lower() == "unreachable":
            hostname = device.get("hostname", "Unknown")
            ip = device.get("managementIpAddress", "N/A")
            print(f"[ALERT] Device '{hostname}' ({ip}) is UNREACHABLE!")

        device_info = {
            "hostname": device.get("hostname", "N/A"),
            "ip": device.get("managementIpAddress", "N/A"),
            "status": status,
            "uptime": device.get("upTime", "N/A"),
            "software_version": device.get("softwareVersion", "N/A"),
            "mac": device.get("macAddress", "N/A"),
            "type": device.get("type", "N/A"),
            "platform": device.get("platformId", "N/A"),
            "product": device.get("productId", "N/A"),
            "serial": device.get("serialNumber", "N/A"),
            "interfaces": device.get("connectedInterfaceName", []),
            "connected_devices": []
        }

        connected_names = device.get("connectedNetworkDeviceName", [])
        connected_ips = device.get("connectedNetworkDeviceIpAddress", [])
        for i, intf in enumerate(device_info["interfaces"]):
            name = connected_names[i] if i < len(connected_names) else "N/A"
            ip_addr = connected_ips[i] if i < len(connected_ips) else "N/A"
            device_info["connected_devices"].append({
                "interface": intf,
                "name": name,
                "ip": ip_addr
            })

        devices_data.append(device_info)

    return devices_data
