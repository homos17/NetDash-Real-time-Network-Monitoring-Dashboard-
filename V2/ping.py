# real_network.py

import time
import subprocess
import logging

class NetworkModel:
    def __init__(self):
        self.router = {
            "ip": "192.168.8.1",
            "device_type": "generic",
            "username": "FUKE U_5G",
            "password": "abdozzxxcv",
            "port": 22
        }
        self.devices = {
            "Laptop": {"ip": "192.168.8.6"},
            "Phone": {"ip": "192.168.8.92"},
            "Server": {"ip": "192.168.8.79"}
        }
        self.data = {
            "ping_status": {},
            "alerts": []
        }

    def ping_device(self, ip: str) -> str:
        try:
            result = subprocess.run(
                ["ping", "-n", "1", ip], capture_output=True, text=True, timeout=5
            )
            if "Reply from" in result.stdout and "Destination host unreachable" not in result.stdout:
                return "up"
            else:
                return "down"
        except subprocess.TimeoutExpired:
            return "down"
        except Exception as e:
            logging.error(f"Error pinging {ip}: {e}")
            return "down"

    def test_ping_devices(self):
        for name, info in self.devices.items():
            ip = info["ip"]
            status = self.ping_device(ip)
            self.data["ping_status"][name] = {"ip": ip, "status": status}
            logging.info(f"{name} ({ip}) is {status}")
            if status == "down":
                alert = f"{name} is DOWN at {time.strftime('%H:%M:%S')}"
                self.data["alerts"].append(alert)

    def poll_data(self):
        self.test_ping_devices()

    def get_status(self):
        self.poll_data()
        return self.data
