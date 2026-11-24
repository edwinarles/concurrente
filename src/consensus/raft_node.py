"""
Implementación completa del algoritmo de consenso Raft para Dog Messenger.
Diseñado desde cero usando sockets TCP nativos y la biblioteca threading de Python.
Sin dependencias externas de consenso.
"""

import socket
import threading
import time
import random
import logging
from typing import List, Dict, Any, Optional
from .protocol import send_msg, recv_msg
from .state_machine import DogChatStateMachine

logger = logging.getLogger("RaftNode")

ROLE_FOLLOWER = "FOLLOWER"
ROLE_CANDIDATE = "CANDIDATE"
ROLE_LEADER = "LEADER"

class RaftNode:
    def __init__(self, node_id: str, host: str, port: int, peers: Dict[str, tuple], state_machine: DogChatStateMachine):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.peers = peers  # dict de peer_id -> (peer_host, peer_port)
        self.state_machine = state_machine
        
        self.lock = threading.RLock()
        self.role = ROLE_FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.current_leader: Optional[str] = None
        
        # Log indexado desde 1. Entrada dummy en 0 para simplificar matemáticas
        self.log: List[Dict[str, Any]] = [{"term": 0, "index": 0, "command": None}]
        
        self.commit_index = 0
        self.last_applied = 0
        
        # Volatile state en Líder
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
        
        # Timers y flags de ejecución
        self.running = False
        self.last_heartbeat_time = time.time()
        self.election_timeout = self._get_random_timeout()
        
        # Socket de escucha
        self.server_socket: Optional[socket.socket] = None
        self.server_thread: Optional[threading.Thread] = None
        self.timer_thread: Optional[threading.Thread] = None
        self.heartbeat_thread: Optional[threading.Thread] = None
        
        # Métricas de rendimiento
        self.consensus_latencies: List[float] = []
        self.total_messages_replicated = 0

    def _get_random_timeout(self) -> float:
        """Tiempo de expiración de elección aleatorio (entre 1.2 y 2.5 seg para LAN)."""
        return random.uniform(1.2, 2.5)

    def start(self):
        """Inicia el servidor de sockets y los hilos de elección y consenso."""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(15)
        
        logger.info(f"[Raft {self.node_id}] Iniciado en {self.host}:{self.port} con rol {self.role}")
        
        self.server_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.server_thread.start()
        
        self.timer_thread = threading.Thread(target=self._election_timer_loop, daemon=True)
        self.timer_thread.start()
        
        self.heartbeat_thread = threading.Thread(target=self._leader_heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def stop(self):
        """Detiene de forma limpia el nodo Raft."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

    def _listen_loop(self):
        """Hilo receptor de conexiones entrantes de otros nodos Raft."""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_connection, args=(conn,), daemon=True).start()
            except Exception:
                break

    def _handle_connection(self, conn: socket.socket):
        """Procesa una conexión entrante."""
        try:
            msg = recv_msg(conn, timeout=5.0)
            if not msg:
                return
            
            msg_type = msg.get("type")
            response = {}
            
            if msg_type == "REQUEST_VOTE":
                response = self._handle_request_vote(msg)
            elif msg_type == "APPEND_ENTRIES":
                response = self._handle_append_entries(msg)
            elif msg_type == "GET_STATUS":
                with self.lock:
                    response = {
                        "status": "OK",
                        "node_id": self.node_id,
                        "role": self.role,
                        "term": self.current_term,
                        "leader": self.current_leader,
                        "log_length": len(self.log) - 1,
                        "commit_index": self.commit_index
                    }
            
            send_msg(conn, response)
        except Exception as e:
            logger.debug(f"[Raft {self.node_id}] Error en conexión: {e}")
        finally:
            conn.close()

    def _send_rpc(self, peer_id: str, msg: dict, timeout: float = 0.8) -> Optional[dict]:
        """Envía un RPC síncrono a un peer vía socket TCP."""
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

    # ========================== LÓGICA DE ELECCIÓN ==========================

    def _election_timer_loop(self):
        """Monitorea el timeout de elección para iniciar una votación si el líder cae."""
        while self.running:
            time.sleep(0.05)
            with self.lock:
                if self.role == ROLE_LEADER:
                    continue
                elapsed = time.time() - self.last_heartbeat_time
                if elapsed > self.election_timeout:
                    self._start_election()

    def _start_election(self):
        """Inicia una elección de líder convirtiéndose en Candidato."""
        self.role = ROLE_CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.current_leader = None
        self.last_heartbeat_time = time.time()
        self.election_timeout = self._get_random_timeout()
        
        term = self.current_term
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index]["term"]
        votes_received = 1  # Vota por sí mismo
        total_nodes = len(self.peers) + 1
        needed_votes = (total_nodes // 2) + 1
        
        logger.info(f"[Raft {self.node_id}] Inició elección para Termino {term}. Necesita {needed_votes} votos.")
        
        req = {
            "type": "REQUEST_VOTE",
            "term": term,
            "candidate_id": self.node_id,
            "last_log_index": last_log_index,
            "last_log_term": last_log_term
        }
        
        # Enviar RequestVote en paralelo a todos los pares
        votes_lock = threading.Lock()
        
        def ask_vote(peer_id):
            nonlocal votes_received
            resp = self._send_rpc(peer_id, req, timeout=1.0)
            if resp and resp.get("vote_granted"):
                with votes_lock:
                    votes_received += 1
            elif resp and resp.get("term", 0) > term:
                with self.lock:
                    if resp["term"] > self.current_term:
                        self.current_term = resp["term"]
                        self.role = ROLE_FOLLOWER
                        self.voted_for = None

        threads = [threading.Thread(target=ask_vote, args=(p,)) for p in self.peers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        with self.lock:
            if self.role == ROLE_CANDIDATE and self.current_term == term:
                if votes_received >= needed_votes:
                    logger.info(f"🏆 [Raft {self.node_id}] ¡Elegido como LÍDER en término {term}! Votos: {votes_received}/{total_nodes}")
                    self.role = ROLE_LEADER
                    self.current_leader = self.node_id
                    # Inicializar next_index y match_index
                    for p in self.peers:
                        self.next_index[p] = len(self.log)
                        self.match_index[p] = 0
                    # Enviar heartbeat inmediato
                    self._send_heartbeats()
                else:
                    logger.info(f"[Raft {self.node_id}] Elección fallida ({votes_received}/{needed_votes} votos).")

    def _handle_request_vote(self, msg: dict) -> dict:
        """Maneja el RPC RequestVote entrante."""
        with self.lock:
            term = msg.get("term", 0)
            candidate_id = msg.get("candidate_id")
            last_log_index = msg.get("last_log_index", 0)
            last_log_term = msg.get("last_log_term", 0)
            
            if term > self.current_term:
                self.current_term = term
                self.role = ROLE_FOLLOWER
                self.voted_for = None
                self.current_leader = None
                
            vote_granted = False
            
            if term == self.current_term and (self.voted_for is None or self.voted_for == candidate_id):
                my_last_index = len(self.log) - 1
                my_last_term = self.log[my_last_index]["term"]
                
                # Regla de actualización de log (Election Safety)
                log_ok = (last_log_term > my_last_term) or (
                    last_log_term == my_last_term and last_log_index >= my_last_index
                )
                
                if log_ok:
                    vote_granted = True
                    self.voted_for = candidate_id
                    self.last_heartbeat_time = time.time()
                    logger.info(f"[Raft {self.node_id}] Voto concedido a {candidate_id} para término {term}")

            return {
                "type": "REQUEST_VOTE_RESP",
                "term": self.current_term,
                "vote_granted": vote_granted
            }

    # ========================== LÓGICA DE REPLICACIÓN Y HEARTBEATS ==========================

    def _leader_heartbeat_loop(self):
        """Hilo de envío periódico de heartbeats si es líder."""
        while self.running:
            time.sleep(0.3)
            with self.lock:
                if self.role == ROLE_LEADER:
                    self._send_heartbeats()

    def _send_heartbeats(self):
        """Envía AppendEntries vacío como heartbeat a todos los seguidores."""
        for peer_id in self.peers:
            threading.Thread(target=self._replicate_to_peer, args=(peer_id,), daemon=True).start()

    def _replicate_to_peer(self, peer_id: str):
        """Replica las entradas pendientes a un seguidor específico."""
        with self.lock:
            if self.role != ROLE_LEADER:
                return
            prev_log_index = self.next_index.get(peer_id, len(self.log)) - 1
            if prev_log_index >= len(self.log):
                prev_log_index = len(self.log) - 1
            prev_log_term = self.log[prev_log_index]["term"]
            entries = self.log[prev_log_index + 1:]
            term = self.current_term
            leader_commit = self.commit_index

        req = {
            "type": "APPEND_ENTRIES",
            "term": term,
            "leader_id": self.node_id,
            "prev_log_index": prev_log_index,
            "prev_log_term": prev_log_term,
            "entries": entries,
            "leader_commit": leader_commit
        }

        resp = self._send_rpc(peer_id, req, timeout=0.8)
        
        with self.lock:
            if not resp or self.role != ROLE_LEADER or self.current_term != term:
                return
            
            resp_term = resp.get("term", 0)
            if resp_term > self.current_term:
                self.current_term = resp_term
                self.role = ROLE_FOLLOWER
                self.voted_for = None
                self.current_leader = None
                return
                
            if resp.get("success"):
                match_idx = resp.get("match_index", prev_log_index + len(entries))
                self.match_index[peer_id] = match_idx
                self.next_index[peer_id] = match_idx + 1
                self._check_and_update_commit_index()
            else:
                # Decrementar next_index y reintentar si el seguidor rechazó por inconsistencia
                if self.next_index[peer_id] > 1:
                    self.next_index[peer_id] -= 1

    def _handle_append_entries(self, msg: dict) -> dict:
        """Maneja el RPC AppendEntries recibido de un líder."""
        with self.lock:
            term = msg.get("term", 0)
            leader_id = msg.get("leader_id")
            prev_log_index = msg.get("prev_log_index", 0)
            prev_log_term = msg.get("prev_log_term", 0)
            entries = msg.get("entries", [])
            leader_commit = msg.get("leader_commit", 0)
            
            # 1. Responder falso si term < current_term
            if term < self.current_term:
                return {"type": "APPEND_ENTRIES_RESP", "term": self.current_term, "success": False}
                
            # Actualizar término si es mayor o reconocer al nuevo líder
            if term > self.current_term or self.role == ROLE_CANDIDATE:
                self.current_term = term
                self.role = ROLE_FOLLOWER
                self.voted_for = None
                
            self.current_leader = leader_id
            self.last_heartbeat_time = time.time()
            
            # 2. Responder falso si el log no contiene una entrada en prev_log_index con prev_log_term
            if prev_log_index >= len(self.log) or self.log[prev_log_index]["term"] != prev_log_term:
                return {
                    "type": "APPEND_ENTRIES_RESP",
                    "term": self.current_term,
                    "success": False,
                    "match_index": len(self.log) - 1
                }
                
            # 3. Si una entrada existente entra en conflicto con una nueva, borrar la existente y las siguientes
            for i, entry in enumerate(entries):
                idx = prev_log_index + 1 + i
                if idx < len(self.log):
                    if self.log[idx]["term"] != entry["term"]:
                        self.log = self.log[:idx]
                        self.log.append(entry)
                else:
                    self.log.append(entry)
                    
            # 4. Si leader_commit > commit_index, commit_index = min(leader_commit, index of last new entry)
            if leader_commit > self.commit_index:
                self.commit_index = min(leader_commit, len(self.log) - 1)
                self._apply_committed_entries()
                
            return {
                "type": "APPEND_ENTRIES_RESP",
                "term": self.current_term,
                "success": True,
                "match_index": len(self.log) - 1
            }

    def _check_and_update_commit_index(self):
        """Verifica si una entrada ha sido replicada en la mayoría de nodos."""
        total_nodes = len(self.peers) + 1
        majority = (total_nodes // 2) + 1
        
        for n in range(self.commit_index + 1, len(self.log)):
            if self.log[n]["term"] == self.current_term:
                # Contar réplicas
                count = 1  # Este líder
                for p in self.peers:
                    if self.match_index.get(p, 0) >= n:
                        count += 1
                if count >= majority:
                    self.commit_index = n
                    self._apply_committed_entries()

    def _apply_committed_entries(self):
        """Aplica entradas comprometidas a la StateMachine secuencialmente."""
        while self.commit_index > self.last_applied:
            self.last_applied += 1
            entry = self.log[self.last_applied]
            cmd = entry.get("command")
            if cmd:
                self.state_machine.apply(cmd)
                self.total_messages_replicated += 1

    # ========================== API CLIENTE ==========================

    def propose(self, command: Dict[str, Any], timeout: float = 3.0) -> Dict[str, Any]:
        """Propone un nuevo comando al clúster Raft. Solo el líder puede proponer."""
        t_start = time.time()
        with self.lock:
            if self.role != ROLE_LEADER:
                return {
                    "success": False,
                    "error": "NOT_LEADER",
                    "leader_id": self.current_leader
                }
            
            entry_index = len(self.log)
            entry = {
                "term": self.current_term,
                "index": entry_index,
                "command": command
            }
            self.log.append(entry)
            
        # Replicar a todos los pares de forma sincrónica para confirmar consenso
        threads = [
            threading.Thread(target=self._replicate_to_peer, args=(p,))
            for p in self.peers
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        # Esperar a que commit_index alcance entry_index
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                if self.commit_index >= entry_index:
                    latency = (time.time() - t_start) * 1000.0
                    self.consensus_latencies.append(latency)
                    return {
                        "success": True,
                        "index": entry_index,
                        "term": self.current_term,
                        "latency_ms": latency
                    }
                if self.role != ROLE_LEADER:
                    return {"success": False, "error": "LEADERSHIP_LOST"}
            time.sleep(0.01)
            
        return {"success": False, "error": "CONSENSUS_TIMEOUT"}
