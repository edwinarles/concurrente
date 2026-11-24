"""
Interfaz gráfica de escritorio Dog Messenger (Tkinter).
Reproduce el diseño visual solicitado en la práctica:
- Barra azul "Dog Messenger"
- Mascota Doge con escudo
- Usuario Validado / idClientChat
- Grupos de chat con consistencia
- Envío de texto, imágenes y archivos
- Cifrado E2EE punto a punto
- Clonación de chats vía QR con sincronización de estado
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import socket
import threading
import time
import base64
import os
import random
from typing import Optional, List, Dict, Any

from src.consensus.protocol import send_msg, recv_msg
from src.crypto.e2ee import DogE2EE
from src.client.qr_code import DogQR
from src.server.config import CLUSTER_NODES, DEFAULT_E2EE_KEY

class DogMessengerGUI:
    def __init__(self, root: tk.Tk, client_id: Optional[str] = None, target_node: str = "node1"):
        self.root = root
        self.client_id = client_id or f"idClientChat {random.randint(1000, 9999)}"
        self.username = f"Usuario_{self.client_id.split()[-1]}"
        self.current_node = target_node
        self.e2ee_key = DEFAULT_E2EE_KEY
        self.e2ee_enabled = True
        self.current_group = "general"
        
        self.sock: Optional[socket.socket] = None
        self.connected = False
        self.messages_seen = 0
        self.running = True
        
        # Configuración de ventana
        self.root.title("Dog Messenger - CC4P1")
        self.root.geometry("450, 720")
        self.root.minsize(400, 650)
        self.root.configure(bg="#F0F4F8")
        
        self._build_ui()
        self._connect_to_node(self.current_node)
        
        # Hilo de sincronización periódica
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()

    def _build_ui(self):
        # 1. Barra superior azul
        header = tk.Frame(self.root, bg="#0066B3", height=50)
        header.pack(fill=tk.X, side=tk.TOP)
        lbl_title = tk.Label(header, text="Dog Messenger", font=("Arial", 16, "bold"), bg="#0066B3", fg="white")
        lbl_title.pack(side=tk.LEFT, padx=15, pady=10)
        
        # Selector de nodo conectado
        self.node_var = tk.StringVar(value=self.current_node)
        node_menu = ttk.Combobox(header, textvariable=self.node_var, values=list(CLUSTER_NODES.keys()), width=8, state="readonly")
        node_menu.pack(side=tk.RIGHT, padx=10, pady=10)
        node_menu.bind("<<ComboboxSelected>>", self._on_node_change)

        # 2. Panel de usuario y mascota
        user_panel = tk.Frame(self.root, bg="white", bd=1, relief=tk.SOLID)
        user_panel.pack(fill=tk.X, padx=10, pady=8)
        
        # Cargar imagen de Doge con escudo si existe
        mascot_path = os.path.join("assets", "doge_shield.png")
        if os.path.exists(mascot_path):
            try:
                pil_img = Image.open(mascot_path).resize((70, 70), Image.Resampling.LANCZOS)
                self.mascot_photo = ImageTk.PhotoImage(pil_img)
                lbl_mascot = tk.Label(user_panel, image=self.mascot_photo, bg="white")
                lbl_mascot.pack(side=tk.LEFT, padx=8, pady=5)
            except Exception:
                pass
                
        info_frame = tk.Frame(user_panel, bg="white")
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(info_frame, text="Usuario Validado", font=("Arial", 10, "bold"), fg="#008000", bg="white").pack(anchor="w")
        self.lbl_client_id = tk.Label(info_frame, text=self.client_id, font=("Arial", 10), fg="#333333", bg="white")
        self.lbl_client_id.pack(anchor="w")
        
        self.lbl_node_status = tk.Label(info_frame, text="Conectando al clúster...", font=("Arial", 8), fg="#666666", bg="white")
        self.lbl_node_status.pack(anchor="w")
        
        # Botón de Clonación QR
        btn_qr = tk.Button(user_panel, text="📱 Clonar QR", font=("Arial", 8, "bold"), bg="#0066B3", fg="white",
                           command=self._open_clone_window, relief=tk.FLAT, padx=6, pady=3)
        btn_qr.pack(side=tk.RIGHT, padx=10)

        # 3. Selector de Grupos
        group_frame = tk.Frame(self.root, bg="#E2EBF0")
        group_frame.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(group_frame, text="Grupo:", font=("Arial", 9, "bold"), bg="#E2EBF0").pack(side=tk.LEFT, padx=5)
        
        self.group_var = tk.StringVar(value=self.current_group)
        self.group_combo = ttk.Combobox(group_frame, textvariable=self.group_var, values=["general", "anuncios"], width=12, state="readonly")
        self.group_combo.pack(side=tk.LEFT, padx=5, pady=4)
        self.group_combo.bind("<<ComboboxSelected>>", self._on_group_change)
        
        btn_new_group = tk.Button(group_frame, text="+ Grupo", font=("Arial", 8), bg="#D0DCE5", command=self._prompt_create_group)
        btn_new_group.pack(side=tk.LEFT, padx=5)
        
        # Indicador de E2EE Cifrado
        self.e2ee_btn = tk.Button(group_frame, text="🔒 E2EE: ON", font=("Arial", 8, "bold"), bg="#E6F4EA", fg="#137333",
                                  command=self._toggle_e2ee, relief=tk.GROOVE)
        self.e2ee_btn.pack(side=tk.RIGHT, padx=5)

        # 4. Caja de Historial de Mensajes
        chat_frame = tk.Frame(self.root, bg="white", bd=1, relief=tk.SOLID)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.chat_list = tk.Text(chat_frame, wrap=tk.WORD, font=("Segoe UI", 10), state=tk.DISABLED, bg="#FAFAFA")
        scrollbar = tk.Scrollbar(chat_frame, command=self.chat_list.yview)
        self.chat_list.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Tags de estilo para mensajes
        self.chat_list.tag_config("me", foreground="#004D80", font=("Segoe UI", 10, "bold"))
        self.chat_list.tag_config("other", foreground="#1E7E34", font=("Segoe UI", 10, "bold"))
        self.chat_list.tag_config("system", foreground="#888888", font=("Segoe UI", 9, "italic"))
        self.chat_list.tag_config("badge", foreground="#D9534F", font=("Segoe UI", 8, "bold"))

        # 5. Barra de Entrada y Envío (igual a la imagen de Dog Messenger del PDF)
        input_container = tk.Frame(self.root, bg="#F0F4F8")
        input_container.pack(fill=tk.X, padx=10, pady=8, side=tk.BOTTOM)
        
        # Botones de adjuntos
        attach_frame = tk.Frame(input_container, bg="#F0F4F8")
        attach_frame.pack(fill=tk.X, pady=2)
        
        btn_file = tk.Button(attach_frame, text="📎 Adjuntar Archivo/Imagen", font=("Arial", 8),
                             bg="#E1E8ED", relief=tk.GROOVE, command=self._attach_file)
        btn_file.pack(side=tk.LEFT)
        
        # Input y botón verde con flecha
        send_frame = tk.Frame(input_container, bg="#F0F4F8")
        send_frame.pack(fill=tk.X, pady=3)
        
        self.txt_input = tk.Entry(send_frame, font=("Arial", 11), bd=1, relief=tk.SOLID)
        self.txt_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 6))
        self.txt_input.bind("<Return>", lambda e: self._send_text_message())
        
        btn_send = tk.Button(send_frame, text="▶", font=("Arial", 14, "bold"), bg="#34A853", fg="white",
                             command=self._send_text_message, width=3, relief=tk.RAISED)
        btn_send.pack(side=tk.RIGHT)

    def _connect_to_node(self, node_id: str):
        """Conecta el cliente al socket TCP del nodo de clúster seleccionado."""
        cfg = CLUSTER_NODES.get(node_id)
        if not cfg:
            return
        
        try:
            if self.sock:
                self.sock.close()
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(4.0)
            self.sock.connect((cfg["host"], cfg["client_port"]))
            self.connected = True
            self.current_node = node_id
            self.lbl_node_status.config(text=f"Conectado a {node_id} ({cfg['host']}:{cfg['client_port']})", fg="#008000")
        except Exception as e:
            self.connected = False
            self.lbl_node_status.config(text=f"Fallo conexión con {node_id}", fg="#CC0000")

    def _on_node_change(self, event=None):
        """Cambio de nodo para pruebas de partición, balanceo y recuperación."""
        new_node = self.node_var.get()
        self._connect_to_node(new_node)
        self._refresh_messages()

    def _on_group_change(self, event=None):
        self.current_group = self.group_var.get()
        self.messages_seen = 0
        self._refresh_messages()

    def _toggle_e2ee(self):
        self.e2ee_enabled = not self.e2ee_enabled
        if self.e2ee_enabled:
            self.e2ee_btn.config(text="🔒 E2EE: ON", bg="#E6F4EA", fg="#137333")
        else:
            self.e2ee_btn.config(text="🔓 E2EE: OFF", bg="#FCE8E6", fg="#C5221F")

    def _prompt_create_group(self):
        """Diálogo para crear nuevo grupo."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Crear Grupo de Chat")
        dlg.geometry("300, 130")
        dlg.transient(self.root)
        tk.Label(dlg, text="Nombre del nuevo grupo:").pack(pady=10)
        entry = tk.Entry(dlg)
        entry.pack(pady=5, padx=20, fill=tk.X)
        
        def do_create():
            g_name = entry.get().strip().lower()
            if g_name and self._send_request({"action": "CREATE_GROUP", "group_name": g_name}):
                self.group_combo["values"] = list(self.group_combo["values"]) + [g_name]
                self.group_var.set(g_name)
                self.current_group = g_name
                dlg.destroy()
                
        tk.Button(dlg, text="Crear en Clúster", command=do_create, bg="#0066B3", fg="white").pack(pady=10)

    def _send_request(self, payload: dict) -> Optional[dict]:
        """Envía una petición al nodo conectado."""
        try:
            if not self.connected or not self.sock:
                self._connect_to_node(self.current_node)
            send_msg(self.sock, payload)
            resp = recv_msg(self.sock, timeout=4.0)
            return resp
        except Exception:
            self.connected = False
            return None

    def _send_text_message(self):
        """Envía mensaje de texto a través del consenso del clúster."""
        raw_text = self.txt_input.get().strip()
        if not raw_text:
            return
            
        content_to_send = raw_text
        if self.e2ee_enabled:
            content_to_send = DogE2EE.encrypt(raw_text, self.e2ee_key)
            
        req = {
            "action": "SEND_MESSAGE",
            "sender": self.client_id,
            "group": self.current_group,
            "content": content_to_send,
            "msg_kind": "text",
            "encrypted": self.e2ee_enabled
        }
        
        resp = self._send_request(req)
        if resp and resp.get("status") == "SUCCESS":
            self.txt_input.delete(0, tk.END)
            self._refresh_messages()
        else:
            err = resp.get("error", "Error de red/consenso") if resp else "Sin respuesta del nodo"
            messagebox.showwarning("Aviso de Consenso", f"No se pudo completar consenso: {err}")

    def _attach_file(self):
        """Selecciona y envía archivo o imagen al clúster."""
        file_path = filedialog.askopenfilename()
        if not file_path:
            return
            
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, "rb") as f:
                data_b64 = base64.b64encode(f.read()).decode("ascii")
                
            is_img = file_name.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
            kind = "image" if is_img else "file"
            
            content_desc = f"[{'Imagen' if is_img else 'Archivo'}: {file_name}]"
            if self.e2ee_enabled:
                content_desc = DogE2EE.encrypt(content_desc, self.e2ee_key)
                
            req = {
                "action": "SEND_MESSAGE",
                "sender": self.client_id,
                "group": self.current_group,
                "content": content_desc,
                "msg_kind": kind,
                "file_name": file_name,
                "file_data": data_b64,
                "encrypted": self.e2ee_enabled
            }
            resp = self._send_request(req)
            if resp and resp.get("status") == "SUCCESS":
                self._refresh_messages()
            else:
                messagebox.showerror("Error", "Fallo al replicar archivo vía consenso")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer archivo: {e}")

    def _sync_loop(self):
        """Bucle en segundo plano para refrescar mensajes y estado del clúster."""
        while self.running:
            time.sleep(1.0)
            if self.connected:
                self.root.after(0, self._refresh_messages)
                self.root.after(0, self._update_status)

    def _update_status(self):
        """Consulta métricas de consenso y estado del líder."""
        resp = self._send_request({"action": "GET_STATUS"})
        if resp and resp.get("status") == "SUCCESS":
            algo = resp.get("algorithm", "raft").upper()
            role_desc = "LÍDER 👑" if resp.get("is_leader") else f"SEGUIDOR (Líder: {resp.get('leader_id')})"
            self.lbl_node_status.config(
                text=f"{self.current_node} [{algo}] | {role_desc}",
                fg="#004D80" if resp.get("is_leader") else "#555555"
            )

    def _refresh_messages(self):
        """Consulta el log consensuado y actualiza la ventana de chat."""
        resp = self._send_request({"action": "GET_MESSAGES", "group": self.current_group})
        if not resp or resp.get("status") != "SUCCESS":
            return
            
        msgs = resp.get("messages", [])
        self.chat_list.configure(state=tk.NORMAL)
        self.chat_list.delete("1.0", tk.END)
        
        for m in msgs:
            sender = m.get("sender", "Anon")
            content = m.get("content", "")
            is_encrypted = m.get("encrypted", False)
            
            # Descifrar si aplica E2EE
            if is_encrypted:
                content = DogE2EE.decrypt(content, self.e2ee_key)
                
            is_me = (sender == self.client_id)
            tag = "me" if is_me else "other"
            sender_display = "Yo" if is_me else sender
            
            self.chat_list.insert(tk.END, f"{sender_display}: ", tag)
            self.chat_list.insert(tk.END, f"{content}\n")
            
        self.chat_list.configure(state=tk.DISABLED)
        self.chat_list.see(tk.END)

    def _open_clone_window(self):
        """Abre ventana de clonación con código QR generado dinámicamente."""
        resp = self._send_request({"action": "CLONE_INIT", "client_id": self.client_id})
        if not resp or resp.get("status") != "SUCCESS":
            messagebox.showerror("Error", "No se pudo obtener snapshot de clonación")
            return
            
        token = resp.get("clone_token", "DOG_CLONE_TOKEN")
        snapshot = resp.get("snapshot", {})
        
        qr_win = tk.Toplevel(self.root)
        qr_win.title("Clonar Chat vía QR - Dog Messenger")
        qr_win.geometry("380, 520")
        qr_win.configure(bg="white")
        
        # Header azul
        h = tk.Frame(qr_win, bg="#0066B3", height=40)
        h.pack(fill=tk.X)
        tk.Label(h, text="Sincronización QR", font=("Arial", 12, "bold"), fg="white", bg="#0066B3").pack(pady=8)
        
        tk.Label(qr_win, text="Escanea este código desde otro dispositivo\npara replicar exactamente el historial de mensajes",
                 font=("Arial", 9), bg="white", fg="#555555").pack(pady=10)
                 
        # Generar QR
        qr_img = DogQR.generate_qr_image(token, box_size=6)
        qr_photo = ImageTk.PhotoImage(qr_img)
        
        lbl_qr = tk.Label(qr_win, image=qr_photo, bg="white")
        lbl_qr.image = qr_photo  # Mantener referencia
        lbl_qr.pack(pady=10)
        
        tk.Label(qr_win, text=f"Token de Clonación:\n{token}", font=("Consolas", 8), bg="white", fg="#666666").pack()
        tk.Label(qr_win, text=f"Total Mensajes Replicados: {snapshot.get('total_messages', 0)}", font=("Arial", 9, "bold"),
                 bg="white", fg="#008000").pack(pady=5)
                 
        # Botón para simular importación en segundo dispositivo
        def do_replicate_to_new_client():
            qr_win.destroy()
            new_root = tk.Toplevel(self.root)
            new_client_id = f"idClientChat {random.randint(1000, 9999)} (Clonado)"
            DogMessengerGUI(new_root, client_id=new_client_id, target_node="node2")
            
        tk.Button(qr_win, text="📲 Simular Escaneo en Móvil (Nuevo Cliente)", bg="#34A853", fg="white",
                  font=("Arial", 9, "bold"), command=do_replicate_to_new_client).pack(pady=10)

def launch_gui(client_id: Optional[str] = None, node: str = "node1"):
    root = tk.Tk()
    app = DogMessengerGUI(root, client_id=client_id, target_node=node)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
