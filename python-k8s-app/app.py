from flask import Flask, jsonify
import os
import socket
import datetime

app = Flask(__name__)

APP_VERSION = "1.0.0"


@app.route("/")
def home():
    return jsonify({
        "message": "Hello from your Python app running in Kubernetes!",
        "hostname": socket.gethostname(),
        "version": APP_VERSION,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })


@app.route("/health")
def health():
    # Used by Kubernetes liveness/readiness probes
    return jsonify({"status": "healthy"}), 200


@app.route("/info")
def info():
    return jsonify({
        "hostname": socket.gethostname(),
        "env": os.environ.get("APP_ENV", "development"),
        "version": APP_VERSION
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
