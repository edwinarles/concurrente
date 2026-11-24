"""
DogChatStateMachine: Máquina de estados replicada para Dog Messenger.
Mantiene el historial global consistente de mensajes, grupos, usuarios y archivos.
Thread-safe mediante RLock.
"""

import threading
import time
import copy
from typing import List, Dict, Any, Optional

class DogChatStateMachine:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.lock = threading.RLock()
        
        # Historial de mensajes en orden estricto de consenso
        self.messages: List[Dict[str, Any]] = []
        
        # Grupos registrados
        self.groups: set = {"general", "anuncios"}
        
        # Archivos/imágenes almacenados en memoria (hash -> dict con info y bytes base64)
        self.files_storage: Dict[str, Dict[str, Any]] = {}
        
        # Usuarios registrados y claves públicas/sesión
        self.users: Dict[str, Dict[str, Any]] = {}
        
        # Tokens de clonación activos: token -> snapshot data
        self.clone_tokens: Dict[str, Dict[str, Any]] = {}

    def apply(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica un comando acordado por consenso a la máquina de estados."""
        with self.lock:
            cmd_type = command.get("type")
            
            if cmd_type == "NEW_MESSAGE":
                msg_data = {
                    "msg_id": command.get("msg_id", f"msg_{len(self.messages)+1}"),
                    "sender": command.get("sender", "Anon"),
                    "group": command.get("group", "general"),
                    "content": command.get("content", ""),
                    "msg_kind": command.get("msg_kind", "text"),  # text, image, file
                    "file_name": command.get("file_name", None),
                    "file_data": command.get("file_data", None),  # Base64 string
                    "encrypted": command.get("encrypted", False),
                    "timestamp": command.get("timestamp", time.time())
                }
                self.messages.append(msg_data)
                if msg_data["group"] not in self.groups:
                    self.groups.add(msg_data["group"])
                return {"status": "SUCCESS", "msg_id": msg_data["msg_id"], "index": len(self.messages)}

            elif cmd_type == "CREATE_GROUP":
                group_name = command.get("group_name")
                if group_name:
                    self.groups.add(group_name)
                    return {"status": "SUCCESS", "group": group_name}
                return {"status": "ERROR", "message": "Nombre de grupo inválido"}

            elif cmd_type == "REGISTER_USER":
                user_id = command.get("user_id")
                public_key = command.get("public_key")
                self.users[user_id] = {
                    "user_id": user_id,
                    "public_key": public_key,
                    "registered_at": time.time()
                }
                return {"status": "SUCCESS", "user_id": user_id}

            elif cmd_type == "SAVE_FILE":
                file_hash = command.get("file_hash")
                file_name = command.get("file_name")
                file_data = command.get("file_data")
                self.files_storage[file_hash] = {
                    "name": file_name,
                    "data": file_data,
                    "saved_at": time.time()
                }
                return {"status": "SUCCESS", "file_hash": file_hash}

            return {"status": "UNKNOWN_COMMAND"}

    def get_messages(self, group: Optional[str] = None, since_index: int = 0) -> List[Dict[str, Any]]:
        """Obtiene mensajes filtrados por grupo o desde un índice específico."""
        with self.lock:
            all_msgs = self.messages[since_index:]
            if group:
                return [m for m in all_msgs if m.get("group") == group]
            return list(all_msgs)

    def get_groups(self) -> List[str]:
        """Retorna la lista ordenada de grupos disponibles."""
        with self.lock:
            return sorted(list(self.groups))

    def create_clone_snapshot(self, client_id: str) -> Dict[str, Any]:
        """Crea una instantánea completa (snapshot) para clonación vía QR."""
        with self.lock:
            snapshot = {
                "client_id": client_id,
                "timestamp": time.time(),
                "total_messages": len(self.messages),
                "messages": copy.deepcopy(self.messages),
                "groups": list(self.groups),
                "users": copy.deepcopy(self.users)
            }
            return snapshot

    def restore_from_snapshot(self, snapshot: Dict[str, Any]) -> bool:
        """Restaura el estado a partir de un snapshot de clonación verificado."""
        with self.lock:
            self.messages = copy.deepcopy(snapshot.get("messages", []))
            self.groups = set(snapshot.get("groups", ["general"]))
            self.users = copy.deepcopy(snapshot.get("users", {}))
            return True
