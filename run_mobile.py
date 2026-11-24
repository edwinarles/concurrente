"""
Lanzador del Cliente Móvil / CLI Dog Messenger.
"""

import argparse
from src.client.mobile_client import MobileDogClient

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente Móvil Dog Messenger")
    parser.add_argument("--user", default="Móvil_0812", help="Identificador de usuario")
    parser.add_argument("--node", default="node1", choices=["node1", "node2", "node3"], help="Nodo a conectar")
    args = parser.parse_args()

    client = MobileDogClient(client_id=args.user, node=args.node)
    client.run_cli()
