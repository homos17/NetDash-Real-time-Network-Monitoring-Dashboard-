from flask import Flask, jsonify
from flask_cors import CORS
from back import get_devices  # كود الـ DNA Center API simulation
from ping import NetworkModel  # كود البينج على الشبكة الحقيقية

app = Flask(__name__)
CORS(app)

# Endpoint 1: Get simulated devices (from Cisco DNA API or REST simulation)
@app.route('/api/devices', methods=['GET'])
def devices():
    try:
        data = get_devices()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint 2: Ping devices on real home network
@app.route('/api/ping', methods=['GET'])
def ping():
    try:
        model = NetworkModel()
        data = model.get_status()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint 3: Combine both sources (simulated + real network)
@app.route('/api/all', methods=['GET'])
def all_data():
    try:
        model = NetworkModel()
        real_data = model.get_status()
        simulated_data = get_devices()
        return jsonify({
            "simulated_devices": simulated_data,
            "real_network": real_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
