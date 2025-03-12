import requests
import json

access_token = "APP_USR-6609597774372079-022200-35bfd03e084edcbc9e182e4c59791183-534685691"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Teste simples para verificar o token
response = requests.get("https://api.mercadopago.com/users/me", headers=headers)
print(f"Status: {response.status_code}")
print(f"Resposta: {response.text}")