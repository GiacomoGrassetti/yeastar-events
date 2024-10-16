import requests
import json, os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import websockets
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import logging
import ssl

load_dotenv()

# Lifespan handler per gestire l'avvio e lo spegnimento dell'applicazione
@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_token()
    print("Token created")

    # Avvio del task per ascoltare gli eventi WebSocket
    print("Avvio del task WebSocket")
    websocket_task = asyncio.create_task(listen_to_yeastar_events())
    refresh_token_task = asyncio.create_task(refresh_token())

    yield
    # Spegnimento: cancellazione del task WebSocket
    websocket_task.cancel()
    refresh_token_task.cancel()

# APP configuration
app = FastAPI(lifespan=lifespan)
origins = ['*']
app.add_middleware(
CORSMiddleware,
allow_origins=origins,
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
)
logging.basicConfig(level=logging.INFO)

WEBSOCKET_URL = f"wss://{os.getenv('WS_HOST')}"

headers = {
    "Content-Type": "application/json",
    "User-Agent": "OpenAPI",
}

print(f"Host: {os.getenv('HOST')}\nWS Host: {WEBSOCKET_URL}\nClient ID: {os.getenv('CLIENT_ID')}\nClient Secret: {os.getenv('CLIENT_SECRET')}")

def read_token():
    with open("token_access.json", "r") as f:
        token = json.load(f)["access_token"]
        f.close()
    return token

# Funzione per ascoltare gli eventi del WebSocket
async def listen_to_yeastar_events():
    token = read_token()
    endpoint_ws = f"{WEBSOCKET_URL}/openapi/v1.0/subscribe?access_token={token}"
    logging.info(f"Connessione al WebSocket: {WEBSOCKET_URL}")

    # Se necessario, usa SSL context. Qui è disabilitato.
    ssl_context = ssl._create_unverified_context()

    try:
        # Connessione al WebSocket
        async with websockets.connect(endpoint_ws, ssl=ssl_context) as websocket:
            # Invia la lista degli argomenti a cui ti vuoi abbonare
            topic_list_env = os.getenv("TOPIC_LIST")
            if topic_list_env:
                topic_list = list(map(int, topic_list_env.split(",")))
            else:
                topic_list = []
                logging.warning("TOPIC_LIST environment variable is not set.")
            topic_list = {"topic_list": topic_list}
            await websocket.send(json.dumps(topic_list))
            logging.info("Topic list inviato")

            # Invia heartbeat ogni 50 secondi
            async def send_heartbeat():
                while True:
                    await asyncio.sleep(50)  # 60s timeout
                    await websocket.send("heartbeat")
            asyncio.create_task(send_heartbeat())
            
            while True:
                logging.info("In attesa di eventi...")
                try:
                    raw_event: str | bytes = await websocket.recv()
                    output = {}
                    event_str = raw_event.decode('utf-8') if isinstance(raw_event, bytes) else raw_event
                    if "heartbeat" in event_str:
                        logging.info("Heartbeat ricevuto")
                    else:
                        event: dict = json.loads(event_str)
                        if event.get("msg"):
                            msg: dict = json.loads(event.get("msg"))
                            print(msg)
                            # TODO invio dati al  loro endpoint
                            #if msg.get("members"):
                            #    members = msg.get("members")
                            #    if len(members) == 2:
                            #        print(members)
                                    #inbound = member.get("inbound")
                                    #extension = member.get("extension")
                                    #output["from"] = inbound.get("from")
                                    #output["to"] = inbound.get("to")
                                    #output["ext_number"] = extension.get("number")
                                    #print(output)
                                    
                                    #    inbound: dict = member.get("inbound")
                                    #    extension: dict = member.get("extension")
                                    #    #if inbound.get("member_status") == "ALERT" or extension.get("member_status") == "ALERT":
                                    #    output["from"] = inbound.get("from")
                                    #    output["to"] = inbound.get("to")
                                    #    output["ext_number"] = extension.get("number")
                                    #    print(output)
                                #        data: dict = member.get("inbound")
                                #        if data.get("member_status") == "ALERT":
                                #            output["inbound"] = data
                                #    if member.get("outbound"):
                                #        data: dict = member.get("outbound")
                                #        if data.get("member_status") == "ALERT":
                                #            output["outbound"] = data
                              
                except websockets.ConnectionClosed:
                    logging.error("Connessione WebSocket chiusa")
                    break
                except json.JSONDecodeError as e:
                    logging.error(f"Errore nel decodificare il messaggio: {e}")
                except Exception as e:
                    logging.error(f"Errore durante la ricezione del messaggio: {e}")
    except Exception as e:
        logging.error(f"Errore nella connessione WebSocket: {e.with_traceback(None)}")
    
@app.get("/")
async def root():
    return {"message": "WebSocket monitor running"}

@app.get("/token")
async def create_token():
    print(f"Host: {os.getenv('HOST')}"),
    response = requests.post(
        f"{os.getenv('HOST')}/openapi/v1.0/get_token",
        headers=headers,
        json={"username": os.getenv("CLIENT_ID"), "password": os.getenv("CLIENT_SECRET")},
        verify=False
    )
    with open("token_access.json", "w") as f:
        json.dump(response.json(), f)
        f.close()
    return response.json()

@app.get("/contacts")
def read_contacts():
    token = read_token()
    response = requests.get(f"{os.getenv('HOST')}/openapi/v1.0/company_contact/list?access_token={token}", headers=headers, verify=False)
    return response.json()

async def refresh_token():
    while True:
        await asyncio.sleep(1500)  # 25 minuti (25 * 60 secondi)
        token = await create_token()
        with open("token_access.json", "w") as f:
            json.dump(token, f)
            f.close()
        logging.info("Token refreshed")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)