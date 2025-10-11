import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

try:
    import config
    GOOGLE_BROWSER_KEY = getattr(config, "GOOGLE_BROWSER_KEY", "")
    GOOGLE_SERVER_KEY = getattr(config, "GOOGLE_SERVER_KEY", None)
except ImportError:
    GOOGLE_BROWSER_KEY = os.getenv("GOOGLE_BROWSER_KEY", "")
    GOOGLE_SERVER_KEY = os.getenv("GOOGLE_SERVER_KEY")

from bridge import fastest_crossing

@app.route("/")
def index():
    return render_template("index.html", GOOGLE_BROWSER_KEY=GOOGLE_BROWSER_KEY)

@app.post("/api/best-crossing")
def api_best_crossing():
    data = request.get_json(force=True)
    try:
        origin = (float(data["origin"]["lat"]), float(data["origin"]["lng"]))
        dest   = (float(data["destination"]["lat"]), float(data["destination"]["lng"]))
        mode   = data.get("mode", "standard")
    except Exception:
        return jsonify({"error": "Invalid JSON payload"}), 400

    if not GOOGLE_SERVER_KEY:
        return jsonify({"error": "Server key not configured"}), 500

    try:
        result = fastest_crossing(origin, dest, mode, GOOGLE_SERVER_KEY)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(debug=True)
