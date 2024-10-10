import requests
import json, os
import asyncio
from fastapi import FastAPI
import websockets
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import ssl
from fastapi.templating import Jinja2Templates
from fastapi import Request
load_dotenv()

call_details = {}
templates = Jinja2Templates(directory="templates")

# Lifespan handler per gestire l'avvio e lo spegnimento dell'applicazione
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Avvio del task per ascoltare gli eventi WebSocket
    print("Avvio del task WebSocket")
    websocket_task = asyncio.create_task(listen_to_yeastar_events())
    yield
    # Spegnimento: cancellazione del task WebSocket
    websocket_task.cancel()
    
app = FastAPI(lifespan=lifespan)

WEBSOCKET_URL = f"wss://{os.getenv('HOST')}"

headers = {
    "Content-Type": "application/json",
    "User-Agent": "OpenAPI",
}

def read_token():
    with open("token_access.json", "r") as f:
        token = json.load(f)["access_token"]
        f.close()
    return token

# Funzione per ascoltare gli eventi del WebSocket
async def listen_to_yeastar_events():
    token = read_token()
    endpoint_ws = f"{WEBSOCKET_URL}/openapi/v1.0/subscribe?access_token={token}"
    print(f"Connessione al WebSocket: {endpoint_ws}")
    
    # Se necessario, usa SSL context. Qui è disabilitato.
    ssl_context = ssl._create_unverified_context()
    
    try:
        # Connessione al WebSocket
        async with websockets.connect(endpoint_ws, ssl=ssl_context) as websocket:
            # Invia la lista degli argomenti a cui ti vuoi abbonare
            topic_list = {"topic_list": [30011]}
            await websocket.send(json.dumps(topic_list))
            print("Topic list inviato")

            # Invia heartbeat ogni 50 secondi
            async def send_heartbeat():
                while True:
                    await asyncio.sleep(50)  # 60s timeout
                    await websocket.send("heartbeat")
                    print("Heartbeat inviato")

            asyncio.create_task(send_heartbeat())
    
            while True:
                print("In attesa di eventi...")
                try:
                    event = await websocket.recv()
                    print(event)
                    event: dict = json.loads(event)
                    if event.get("msg"):
                        msg = json.loads(event.get("msg"))
                        members = msg.get("members")
                        if members:
                            for member in members:
                                data = member.get("inbound")
                                if data.get("member_status") == "RING" or data.get("member_status") == "ALERT":      
                                    with open("events.json", "a+") as f:
                                        json.dump(event, f)
                except websockets.ConnectionClosed:
                    print("Connessione WebSocket chiusa")
                    break
                except json.JSONDecodeError:
                    print("Errore nel decodificare il messaggio")
                except Exception as e:
                    print(f"Errore durante la ricezione del messaggio: {e}")
    except Exception as e:
        print(f"Errore nella connessione WebSocket: {e.with_traceback(None)}")

async def refresh_token():
    asyncio.sleep(25*60)
    asyncio.create_task(create_token())
    
@app.get("/")
async def root():
    return {"message": "WebSocket monitor running"}

@app.get("/token")
def create_token():
    response = requests.post(
        f"{os.getenv('HOST')}/openapi/v1.0/get_token",
        headers=headers,
        json={"username": os.getenv("CLIENT_ID"), "password": os.getenv("CLIENT_SECRET")},
        verify=False
    )
    return response.json()

@app.get("/contacts")
def read_contacts():
    token = read_token()
    response = requests.get(f"{os.getenv('HOST')}/openapi/v1.0/company_contact/list?access_token={token}", headers=headers, verify=False)
    return response.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)