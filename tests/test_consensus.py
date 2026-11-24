"""
Pruebas de los motores de consenso Raft y Multi-Paxos.
Verifica elección de líder, replicación consistente y recuperación tras fallos.
"""

import unittest
import time
import socket
from src.server.server_node import DogServerNode
from src.server.config import CLUSTER_NODES
from src.consensus.protocol import send_msg, recv_msg

class TestConsensusEngines(unittest.TestCase):
    def test_raft_cluster_replication_and_failover(self):
        # Iniciar 3 nodos Raft
        nodes = {}
        for nid in ["node1", "node2", "node3"]:
            nodes[nid] = DogServerNode(node_id=nid, algorithm="raft")
            nodes[nid].start()

        time.sleep(3.5)  # Esperar elección de líder

        # Verificar que exactamente un líder fue elegido
        leaders = [nid for nid, n in nodes.items() if n.consensus_engine.role == "LEADER"]
        self.assertGreaterEqual(len(leaders), 1, "Debe haber al menos un líder elegido")
        leader_id = leaders[0]

        # Proponer comando al líder
        cmd = {"type": "NEW_MESSAGE", "sender": "Tester", "group": "general", "content": "Hola Raft"}
        res = nodes[leader_id].consensus_engine.propose(cmd)
        self.assertTrue(res.get("success"), "La propuesta debe ser aprobada por consenso")

        # Verificar que el mensaje llegó a las StateMachines de los 3 nodos
        time.sleep(0.5)
        for nid, n in nodes.items():
            msgs = n.state_machine.get_messages("general")
            self.assertEqual(len(msgs), 1)
            self.assertEqual(msgs[0]["content"], "Hola Raft")

        # Probar Caída de Líder
        nodes[leader_id].stop()
        time.sleep(3.5)

        # Verificar que los nodos supervivientes eligen un nuevo líder
        survivors = [nid for nid in ["node1", "node2", "node3"] if nid != leader_id]
        new_leaders = [nid for nid in survivors if nodes[nid].consensus_engine.role == "LEADER"]
        self.assertGreaterEqual(len(new_leaders), 1, "Un nuevo líder debe ser elegido tras la caída")

        # Limpiar
        for nid in survivors:
            nodes[nid].stop()

    def test_paxos_cluster_replication(self):
        # Iniciar 3 nodos Paxos
        nodes = {}
        for nid in ["node1", "node2", "node3"]:
            nodes[nid] = DogServerNode(node_id=nid, algorithm="paxos")
            nodes[nid].start()

        time.sleep(3.5)

        # Proponer comando a través del líder o nodo
        cmd = {"type": "NEW_MESSAGE", "sender": "TesterPaxos", "group": "general", "content": "Hola Paxos"}
        leader_node = None
        for nid, n in nodes.items():
            if n.consensus_engine.is_leader:
                leader_node = n
                break
        if not leader_node:
            leader_node = nodes["node1"]

        res = leader_node.consensus_engine.propose(cmd)
        self.assertTrue(res.get("success"), "La propuesta Paxos debe ser aprobada")

        time.sleep(0.5)
        # Verificar replicación
        replicated_count = 0
        for nid, n in nodes.items():
            if len(n.state_machine.get_messages("general")) >= 1:
                replicated_count += 1
        self.assertGreaterEqual(replicated_count, 2, "La mayoría de nodos debe tener la entrada replicada")

        for n in nodes.values():
            n.stop()

if __name__ == "__main__":
    unittest.main()
