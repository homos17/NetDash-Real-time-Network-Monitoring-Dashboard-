import time
import subprocess
import logging
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Model: Handles data collection and storage
class NetworkModel:
    def __init__(self):
        """Initialize the network model."""
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
            "interface_data": {},
            "bandwidth_trends": {},
            "alerts": []
        }
    def ping_device(self, ip: str) -> str:
        """Ping a device and return 'up' if reachable, otherwise 'down'."""
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
        """Ping all devices and update their status."""
        for name, info in self.devices.items():
            status = self.ping_device(info["ip"])
            self.data["ping_status"][name] = status
            logging.info(f"{name} ({info['ip']}) is {status}")
            if status == "down":
                alert = f"{name} is DOWN at {time.strftime('%H:%M:%S')}"
                self.data["alerts"].append(alert)

    # def get_real_bandwidth(self):
    #     try:
    #         with ConnectHandler(**self.router) as ssh:
    #             # snapshot 1
    #             output1 = ssh.send_command("cat /proc/net/dev")
    #             rates1 = self._parse_proc_net_dev(output1)
    #             time.sleep(1)  # انتظر ثانية واحدة لقياس السرعة
    #             # snapshot 2
    #             output2 = ssh.send_command("cat /proc/net/dev")
    #             rates2 = self._parse_proc_net_dev(output2)

    #             # حساب السرعة من الفرق بين القراءتين
    #             for iface in rates1:
    #                 if iface in rates2:
    #                     rx_diff = rates2[iface]['rx'] - rates1[iface]['rx']
    #                     tx_diff = rates2[iface]['tx'] - rates1[iface]['tx']
    #                     rx_rate_mbps = rx_diff * 8 / 1_000_000  # تحويل لـ Mbps
    #                     tx_rate_mbps = tx_diff * 8 / 1_000_000

    #                     # سجل البيانات
    #                     if iface not in self.data["bandwidth_trends"]:
    #                         self.data["bandwidth_trends"][iface] = []

    #                     self.data["bandwidth_trends"][iface].append((rx_rate_mbps, tx_rate_mbps))

    #                     # احتفظ بآخر 10 قراءات
    #                     if len(self.data["bandwidth_trends"][iface]) > 10:
    #                         self.data["bandwidth_trends"][iface].pop(0)

    #     except Exception as e:
    #         self.data["alerts"].append(f"Bandwidth fetch error: {e}")
    #         logging.error(f"Bandwidth fetch error: {e}")

    # def poll_router_interface_data(self):
    #     """Fetch router interface data via SSH using Netmiko."""
    #     try:
    #         connection = ConnectHandler(**self.router)
    #         output = connection.send_command("show ip interface brief")
    #         logging.info("Raw router output:\n" + output)  # Log the raw output
    #         self.data["interface_data"] = self._parse_interface_data(output)
    #         connection.disconnect()
    #     except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
    #         logging.error(f"SSH to router failed: {e}")
    #     except Exception as e:
    #         logging.error(f"Unexpected error fetching router data: {e}")

    # def _parse_interface_data(self, output: str) -> Dict[str, Dict[str, str]]:
    #     """Parse 'show ip interface brief' output."""
    #     lines = output.strip().splitlines()[1:]  # Skip header
    #     parsed = {}
    #     for line in lines:
    #         parts = line.split()
    #         logging.debug(f"Parsing line: {line}")
    #         if len(parts) >= 6:
    #             iface, ip, _, _, status, protocol = parts[:6]
    #             parsed[iface] = {
    #                 "ip": ip,
    #                 "status": status,
    #                 "protocol": protocol
    #             }
    #     return parsed
    

    def poll_data(self):
        self.test_ping_devices()
        #self.get_real_bandwidth()
        #self.poll_router_interface_data()



class NetworkController:
    def __init__(self, model: NetworkModel):
        self.model = model

    def display_data(self):
        """Display network data in the terminal with periodic updates."""
        try:
            while True:
                self.model.poll_data()
                self._display_ping_status()
                # self._display_interface_data()
                # self._display_bandwidth_trends()
                self._display_alerts()
                time.sleep(10)
        except KeyboardInterrupt:
            logging.info("Exiting program...")

    def _display_ping_status(self):
        print("=== Ping Status ===")
        for device, status in self.model.data["ping_status"].items():
            print(f"{device:<10}: {'UP' if status == 'up' else 'DOWN'}")
        print()

    # def _display_interface_data(self):
    #     print("=== Router Interface Data ===")
    #     print(f"{'Interface':<20} {'IP Address':<15} {'Status':<10} {'Protocol':<10}")
    #     print("-" * 55)
    #     for intf, info in self.model.data["interface_data"].items():
    #         print(f"{intf:<20} {info['ip']:<15} {info['status']:<10} {info['protocol']:<10}")
    #     if not self.model.data["interface_data"]:
    #         print("No interface data available.")
    #     print()

    # def _display_bandwidth_trends(self):
    #     print("=== Bandwidth Usage (Mbps) per Interface ===")
    #     print(f"{'Interface':<15} {'RX Mbps':<10} {'TX Mbps':<10} {'Avg RX':<10} {'Avg TX':<10}")
    #     print("-" * 60)
    #     for iface, values in self.model.data["bandwidth_trends"].items():
    #         if not values:
    #             continue
    #         rx, tx = values[-1]
    #         avg_rx = sum(v[0] for v in values) / len(values)
    #         avg_tx = sum(v[1] for v in values) / len(values)
    #         print(f"{iface:<15} {rx:<10.2f} {tx:<10.2f} {avg_rx:<10.2f} {avg_tx:<10.2f}")
    #     print()




    def _display_alerts(self):
        print("=== Alerts ===")
        if not self.model.data["alerts"]:
            print("No alerts at this time.")
        else:
            for alert in self.model.data["alerts"][-5:]:
                print(f"Alert: {alert}")
        print()


if __name__ == "__main__":
    model = NetworkModel()
    controller = NetworkController(model)
    controller.display_data()