"""
Configuración del clúster de Dog Messenger.
Define puertos de consenso (Raft/Paxos) y puertos de clientes de chat.
Permite despliegue local o en red LAN/WiFi.
"""

# Configuración de los 3 nodos por defecto
CLUSTER_NODES = {
    "node1": {
        "host": "127.0.0.1",
        "consensus_port": 9001,
        "client_port": 8001
    },
    "node2": {
        "host": "127.0.0.1",
        "consensus_port": 9002,
        "client_port": 8002
    },
    "node3": {
        "host": "127.0.0.1",
        "consensus_port": 9003,
        "client_port": 8003
    }
}

DEFAULT_ALGORITHM = "raft"  # "raft" o "paxos"
DEFAULT_E2EE_KEY = "DoggoSecureKey2026"
