"""
Lanzador del Clúster Dog Messenger.
Permite iniciar los 3 nodos en un solo proceso con hilos o lanzar un nodo específico.
Soporta cambiar entre algoritmo 'raft' y 'paxos'.
"""

import argparse
import time
import signal
import sys
from src.server.server_node import DogServerNode
from src.server.config import CLUSTER_NODES

def main():
    parser = argparse.ArgumentParser(description="Lanzador de Nodos Dog Messenger")
    parser.add_argument("--algo", choices=["raft", "paxos"], default="raft", help="Algoritmo de consenso (raft o paxos)")
    parser.add_argument("--node", choices=["node1", "node2", "node3", "all"], default="all", help="Nodo a iniciar o 'all' para el clúster completo")
    args = parser.parse_args()

    print("==================================================================")
    print(f"       INICIANDO CLÚSTER DOG MESSENGER [{args.algo.upper()}]")
    print("==================================================================")

    nodes = []
    if args.node == "all":
        for nid in ["node1", "node2", "node3"]:
            node = DogServerNode(node_id=nid, algorithm=args.algo)
            node.start()
            nodes.append(node)
        print("\n✔ Los 3 nodos del clúster están en ejecución.")
    else:
        node = DogServerNode(node_id=args.node, algorithm=args.algo)
        node.start()
        nodes.append(node)
        print(f"\n✔ Nodo individual {args.node} en ejecución.")

    print("Presiona Ctrl+C para detener el clúster.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo clúster de forma ordenada...")
        for n in nodes:
            n.stop()
        print("Clúster detenido.")

if __name__ == "__main__":
    main()
