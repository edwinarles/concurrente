"""
Implementación completa del algoritmo de consenso Multi-Paxos para Dog Messenger.
Diseñado desde cero usando sockets TCP nativos y la biblioteca threading de Python.
Permite comparación directa con Raft: latencia, número de mensajes y throughput.
"""

import socket
import threading
import time
import random
import logging
from typing import List, Dict, Any, Optional
from .protocol import send_msg, recv_msg
from .state_machine import DogChatStateMachine

logger = logging.getLogger("PaxosNode")

class PaxosNode:
    def __init__(self, node_id: str, host: str, port: int, peers: Dict[str, tuple], state_machine: DogChatStateMachine):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.peers = peers  # dict de peer_id -> (peer_host, peer_port)
        self.state_machine = state_machine
        
        self.lock = threading.RLock()
        self.running = False
        
        # Identificador numérico para orden de propuestas (round, int_id)
        # Extraemos número de node_id o usamos hash
        self.numeric_id = int(''.join(filter(str.isdigit, node_id)) or "1")
        self.current_round = 0
        self.is_leader = False
        self.current_leader: Optional[str] = None
        
        # Estado de Aceptador:
        # min_proposal: mayor número de propuesta prometido
        self.min_proposal = 0
        # accepted_entries: slot -> {"n": int, "val": any}
        self.accepted_entries: Dict[int, Dict[str, Any]] = {}
        # committed_entries: slot -> val
        self.committed_entries: Dict[int, Any] = {}
        
        self.last_applied_slot = 0
        self.next_slot = 1
        
        # Timers y sockets
        self.last_leader_contact = time.time()
        self.leader_lease_timeout = random.uniform(1.8, 3.0)
        
        self.server_socket: Optional[socket.socket] = None
        self.server_thread: Optional[threading.Thread] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.heartbeat_thread: Optional[threading.Thread] = None
        
        # Métricas
        self.consensus_latencies: List[float] = []
        self.total_messages_replicated = 0

    def _make_proposal_number(self) -> int:
        """Genera un proposal number único y estrictamente creciente."""
        self.current_round += 1
        return (self.current_round * 100) + (self.numeric_id % 100)

    def start(self):
        """Inicia el servidor y los hilos de Multi-Paxos."""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(15)
        
        logger.info(f"[Paxos {self.node_id}] Iniciado en {self.host}:{self.port}")
        
        self.server_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.server_thread.start()
        
        self.monitor_thread = threading.Thread(target=self._leader_monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.heartbeat_thread = threading.Thread(target=self._leader_heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def stop(self):
        """Detiene de forma limpia el nodo Paxos."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

    def _listen_loop(self):
        """Receptor de conexiones entrantes de otros nodos Paxos."""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_connection, args=(conn,), daemon=True).start()
            except Exception:
                break

    def _handle_connection(self, conn: socket.socket):
        """Despacha RPCs de Multi-Paxos."""
        try:
            msg = recv_msg(conn, timeout=5.0)
            if not msg:
                return
            
            m_type = msg.get("type")
            resp = {}
            
            if m_type == "PAXOS_PREPARE":
                resp = self._handle_prepare(msg)
            elif m_type == "PAXOS_ACCEPT":
                resp = self._handle_accept(msg)
            elif m_type == "PAXOS_COMMIT":
                resp = self._handle_commit(msg)
            elif m_type == "PAXOS_HEARTBEAT":
                resp = self._handle_heartbeat(msg)
            elif m_type == "GET_STATUS":
                with self.lock:
                    resp = {
                        "status": "OK",
                        "node_id": self.node_id,
                        "is_leader": self.is_leader,
                        "leader": self.current_leader,
                        "slots_committed": len(self.committed_entries),
                        "last_applied": self.last_applied_slot
                    }
                    
            send_msg(conn, resp)
        except Exception as e:
            logger.debug(f"[Paxos {self.node_id}] Error: {e}")
        finally:
            conn.close()

    def _send_rpc(self, peer_id: str, msg: dict, timeout: float = 0.8) -> Optional[dict]:
        """Envía RPC síncrono a un peer Paxos."""
        if peer_id not in self.peers:
            return None
        host, port = self.peers[peer_id]
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((host, port))
            if send_msg(s, msg):
                return recv_msg(s, timeout=timeout)
            return None
        except Exception:
            return None
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass

    # ========================== FASE 1: PREPARE / PROMISE (Líder Multi-Paxos) ==========================

    def _leader_monitor_loop(self):
        """Verifica si no hay líder activo para intentar tomar el liderazgo."""
        while self.running:
            time.sleep(0.1)
            with self.lock:
                if self.is_leader:
                    continue
                elapsed = time.time() - self.last_leader_contact
                if elapsed > self.leader_lease_timeout:
                    self._acquire_leadership()

    def _acquire_leadership(self):
        """Ejecuta la Fase 1 (Prepare) para consolidar el rol de Líder de Multi-Paxos."""
        with self.lock:
            proposal_n = self._make_proposal_number()
            first_uncommitted_slot = self.last_applied_slot + 1
            
        logger.info(f"[Paxos {self.node_id}] Intentando liderazgo con propuesta n={proposal_n}")
        req = {
            "type": "PAXOS_PREPARE",
            "proposer_id": self.node_id,
            "proposal_n": proposal_n,
            "first_slot": first_uncommitted_slot
        }
        
        promises_received = 1  # Promesa a sí mismo
        total_nodes = len(self.peers) + 1
        majority = (total_nodes // 2) + 1
        accepted_values_collected = {}  # slot -> {"n": int, "val": any}
        
        lock = threading.Lock()
        
        def send_prepare(peer_id):
            nonlocal promises_received
            resp = self._send_rpc(peer_id, req, timeout=1.0)
            if resp and resp.get("status") == "PROMISE":
                with lock:
                    promises_received += 1
                    peer_accepted = resp.get("accepted_entries", {})
                    for s_str, item in peer_accepted.items():
                        s = int(s_str)
                        if s not in accepted_values_collected or item["n"] > accepted_values_collected[s]["n"]:
                            accepted_values_collected[s] = item

        threads = [threading.Thread(target=send_prepare, args=(p,)) for p in self.peers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        with self.lock:
            if promises_received >= majority:
                logger.info(f"🏆 [Paxos {self.node_id}] ¡Liderazgo adquirido! Quorum: {promises_received}/{total_nodes}")
                self.is_leader = True
                self.current_leader = self.node_id
                self.min_proposal = proposal_n
                self.last_leader_contact = time.time()
                
                # Consolidar entradas aceptadas que no se hubieran comprometido
                for s, item in accepted_values_collected.items():
                    if s not in self.committed_entries:
                        self.accepted_entries[s] = item
                
                # Calcular el siguiente slot libre
                max_slot = self.last_applied_slot
                for s in list(self.accepted_entries.keys()) + list(self.committed_entries.keys()):
                    if s > max_slot:
                        max_slot = s
                self.next_slot = max_slot + 1
            else:
                self.is_leader = False
                self.leader_lease_timeout = random.uniform(1.8, 3.0)

    def _handle_prepare(self, msg: dict) -> dict:
        """Fase 1b (Acceptor): Responde Promise si proposal_n > min_proposal."""
        with self.lock:
            proposal_n = msg.get("proposal_n", 0)
            if proposal_n > self.min_proposal:
                self.min_proposal = proposal_n
                self.is_leader = False
                self.current_leader = msg.get("proposer_id")
                self.last_leader_contact = time.time()
                
                # Enviar todas las entradas aceptadas para slots >= first_slot
                first_slot = msg.get("first_slot", 1)
                entries_to_send = {
                    s: item for s, item in self.accepted_entries.items()
                    if s >= first_slot and s not in self.committed_entries
                }
                
                return {
                    "status": "PROMISE",
                    "proposal_n": proposal_n,
                    "accepted_entries": entries_to_send
                }
            else:
                return {
                    "status": "NACK",
                    "min_proposal": self.min_proposal
                }

    # ========================== FASE 2: ACCEPT / ACCEPTED ==========================

    def _handle_accept(self, msg: dict) -> dict:
        """Fase 2b (Acceptor): Acepta la propuesta si proposal_n >= min_proposal."""
        with self.lock:
            proposal_n = msg.get("proposal_n", 0)
            slot = msg.get("slot")
            val = msg.get("value")
            
            if proposal_n >= self.min_proposal:
                self.min_proposal = proposal_n
                self.accepted_entries[slot] = {"n": proposal_n, "val": val}
                self.last_leader_contact = time.time()
                self.current_leader = msg.get("leader_id")
                return {"status": "ACCEPTED", "slot": slot, "proposal_n": proposal_n}
            else:
                return {"status": "REJECTED", "min_proposal": self.min_proposal}

    def _handle_commit(self, msg: dict) -> dict:
        """Fase 3 (Learner): Aprende el valor consensuado y aplica a la StateMachine."""
        with self.lock:
            slot = msg.get("slot")
            val = msg.get("value")
            self.committed_entries[slot] = val
            self._apply_committed()
            return {"status": "OK", "slot": slot}

    def _apply_committed(self):
        """Aplica slots comprometidos a la StateMachine en orden estricto."""
        while (self.last_applied_slot + 1) in self.committed_entries:
            self.last_applied_slot += 1
            val = self.committed_entries[self.last_applied_slot]
            if val:
                self.state_machine.apply(val)
                self.total_messages_replicated += 1

    def _leader_heartbeat_loop(self):
        """Mantiene el lease de líder con un heartbeat periódico."""
        while self.running:
            time.sleep(0.4)
            with self.lock:
                if not self.is_leader:
                    continue
                leader_id = self.node_id
                proposal_n = self.min_proposal
                
            req = {"type": "PAXOS_HEARTBEAT", "leader_id": leader_id, "proposal_n": proposal_n}
            for p in self.peers:
                threading.Thread(target=self._send_rpc, args=(p, req), daemon=True).start()

    def _handle_heartbeat(self, msg: dict) -> dict:
        """Maneja el heartbeat del líder Paxos."""
        with self.lock:
            p_n = msg.get("proposal_n", 0)
            if p_n >= self.min_proposal:
                self.min_proposal = p_n
                self.current_leader = msg.get("leader_id")
                self.last_leader_contact = time.time()
                return {"status": "OK"}
            return {"status": "STALE"}

    # ========================== API DE PROPUESTA (CLIENTE) ==========================

    def propose(self, command: Dict[str, Any], timeout: float = 3.0) -> Dict[str, Any]:
        """Propone un valor usando Fase 2 directa sobre el líder establecido."""
        t_start = time.time()
        with self.lock:
            if not self.is_leader:
                return {
                    "success": False,
                    "error": "NOT_LEADER",
                    "leader_id": self.current_leader
                }
            
            slot = self.next_slot
            self.next_slot += 1
            proposal_n = self.min_proposal
            self.accepted_entries[slot] = {"n": proposal_n, "val": command}

        req_accept = {
            "type": "PAXOS_ACCEPT",
            "leader_id": self.node_id,
            "slot": slot,
            "proposal_n": proposal_n,
            "value": command
        }

        # Enviar Fase 2a a todos los aceptadores
        accepts_received = 1  # El líder se auto-acepta
        total_nodes = len(self.peers) + 1
        majority = (total_nodes // 2) + 1
        lock = threading.Lock()

        def send_accept(peer_id):
            nonlocal accepts_received
            resp = self._send_rpc(peer_id, req_accept, timeout=1.0)
            if resp and resp.get("status") == "ACCEPTED":
                with lock:
                    accepts_received += 1

        threads = [threading.Thread(target=send_accept, args=(p,)) for p in self.peers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Si se obtiene mayoría en Fase 2, se compromete
        if accepts_received >= majority:
            with self.lock:
                self.committed_entries[slot] = command
                self._apply_committed()
            
            # Enviar Commit a todos los nodos
            req_commit = {"type": "PAXOS_COMMIT", "slot": slot, "value": command}
            for p in self.peers:
                threading.Thread(target=self._send_rpc, args=(p, req_commit), daemon=True).start()
                
            latency = (time.time() - t_start) * 1000.0
            self.consensus_latencies.append(latency)
            return {
                "success": True,
                "slot": slot,
                "proposal_n": proposal_n,
                "latency_ms": latency
            }
        else:
            return {"success": False, "error": "QUORUM_NOT_REACHED"}
