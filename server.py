import os
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app)  # Permite peticiones CORS desde el frontend

# ===================================================================
# 🔑 CONFIGURACIÓN DE TUS CREDENCIALES DE MERCADO PAGO
# ===================================================================
CLIENT_ID = os.getenv("MP_CLIENT_ID", "8967740339323403")
CLIENT_SECRET = os.getenv("MP_CLIENT_SECRET", "sXpFGTYAYnQwCLDBhy9dU7enSG3t3vgu")
BASE_URL = os.getenv("BASE_URL", "https://mar-web.netlify.app")
SERVER_URL = os.getenv("SERVER_URL", "https://mi-servidor-python-production.up.railway.app")

REDIRECT_URI = f"{SERVER_URL}/api/auth/mercadopago/callback"
MARGIN_RATE = 0.025  # 2.5% Comisión MAR

# Base de datos local simulada en memoria
sellers_db = {}

# Ruta de prueba para verificar que Railway está encendido
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "online", "service": "Backend MAR activo"}), 200


# -------------------------------------------------------------------
# 1. ENDPOINT: VINCULACIÓN OAUTH (PLANTA DE PROCESAMIENTO)
# -------------------------------------------------------------------
@app.route('/api/auth/mercadopago/connect/<plant_id>', methods=['GET'])
def connect_mercadopago(plant_id):
    mp_auth_url = (
        f"https://auth.mercadopago.com.ar/authorization"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&platform_id=mp"
        f"&state={plant_id}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return redirect(mp_auth_url)


@app.route('/api/auth/mercadopago/callback', methods=['GET'])
def mp_callback():
    code = request.args.get('code')
    plant_id = request.args.get('state')

    if not code:
        return jsonify({"error": "Código de autorización faltante"}), 400

    token_url = "https://api.mercadopago.com/oauth/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    response = requests.post(token_url, data=payload)
    data = response.json()

    if response.status_code == 200:
        sellers_db[plant_id] = {
            "access_token": data.get("access_token"),
            "collector_id": data.get("user_id"),
            "refresh_token": data.get("refresh_token")
        }
        return redirect(f"{BASE_URL}?mp_connected=true&plant={plant_id}")
    else:
        return jsonify({"error": "Error al conectar cuenta de Mercado Pago", "details": data}), 400


# -------------------------------------------------------------------
# 2. ENDPOINT: CREAR PREFERENCIA DE RESERVA (2.5% COMISIÓN MAR)
# -------------------------------------------------------------------
@app.route('/api/create-preference', methods=['POST'])
def create_preference():
    body = request.json or {}
    item_title = body.get('title', 'Reserva de Lote Pesquero')
    net_price = float(body.get('net_price', 0))

    # Cálculo exacto de la seña del 2.5%
    fee_amount = round(net_price * MARGIN_RATE, 2)

    if fee_amount <= 0:
        return jsonify({"error": "Monto de reserva inválido"}), 400

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
    }

    headers = {
        "Authorization": f"Bearer {CLIENT_SECRET}",
        "Content-Type": "application/json"
    }

    try:
        mp_res = requests.post(
            "https://api.mercadopago.com/checkout/preferences",
            headers=headers,
            data=json.dumps(preference_data)
        )

        if mp_res.status_code in [200, 201]:
            res_data = mp_res.json()
            return jsonify({
                "preference_id": res_data["id"],
                "init_point": res_data["init_point"],
                "fee_amount": fee_amount
            })
        else:
            return jsonify({"error": "Error al comunicar con la pasarela", "details": mp_res.json()}), 400

    except Exception as e:
        return jsonify({"error": "Error de servidor interno", "details": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Servidor Backend MAR iniciado en el puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)