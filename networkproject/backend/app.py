from flask import Flask, jsonify, request
from flask_cors import CORS
import time
import subprocess
import random
import logging
import json
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from typing import Dict, List
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


class NetworkModel:
    def __init__(self):
        """Initialize the network model."""
        self.router = {
            "ip": "192.168.1.1",
            "device_type": "cisco_ios",
            "username": "user",
            "password": "orangeuser",
            "port": 22
        }
        self.data = {
            "ping_status": {},
            "interface_data": {},
            "bandwidth_trends": {},
            "alerts": []
        }
        self.json_file = "devices.json"
        self.load_devices()

    def load_devices(self):
        """Load devices from JSON file."""
        try:
            with open(self.json_file, 'r') as f:
                data = json.load(f)
                self.devices = {device['name']: {'ip': device['ip']} for device in data['devices']}
        except FileNotFoundError:
            logging.error(f"Devices file {self.json_file} not found.")
            self.devices = {}
        except json.JSONDecodeError:
            logging.error(f"Error decoding {self.json_file}.")
            self.devices = {}

    def save_devices(self):
        """Save devices to JSON file."""
        try:
            with open(self.json_file, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"devices": []}

        # Update the devices list
        data['devices'] = [
            {
                "name": name,
                "ip": info['ip'],
                "mac_address": info.get('mac_address', ':'.join(['{:02x}'.format(random.randint(0, 255)) for _ in range(6)])),
                "interface": info.get('interface', f"GigabitEthernet{random.randint(1, 4)}"),
                "last_ping": info.get('last_ping'),
                "status": info.get('status', 'unknown')
            }
            for name, info in self.devices.items()
        ]

        with open(self.json_file, 'w') as f:
            json.dump(data, f, indent=4)

    def register_device(self, name: str, ip: str):
        """Register a new device with a name and IP address."""
        if name in self.devices:
            logging.warning(f"Device {name} already exists.")
            return False
        
        self.devices[name] = {
            "ip": ip,
            "mac_address": ':'.join(['{:02x}'.format(random.randint(0, 255)) for _ in range(6)]),
            "interface": f"GigabitEthernet{random.randint(1, 4)}",
            "last_ping": None,
            "status": "unknown"
        }
        self.save_devices()
        logging.info(f"Device {name} with IP {ip} registered successfully.")
        return True

    def delete_device(self, name: str):
        """Delete a device."""
        if name in self.devices:
            del self.devices[name]
            self.save_devices()
            logging.info(f"Device {name} deleted successfully.")
        else:
            logging.warning(f"Device {name} not found.")

    def edit_device(self, old_name: str, new_name: str, new_ip: str):
        """Edit an existing device."""
        try:
            with open(self.json_file, 'r') as f:
                data = json.load(f)
                
            # Find the device in the JSON data
            device_index = next((i for i, d in enumerate(data['devices']) if d['name'] == old_name), None)
            
            if device_index is not None:
                # Get the existing device info
                device_info = data['devices'][device_index]
                
                # Update only the name and IP, preserve other information
                device_info['name'] = new_name
                device_info['ip'] = new_ip
                
                # Update the devices list
                data['devices'][device_index] = device_info
                
                # Save back to JSON
                with open(self.json_file, 'w') as f:
                    json.dump(data, f, indent=4)
                
                # Update the in-memory devices dictionary
                self.devices[new_name] = {"ip": new_ip}
                if old_name in self.devices:
                    del self.devices[old_name]
                
                logging.info(f"Device {old_name} edited to {new_name} with IP {new_ip}.")
            else:
                logging.warning(f"Device {old_name} not found.")
        except Exception as e:
            logging.error(f"Error editing device: {e}")

    def ping_device(self, ip: str) -> str:
        """Ping a device and return 'up' if reachable, otherwise 'down'."""
        try:
            result = subprocess.run(
                ["ping", "-n", "1", ip], capture_output=True, text=True, timeout=5
            )
            status = "up" if "Reply from" in result.stdout and "Destination host unreachable" not in result.stdout else "down"
            
            # Update device status in JSON
            for name, info in self.devices.items():
                if info['ip'] == ip:
                    info['status'] = status
                    info['last_ping'] = datetime.now().isoformat()
                    self.save_devices()
                    break
            
            return status
        except subprocess.TimeoutExpired:
            return "down"
        except Exception as e:
            logging.error(f"Error pinging {ip}: {e}")
            return "down"

    def test_ping_devices(self):
        """Check device presence using /host API instead of /network-device."""
        api_url = "http://localhost:58000/api/v1/host"
        headers = {"X-Auth-Token": "NC-102-e202ec415c014cd59dd1-nbi"}

        try:
            resp = requests.get(api_url, headers=headers, verify=False)
            if resp.status_code == 200:
                hosts = resp.json().get("response", [])
                for name, info in self.devices.items():
                    ip = info["ip"]
                    match = next((h for h in hosts if h.get("hostIp") == ip), None)
                    if match:
                        status = "up"
                    else:
                        status = "down"
                        self.data["alerts"].append(f"{name} is DOWN at {time.strftime('%H:%M:%S')}")
                    self.data["ping_status"][name] = status
            else:
                logging.error(f"Failed to fetch host data. Status code: {resp.status_code}")
        except Exception as e:
            logging.error(f"Error fetching host status via API: {e}")

    def fetch_actual_bandwidth(self):
        """Fetch host information from Cisco DNA Center."""
        try:
            api_url = "http://localhost:58000/api/v1/host"
            headers = {"X-Auth-Token": "NC-102-e202ec415c014cd59dd1-nbi"}
            
            resp = requests.get(api_url, headers=headers, verify=False)
            if resp.status_code == 200:
                hosts = resp.json().get("response", [])
                interface_data = {}
                
                for host in hosts:
                    interface_name = host.get("connectedInterfaceName", "Unknown")
                    interface_data[interface_name] = {
                        "host_name": host.get("hostName", "Unknown"),
                        "ip_address": host.get("hostIp", "Unknown"),
                        "mac_address": host.get("hostMac", "Unknown"),
                        "status": "up"  # Since we got the host info, it's up
                    }
                
                self.data["interface_data"] = interface_data
                logging.info(f"Successfully fetched host information for {len(interface_data)} interfaces")
            else:
                logging.error(f"Failed to fetch host data. Status code: {resp.status_code}")
        except Exception as e:
            logging.error(f"Error fetching host information: {e}")
            # Provide some sample data for testing
            self.data["interface_data"] = {
                "GigabitEthernet1": {
                    "host_name": "Router1",
                    "ip_address": "192.168.1.1",
                    "mac_address": "00:11:22:33:44:55",
                    "status": "up"
                },
                "GigabitEthernet2": {
                    "host_name": "Switch1",
                    "ip_address": "192.168.1.2",
                    "mac_address": "00:11:22:33:44:56",
                    "status": "up"
                }
            }

    def simulate_bandwidth(self):
        """Simulate bandwidth trends for each device that is reachable and display current bandwidth."""
        for device in self.devices:
            if self.data["ping_status"].get(device) != "up":
                continue

            if device not in self.data["bandwidth_trends"]:
                self.data["bandwidth_trends"][device] = []

            bandwidth = random.uniform(0.5, 20.0)  # Random bandwidth between 0.5 and 20 Mbps
            self.data["bandwidth_trends"][device].append(bandwidth)

            if len(self.data["bandwidth_trends"][device]) > 10:
                self.data["bandwidth_trends"][device].pop(0)

            current_bandwidth = self.data["bandwidth_trends"][device][-1]
            if current_bandwidth < 1.0:
                self.data["alerts"].append(f"{device} bandwidth low: {current_bandwidth:.2f} Mbps")

            logging.info(f"{device} current bandwidth: {current_bandwidth:.2f} Mbps")

    def _display_alerts(self):
        print("=== Alerts ===")
        if not self.data["alerts"]:
            print("No alerts at this time.")
        else:
            for alert in self.data["alerts"][-5:]:
                print(f"Alert: {alert}")
        print()

    def _display_json_devices(self):
        """Display the contents of devices.json in a readable format."""
        print("=== Local Devices (devices.json) ===")
        try:
            with open(self.json_file, 'r') as f:
                data = json.load(f)
                print(f"{'Host Name':<20} {'IP Address':<15} {'MAC Address':<20} {'Interface':<15} {'Status':<10}")
                print("-" * 85)
                for device in data['devices']:
                    print(f"{device['name']:<20} {device['ip']:<15} {device['mac_address']:<20} "
                          f"{device['interface']:<15} {device['status']:<10}")
        except Exception as e:
            print(f"Error reading devices.json: {e}")
        print()


class NetworkController:
    def __init__(self, model: NetworkModel):
        self.model = model

    def display_data(self):
        """Display network data in the terminal with periodic updates."""
        try:
            while True:
                self.model.test_ping_devices()
                self.model.simulate_bandwidth()
                self.model.fetch_actual_bandwidth()  # Fetch actual bandwidth if possible
                self._display_ping_status()
                self._display_interface_data()
                self._display_bandwidth_trends()
                self._display_alerts()
                
                time.sleep(10)
        except KeyboardInterrupt:
            logging.info("Exiting program...")

    def _display_ping_status(self):
        print("=== Ping Status ===")
        for device, status in self.model.data["ping_status"].items():
            print(f"{device:<10}: {'UP' if status == 'up' else 'DOWN'}")
        print()

    def _display_interface_data(self):
        print("=== Host Info ===")
        url = "http://localhost:58000/api/v1/host"
        headers = {"X-Auth-Token": "NC-102-e202ec415c014cd59dd1-nbi"}
        try:
            resp = requests.get(url, headers=headers, verify=False)
            if resp.status_code == 200:
                hosts = resp.json().get("response", [])
                print(f"{'Host Name':<20} {'IP Address':<15} {'MAC Address':<20} {'Interface':<15}")
                print("-" * 70)
                for host in hosts:
                    print(f"{host.get('hostName', 'Unknown'):<20} {host.get('hostIp', 'Unknown'):<15} {host.get('hostMac', 'Unknown'):<20} {host.get('connectedInterfaceName', 'Unknown'):<15}")
            else:
                print(f"Failed to fetch hosts: {resp.status_code}")
        except Exception as e:
            print(f"Host fetch error: {e}")
        print()

    def _display_bandwidth_trends(self):
        print("=== Current Bandwidth Usage (kbps) ===")
        print(f"{'Device':<15} {'Input Rate (kbps)':<20} {'Output Rate (kbps)':<20}")
        print("-" * 45)
        for device, data in self.model.data["interface_data"].items():
            input_rate = data.get("input_rate", "N/A")
            output_rate = data.get("output_rate", "N/A")
            print(f"{device:<15} {input_rate:<20} {output_rate:<20}")
        print()

    def _display_alerts(self):
        print("=== Alerts ===")
        if not self.model.data["alerts"]:
            print("No alerts at this time.")
        else:
            for alert in self.model.data["alerts"][-5:]:
                print(f"Alert: {alert}")
        print()        

    def register_and_ping_device(self):
        """Register a new device and ping it."""
        name = input("Enter the device name: ")
        ip = input("Enter the device IP address: ")
        self.model.register_device(name, ip)
        status = self.model.ping_device(ip)
        print(f"Device {name} ({ip}) is {'UP' if status == 'up' else 'DOWN'}.")

    def delete_device(self):
        """Delete a device."""
        name = input("Enter the name of the device to delete: ")
        self.model.delete_device(name)

    def edit_device(self):
        """Edit a device."""
        old_name = input("Enter the current device name: ")
        new_name = input("Enter the new device name: ")
        new_ip = input("Enter the new device IP address: ")
        self.model.edit_device(old_name, new_name, new_ip)

    def _display_json_devices(self):
        """Display the contents of devices.json in a readable format."""
        print("=== Local Devices (devices.json) ===")
        try:
            with open(self.model.json_file, 'r') as f:
                data = json.load(f)
                print(f"{'Host Name':<20} {'IP Address':<15} {'MAC Address':<20} {'Interface':<15} {'Status':<10}")
                print("-" * 85)
                for device in data['devices']:
                    print(f"{device['name']:<20} {device['ip']:<15} {device['mac_address']:<20} "
                          f"{device['interface']:<15} {device['status']:<10}")
        except Exception as e:
            print(f"Error reading devices.json: {e}")
        print()


@app.route('/api/devices', methods=['GET'])
def get_devices():
    try:
        model = NetworkModel()
        with open(model.json_file, 'r') as f:
            data = json.load(f)
        return jsonify({"devices": data.get('devices', [])})
    except FileNotFoundError:
        return jsonify({"devices": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices', methods=['POST'])
def add_device():
    try:
        data = request.json
        if not data or 'name' not in data or 'ip' not in data:
            return jsonify({"error": "Name and IP are required"}), 400
            
        model = NetworkModel()
        success = model.register_device(data['name'], data['ip'])
        if success:
            return jsonify({"message": "Device added successfully"}), 201
        return jsonify({"error": "Device already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices/<name>', methods=['DELETE'])
def delete_device(name):
    try:
        model = NetworkModel()
        if name in model.devices:
            model.delete_device(name)
            return jsonify({"message": "Device deleted successfully"})
        return jsonify({"error": "Device not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices/<name>/ping', methods=['GET'])
def ping_device(name):
    try:
        model = NetworkModel()
        if name in model.devices:
            ip = model.devices[name]['ip']
            status = model.ping_device(ip)
            return jsonify({"status": status})
        return jsonify({"error": "Device not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/network-status', methods=['GET'])
def get_network_status():
    try:
        model = NetworkModel()
        model.test_ping_devices()
        model.fetch_actual_bandwidth()
        model.simulate_bandwidth()
        
        return jsonify({
            "pingStatus": model.data["ping_status"],
            "interfaceData": model.data["interface_data"],
            "bandwidthTrends": model.data["bandwidth_trends"],
            "alerts": model.data["alerts"][-5:]  # Get last 5 alerts
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/network/bandwidth', methods=['GET'])
def get_bandwidth_data():
    try:
        model = NetworkModel()
        model.fetch_actual_bandwidth()
        return jsonify(model.data["interface_data"])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/network/alerts', methods=['GET'])
def get_alerts():
    try:
        model = NetworkModel()
        return jsonify({"alerts": model.data["alerts"][-5:]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    try:
        model = NetworkModel()
        model.test_ping_devices()
        model.fetch_actual_bandwidth()
        
        # Calculate dashboard statistics
        total_devices = len(model.devices)
        active_devices = sum(1 for status in model.data["ping_status"].values() if status == "up")
        
        # Calculate total bandwidth
        total_bandwidth = sum(
            float(data.get("input_rate", 0)) + float(data.get("output_rate", 0))
            for data in model.data["interface_data"].values()
        ) / 1000  # Convert to Mbps
        
        return jsonify({
            "totalDevices": total_devices,
            "activeDevices": active_devices,
            "totalBandwidth": round(total_bandwidth, 2),
            "recentAlerts": model.data["alerts"][-5:]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hosts', methods=['GET'])
def get_hosts():
    try:
        url = "http://localhost:58000/api/v1/host"
        headers = {"X-Auth-Token": "NC-102-e202ec415c014cd59dd1-nbi"}
        
        resp = requests.get(url, headers=headers, verify=False)
        if resp.status_code == 200:
            hosts = resp.json().get("response", [])
            formatted_hosts = []
            for host in hosts:
                formatted_hosts.append({
                    "hostName": host.get("hostName", "Unknown"),
                    "hostIp": host.get("hostIp", "Unknown"),
                    "hostMac": host.get("hostMac", "Unknown"),
                    "connectedInterfaceName": host.get("connectedInterfaceName", "Unknown")
                })
            return jsonify({"hosts": formatted_hosts})
        else:
            return jsonify({"error": f"Failed to fetch hosts: {resp.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
