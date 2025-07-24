import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from subprocess import run, PIPE

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from geopy.distance import geodesic
import uvicorn

from wg_utils import generate_wg_keypair, apply_wg_config

DB_PATH = "./payments.db"
WG_CONFIG_DIR = "./wg_configs"
WG_PORT = 51820

if not os.path.exists(WG_CONFIG_DIR):
    os.makedirs(WG_CONFIG_DIR)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        role TEXT,
        ip TEXT,
        lat REAL,
        lon REAL,
        account TEXT,
        price_per_hour INTEGER,
        private_key TEXT,
        public_key TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS transactions (
        tx_hash TEXT PRIMARY KEY,
        provider_id TEXT,
        borrower_id TEXT,
        start_time TEXT,
        end_time TEXT,
        status TEXT
    )''')
    conn.close()

init_db()

@app.post("/api/register")
async def register_user(request: Request):
    data = await request.json()
    priv, pub = generate_wg_keypair()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
            data['user_id'], data['role'], request.client.host,
            data['lat'], data['lon'], data['account'], data['price_per_hour'],
            priv, pub
        ))
        conn.commit()
        return {"status": "success", "public_key": pub}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="이미 등록된 사용자입니다")

@app.get("/api/providers")
async def get_providers(lat: float, lon: float):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM users WHERE role='provider'").fetchall()
    result = []
    for r in rows:
        dist = geodesic((lat, lon), (r[3], r[4])).km
        if dist <= 2:
            result.append({
                "id": r[0], "account": r[5], "price_per_hour": r[6],
                "lat": r[3], "lon": r[4], "distance": round(dist, 2),
                "public_key": r[8]
            })
    return {"providers": sorted(result, key=lambda x: x['distance'])}

@app.post("/api/request")
async def request_tx(request: Request):
    data = await request.json()
    now = datetime.now()
    end = now + timedelta(minutes=data['duration'])
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?)", (
        data['tx_hash'], data['provider_id'], data['borrower_id'],
        now.isoformat(), end.isoformat(), 'pending')
    )
    conn.commit()
    return {"status": "waiting_approval"}

@app.post("/api/approve")
async def approve_tx(request: Request):
    data = await request.json()
    tx_hash = data['tx_hash']

    conn = sqlite3.connect(DB_PATH)
    tx = conn.execute("SELECT * FROM transactions WHERE tx_hash=?", (tx_hash,)).fetchone()
    if not tx:
        raise HTTPException(status_code=404, detail="거래 없음")

    conn.execute("UPDATE transactions SET status='approved' WHERE tx_hash=?", (tx_hash,))
    conn.commit()

    provider = conn.execute("SELECT ip, private_key, public_key FROM users WHERE id=?", (tx[1],)).fetchone()
    borrower = conn.execute("SELECT ip, private_key, public_key FROM users WHERE id=?", (tx[2],)).fetchone()
    conn.close()

    if not provider or not borrower:
        raise HTTPException(status_code=404, detail="사용자 정보 없음")

    provider_ip, provider_priv, provider_pub = provider
    borrower_ip, borrower_priv, borrower_pub = borrower

    provider_conf_path = os.path.join(WG_CONFIG_DIR, f"{tx_hash}_provider.conf")
    borrower_conf_path = os.path.join(WG_CONFIG_DIR, f"{tx_hash}_borrower.conf")

    provider_vpn_ip = "10.0.0.1/24"
    borrower_vpn_ip = "10.0.0.2/24"

    provider_config = f"""
[Interface]
PrivateKey = {provider_priv}
Address = {provider_vpn_ip}
ListenPort = {WG_PORT}

[Peer]
PublicKey = {borrower_pub}
AllowedIPs = 10.0.0.2/32
"""
    with open(provider_conf_path, "w") as f:
        f.write(provider_config)

    borrower_config = f"""
[Interface]
PrivateKey = {borrower_priv}
Address = {borrower_vpn_ip}

[Peer]
PublicKey = {provider_pub}
Endpoint = {provider_ip}:{WG_PORT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""
    with open(borrower_conf_path, "w") as f:
        f.write(borrower_config)

    stdout, stderr = apply_wg_config(provider_conf_path)
    print(f"WireGuard 설정 적용 stdout: {stdout}\nstderr: {stderr}")

    def auto_stop():
        seconds = (datetime.fromisoformat(tx[4]) - datetime.now()).total_seconds()
        if seconds > 0:
            time.sleep(seconds)
        run(["wg-quick", "down", provider_conf_path], stdout=PIPE, stderr=PIPE)
        if os.path.exists(provider_conf_path):
            os.remove(provider_conf_path)
        if os.path.exists(borrower_conf_path):
            os.remove(borrower_conf_path)
        print(f"VPN 연결 종료: {tx_hash}")

    threading.Thread(target=auto_stop, daemon=True).start()

    return {
        "status": "approved",
        "provider_config": provider_conf_path,
        "borrower_config": borrower_conf_path
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
