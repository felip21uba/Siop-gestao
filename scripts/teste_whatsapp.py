import requests
import streamlit as st

def enviar_teste():
    url = f"{st.secrets['EVOLUTION_API_URL']}/message/sendText/{st.secrets['EVOLUTION_INSTANCE']}"
    headers = {
        "apikey": st.secrets["EVOLUTION_API_KEY"],
        "Content-Type": "application/json"
    }
    payload = {
        "number": "5532999999999", # Coloque seu numero completo com DDD
        "text": "🚨 *TESTE SIOP:* Integração com WhatsApp realizada com sucesso!"
    }
    
    resp = requests.post(url, json=payload, headers=headers)
    print("Status:", resp.status_code)
    print("Resposta:", resp.text)

if __name__ == "__main__":
    enviar_teste()