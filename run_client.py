"""
Lanzador del Cliente Desktop Dog Messenger con interfaz gráfica Tkinter.
"""

import argparse
from src.client.dog_gui import launch_gui

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente Desktop Dog Messenger")
    parser.add_argument("--user", default=None, help="Identificador del usuario (ej. 0812)")
    parser.add_argument("--node", default="node1", choices=["node1", "node2", "node3"], help="Nodo al cual conectarse")
    args = parser.parse_args()

    client_id = f"idClientChat {args.user}" if args.user else None
    launch_gui(client_id=client_id, node=args.node)
