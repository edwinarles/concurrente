"""
Cliente Móvil / Terminal interactivo para Dog Messenger.
Diseñado para correr en dispositivos móviles (Termux/SSH) o terminales remotos en LAN/WiFi.
Usa exclusivamente sockets TCP nativos. Soporta visualización de QR en ASCII.
"""

import socket
import sys
import time
import threading
from src.consensus.protocol import send_msg, recv_msg
from src.crypto.e2ee import DogE2EE
from src.client.qr_code import DogQR
from src.server.config import CLUSTER_NODES, DEFAULT_E2EE_KEY

class MobileDogClient:
    def __init__(self, client_id: str = "Móvil_0812", node: str = "node1"):
        self.client_id = client_id
        self.node = node
        self.sock = None
        self.running = True
        self.current_group = "general"
        self.e2ee_key = DEFAULT_E2EE_KEY
        self.e2ee = True

    def connect(self):
        cfg = CLUSTER_NODES[self.node]
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((cfg["host"], cfg["client_port"]))
        print(f"🐶 [Dog Mobile] Conectado exitosamente al nodo {self.node} ({cfg['host']}:{cfg['client_port']})")

    def run_cli(self):
        self.connect()
        print("\n" + "="*50)
        print(f"      DOG MESSENGER MÓVIL (Cliente: {self.client_id})")
        print("Comandos: /msg <texto>, /grupo <nombre>, /sync, /qr, /salir")
        print("="*50 + "\n")
        
        while self.running:
            try:
                line = input(f"[{self.current_group}] {self.client_id} > ").strip()
                if not line:
                    continue
                if line == "/salir":
                    break
                elif line == "/sync":
                    self.sync_messages()
                elif line == "/qr":
                    self.show_clone_qr()
                elif line.startswith("/grupo "):
                    self.current_group = line.split(" ", 1)[1].strip()
                    print(f"Cambiado al grupo: {self.current_group}")
                else:
                    self.send_message(line)
            except (KeyboardInterrupt, EOFError):
                break
        self.sock.close()

    def send_message(self, text: str):
        content = DogE2EE.encrypt(text, self.e2ee_key) if self.e2ee else text
        req = {
            "action": "SEND_MESSAGE",
            "sender": self.client_id,
            "group": self.current_group,
            "content": content,
            "encrypted": self.e2ee
        }
        send_msg(self.sock, req)
        resp = recv_msg(self.sock, timeout=4.0)
        if resp and resp.get("status") == "SUCCESS":
            print("  ✔ Replicado por consenso en el clúster.")
        else:
            print(f"  ❌ Error: {resp.get('error') if resp else 'Sin respuesta'}")

    def sync_messages(self):
        req = {"action": "GET_MESSAGES", "group": self.current_group}
        send_msg(self.sock, req)
        resp = recv_msg(self.sock, timeout=4.0)
        if resp and resp.get("status") == "SUCCESS":
            print(f"\n--- Historial Consensuado Grupo [{self.current_group}] ---")
            for m in resp.get("messages", []):
                content = m["content"]
                if m.get("encrypted"):
                    content = DogE2EE.decrypt(content, self.e2ee_key)
                print(f"[{m['sender']}] {content}")
            print("--------------------------------------------------\n")

    def show_clone_qr(self):
        req = {"action": "CLONE_INIT", "client_id": self.client_id}
        send_msg(self.sock, req)
        resp = recv_msg(self.sock, timeout=4.0)
        if resp and resp.get("status") == "SUCCESS":
            token = resp.get("clone_token")
            print("\n" + DogQR.generate_ascii_qr(token))
            print(f"\nToken de sincronización QR: {token}\n")

if __name__ == "__main__":
    cid = sys.argv[1] if len(sys.argv) > 1 else "Móvil_0812"
    target = sys.argv[2] if len(sys.argv) > 2 else "node1"
    client = MobileDogClient(client_id=cid, node=target)
    client.run_cli()
