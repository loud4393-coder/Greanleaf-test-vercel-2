from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="/static")

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/health")
def health():
    return jsonify(status="ok", app="greenleaf-vercel-test")

@app.route("/api/test")
def api_test():
    return jsonify(status="ok", message="Flask API is working")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
