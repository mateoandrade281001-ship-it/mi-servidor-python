import os
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app)

# ===================================================================
# 🔑 CONFIGURACIÓN SEGURA (LEE DESDE VARIABLES DE RAILWAY)
# ===================================================================
CLIENT_ID = os.getenv("MP_CLIENT_ID")
CLIENT_SECRET = os.getenv("MP_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
BASE_URL = os.getenv("BASE_URL", "https://mar-web.netlify.app")[cite: 3]
SERVER_URL = os.getenv("SERVER_URL", "https://mi-servidor-python-production.up.railway.app")[cite: 3]

REDIRECT_URI = f"{SERVER_URL}/api/auth/mercadopago/callback"[cite: 3]
MARGIN_RATE = 0.025  # 2.5% Comisión MAR

sellers_db = {}[cite: 3]

@app.route('/', methods=['GET'])[cite: 3]
def health_check():[cite: 3]
    return jsonify({"status": "online", "service": "Backend MAR activo"}), 200[cite: 3]

# -------------------------------------------------------------------
# 1. ENDPOINT: VINCULACIÓN OAUTH (PLANTA DE PROCESAMIENTO)
# -------------------------------------------------------------------
@app.route('/api/auth/mercadopago/connect/<plant_id>', methods=['GET'])[cite: 3]
def connect_mercadopago(plant_id):[cite: 3]
    mp_auth_url = (
        f"https://auth.mercadopago.com.ar/authorization"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&platform_id=mp"
        f"&state={plant_id}"
        f"&redirect_uri={REDIRECT_URI}"
    )[cite: 3]
    return redirect(mp_auth_url)[cite: 3]

@app.route('/api/auth/mercadopago/callback', methods=['GET'])[cite: 3]
def mp_callback():[cite: 3]
    code = request.args.get('code')[cite: 3]
    plant_id = request.args.get('state')[cite: 3]

    if not code:[cite: 3]
        return jsonify({"error": "Código de autorización faltante"}), 400[cite: 3]

    token_url = "https://api.mercadopago.com/oauth/token"[cite: 3]
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }[cite: 3]

    response = requests.post(token_url, data=payload)[cite: 3]
    data = response.json()[cite: 3]

    if response.status_code == 200:[cite: 3]
        sellers_db[plant_id] = {
            "access_token": data.get("access_token"),
            "collector_id": data.get("user_id"),
            "refresh_token": data.get("refresh_token")
        }[cite: 3]
        return redirect(f"{BASE_URL}?mp_connected=true&plant={plant_id}")[cite: 3]
    else:[cite: 3]
        return jsonify({"error": "Error al conectar cuenta de Mercado Pago", "details": data}), 400[cite: 3]

# -------------------------------------------------------------------
# 2. ENDPOINT: CREAR PREFERENCIA DE RESERVA (2.5% COMISIÓN MAR)
# -------------------------------------------------------------------
@app.route('/api/create-preference', methods=['POST'])[cite: 3]
def create_preference():[cite: 3]
    body = request.json or {}[cite: 3]
    item_title = body.get('title', 'Reserva de Lote Pesquero')[cite: 3]
    net_price = float(body.get('net_price', 0))[cite: 3]

    fee_amount = round(net_price * MARGIN_RATE, 2)[cite: 3]

    if fee_amount <= 0:[cite: 3]
        return jsonify({"error": "Monto de reserva inválido"}), 400[cite: 3]

    preference_data = {
        "items": [
            {
                "title": f"Seña / Reserva de Lote MAR (2.5%): {item_title}",
                "quantity": 1,
                "unit_price": fee_amount,
                "currency_id": "ARS"
            }
        ],
        "back_urls": {
            "success": f"{BASE_URL}?payment=success",
            "failure": f"{BASE_URL}?payment=failure"
        },
        "auto_return": "approved"
    }[cite: 3]

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }[cite: 3]

    try:[cite: 3]
        mp_res = requests.post(
            "https://api.mercadopago.com/checkout/preferences",
            headers=headers,
            data=json.dumps(preference_data)
        )[cite: 3]

        if mp_res.status_code in [200, 201]:[cite: 3]
            res_data = mp_res.json()[cite: 3]
            return jsonify({
                "preference_id": res_data["id"],
                "init_point": res_data["init_point"],
                "fee_amount": fee_amount
            })[cite: 3]
        else:[cite: 3]
            return jsonify({"error": "Error al comunicar con la pasarela", "details": mp_res.json()}), 400[cite: 3]

    except Exception as e:[cite: 3]
        return jsonify({"error": "Error de servidor interno", "details": str(e)}), 500[cite: 3]

if __name__ == '__main__':[cite: 3]
    port = int(os.environ.get("PORT", 5000))[cite: 3]
    print(f"🚀 Servidor Backend MAR iniciado en el puerto {port}")[cite: 3]
    app.run(host='0.0.0.0', port=port, debug=False)[cite: 3]