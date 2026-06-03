"""Protected demo server — serves time-limited, copy-protected restaurant sites"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, send_from_directory, abort, request, jsonify, render_template_string
from datetime import datetime
import db

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()}), 200

@app.route("/")
def home():
    return jsonify({
        "status": "Restaurant AI Demo Server",
        "endpoints": {
            "/demo/<token>": "View protected restaurant demo",
            "/health": "Health check"
        }
    })

@app.route("/demo/<token>")
def view_demo(token):
    """Serve a protected demo site by token"""
    site = db.get_demo_by_token(token)
    if not site:
        return render_template_string("""
        <!DOCTYPE html>
        <html><head><title>Not Found</title>
        <style>body{font-family:system-ui;background:#050505;color:#888;display:flex;align-items:center;justify-content:center;height:100vh;text-align:center;padding:20px}
        h1{font-weight:300;color:#fff;font-size:2rem} .small{font-size:0.85rem}</style>
        </head>
        <body>
        <div>
            <h1>Link not found</h1>
            <p class="small">This demo link is invalid or has expired.</p>
        </div>
        </body></html>
        """), 404
    
    # Check if the lead's demo has an expiry
    lead = db.get_db().execute(
        "SELECT demo_expires_at, demo_viewed FROM leads WHERE id = ?",
        (site["lead_id"],)
    ).fetchone()
    
    if lead and lead["demo_expires_at"]:
        try:
            expires = datetime.fromisoformat(lead["demo_expires_at"])
            if datetime.now() > expires:
                return render_template_string("""
                <!DOCTYPE html>
                <html><head><title>Expired</title>
                <style>body{font-family:system-ui;background:#050505;color:#888;display:flex;align-items:center;justify-content:center;height:100vh;text-align:center;padding:20px}
                h1{font-weight:300;color:#f0c040;font-size:2rem} .small{font-size:0.85rem} .btn{display:inline-block;margin-top:20px;padding:12px 28px;background:#f0c040;color:#000;text-decoration:none;border-radius:8px;font-weight:600}</style>
                </head>
                <body>
                <div>
                    <h1>Demo Expired ✌️</h1>
                    <p class="small">This preview link has expired. Contact the owner to request a new one.</p>
                </div>
                </body></html>
                """), 410
        except ValueError:
            pass
    
    # Mark as viewed
    if lead:
        db.get_db().execute("UPDATE leads SET demo_viewed = 1 WHERE id = ?", (site["lead_id"],))
        db.get_db().commit()
    
    html = site["html_content"]
    return render_template_string(html)

@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Demo server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
