"""
ServerNode: Servidor de mensajería Dog Messenger para cada nodo del clúster.
Integra el motor de consenso (Raft o Multi-Paxos), la StateMachine y la interfaz TCP para clientes.
Cumple estrictamente con el uso exclusivo de Sockets nativos e hilos.
"""

import socket
import threading
import time
import logging
from typing import Dict, Any, Optional
from src.consensus.protocol import send_msg, recv_msg
from src.consensus.state_machine import DogChatStateMachine
from src.consensus.raft_node import RaftNode, ROLE_LEADER
from src.consensus.paxos_node import PaxosNode
from src.server.config import CLUSTER_NODES, DEFAULT_ALGORITHM

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("DogServer")

class DogServerNode:
    def __init__(self, node_id: str, algorithm: str = DEFAULT_ALGORITHM, nodes_config: Dict[str, dict] = CLUSTER_NODES):
        self.node_id = node_id
        self.algorithm = algorithm.lower()
        self.config = nodes_config
        
        node_cfg = self.config[node_id]
        self.host = node_cfg["host"]
        self.consensus_port = node_cfg["consensus_port"]
        self.client_port = node_cfg["client_port"]
        
        # State machine común
        self.state_machine = DogChatStateMachine(node_id)
        
        # Diccionario de peers para el consenso
        peers_consensus = {
            nid: (cfg["host"], cfg["consensus_port"])
            for nid, cfg in self.config.items() if nid != node_id
        }
        
        # Inicializar motor de consenso seleccionado
        if self.algorithm == "paxos":
            self.consensus_engine = PaxosNode(
                node_id=self.node_id,
                host=self.host,
                port=self.consensus_port,
                peers=peers_consensus,
                state_machine=self.state_machine
            )
        else:
            self.consensus_engine = RaftNode(
                node_id=self.node_id,
                host=self.host,
                port=self.consensus_port,
                peers=peers_consensus,
                state_machine=self.state_machine
            )
            
        self.running = False
        self.client_socket: Optional[socket.socket] = None
        self.client_thread: Optional[threading.Thread] = None

    def start(self):
        """Inicia el motor de consenso y el listener TCP para clientes."""
        self.running = True
        
        # 1. Iniciar consenso
        self.consensus_engine.start()
        
        # 2. Iniciar socket para clientes
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.client_socket.bind((self.host, self.client_port))
        self.client_socket.listen(30)
        
        logger.info(f"🚀 [DogServer {self.node_id}] Motor: {self.algorithm.upper()} | Clientes en {self.host}:{self.client_port}")
        
        self.client_thread = threading.Thread(target=self._client_listen_loop, daemon=True)
        self.client_thread.start()

    def stop(self):
        """Detiene el servidor y el consenso."""
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        self.consensus_engine.stop()

    def _client_listen_loop(self):
        """Bucle de recepción de clientes de chat."""
        while self.running:
            try:
                conn, addr = self.client_socket.accept()
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
            except Exception:
                break

    def _handle_client(self, conn: socket.socket, addr):
        """Maneja las peticiones de los clientes Dog Messenger."""
        try:
            while self.running:
                req = recv_msg(conn, timeout=30.0)
                if not req:
                    break
                
                cmd = req.get("action")
                resp = {"status": "ERROR", "message": "Acción desconocida"}
                
                if cmd == "PING":
                    resp = {"status": "PONG", "node_id": self.node_id, "algorithm": self.algorithm}
                
                elif cmd == "GET_STATUS":
                    resp = self._get_cluster_status()
                    
                elif cmd == "SEND_MESSAGE":
                    resp = self._handle_client_message(req)
                    
                elif cmd == "GET_MESSAGES":
                    group = req.get("group")
                    since = req.get("since_index", 0)
                    msgs = self.state_machine.get_messages(group=group, since_index=since)
                    resp = {"status": "SUCCESS", "messages": msgs, "total": len(msgs)}
                    
                elif cmd == "GET_GROUPS":
                    groups = self.state_machine.get_groups()
                    resp = {"status": "SUCCESS", "groups": groups}
                    
                elif cmd == "CREATE_GROUP":
                    resp = self._handle_create_group(req)
                    
                elif cmd == "CLONE_INIT":
                    # Genera token de clonación y snapshot inicial
                    client_id = req.get("client_id", "Client_Unknown")
                    snapshot = self.state_machine.create_clone_snapshot(client_id)
                    token = f"DOG_CLONE_{client_id}_{int(time.time())}"
                    resp = {
                        "status": "SUCCESS",
                        "clone_token": token,
                        "snapshot": snapshot
                    }
                    
                elif cmd == "CLONE_SYNC":
                    # Sincronización completa para chat clonado
                    client_id = req.get("client_id")
                    snapshot = self.state_machine.create_clone_snapshot(client_id)
                    resp = {"status": "SUCCESS", "snapshot": snapshot}

                send_msg(conn, resp)
                
        except Exception as e:
            logger.debug(f"[DogServer {self.node_id}] Desconexión de cliente {addr}: {e}")
        finally:
            conn.close()

    def _get_cluster_status(self) -> dict:
        """Devuelve el estado actual de este nodo en el clúster."""
        is_leader = False
        leader_id = None
        term_or_round = 0
        
        if self.algorithm == "raft":
            is_leader = (self.consensus_engine.role == ROLE_LEADER)
            leader_id = self.consensus_engine.current_leader
            term_or_round = self.consensus_engine.current_term
        else:
            is_leader = self.consensus_engine.is_leader
            leader_id = self.consensus_engine.current_leader
            term_or_round = self.consensus_engine.min_proposal
            
        return {
            "status": "SUCCESS",
            "node_id": self.node_id,
            "algorithm": self.algorithm,
            "is_leader": is_leader,
            "leader_id": leader_id,
            "term_or_round": term_or_round,
            "total_messages": len(self.state_machine.messages),
            "groups": self.state_machine.get_groups(),
            "latencies": self.consensus_engine.consensus_latencies[-20:]
        }

    def _handle_client_message(self, req: dict) -> dict:
        """Procesa el envío de mensaje delegando al consenso para garantizar replicación y orden."""
        command = {
            "type": "NEW_MESSAGE",
            "msg_id": req.get("msg_id", f"msg_{int(time.time()*1000)}"),
            "sender": req.get("sender", "Anon"),
            "group": req.get("group", "general"),
            "content": req.get("content", ""),
            "msg_kind": req.get("msg_kind", "text"),
            "file_name": req.get("file_name"),
            "file_data": req.get("file_data"),
            "encrypted": req.get("encrypted", False),
            "timestamp": time.time()
        }
        
        # Proponer al algoritmo de consenso
        res = self.consensus_engine.propose(command, timeout=4.0)
        
        if res.get("success"):
            return {
                "status": "SUCCESS",
                "message": "Mensaje consensuado y replicado exitosamente",
                "consensus_data": res
            }
        else:
            # Si no es líder, reenviar automáticamente al líder
            leader_id = res.get("leader_id")
            if leader_id and leader_id in self.config and leader_id != self.node_id:
                leader_cfg = self.config[leader_id]
                try:
                    s_lead = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s_lead.settimeout(3.0)
                    s_lead.connect((leader_cfg["host"], leader_cfg["client_port"]))
                    send_msg(s_lead, req)
                    lead_resp = recv_msg(s_lead, timeout=4.0)
                    s_lead.close()
                    if lead_resp:
                        return lead_resp
                except Exception as e:
                    logger.warning(f"Error al redirigir al líder {leader_id}: {e}")
                    
            return {
                "status": "ERROR",
                "error": res.get("error", "FALLO_CONSENSO"),
                "leader_id": leader_id
            }

    def _handle_create_group(self, req: dict) -> dict:
        """Crea un grupo de chat replicado a través de consenso."""
        group_name = req.get("group_name")
        command = {"type": "CREATE_GROUP", "group_name": group_name}
        res = self.consensus_engine.propose(command, timeout=3.0)
        if res.get("success"):
            return {"status": "SUCCESS", "group": group_name}
        return {"status": "ERROR", "error": res.get("error")}
