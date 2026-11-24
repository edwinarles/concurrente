"""
Generador de diagramas de arquitectura y protocolo para el Informe y Presentación.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

os.makedirs("docs/figures", exist_ok=True)

def generate_architecture_diagram():
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Fondo suave
    fig.patch.set_facecolor('#F8FAFC')
    ax.set_facecolor('#F8FAFC')

    # Título
    ax.text(50, 95, "Arquitectura Distribuida Dog Messenger (CC4P1)", fontsize=13, fontweight='bold', ha='center', color='#003366')
    ax.text(50, 90, "Consenso Replicado (Raft / Multi-Paxos) con Sockets TCP Puros e Hilos", fontsize=9, ha='center', color='#555555')

    # Clientes (Izquierda)
    # Desktop
    ax.add_patch(patches.FancyBboxPatch((4, 52), 22, 28, boxstyle="round,pad=1", facecolor='#E8F0FE', edgecolor='#1A73E8', linewidth=2))
    ax.text(15, 75, "Desktop Client", fontsize=10, fontweight='bold', ha='center', color='#1A73E8')
    ax.text(15, 68, "• GUI Tkinter\n• Doge Mascot\n• E2EE Crypto\n• Adjuntos / QR", fontsize=8, ha='center', color='#333333')

    # Móvil
    ax.add_patch(patches.FancyBboxPatch((4, 15), 22, 28, boxstyle="round,pad=1", facecolor='#E6F4EA', edgecolor='#137333', linewidth=2))
    ax.text(15, 38, "Mobile / CLI", fontsize=10, fontweight='bold', ha='center', color='#137333')
    ax.text(15, 31, "• TCP Sockets\n• ASCII QR Sync\n• Consistencia\n• Terminal LAN", fontsize=8, ha='center', color='#333333')

    # Red LAN Sockets
    ax.add_patch(patches.FancyBboxPatch((32, 10), 65, 75, boxstyle="round,pad=1.5", facecolor='#FFFFFF', edgecolor='#CBD5E1', linewidth=1.5, linestyle='--'))
    ax.text(64.5, 82, "Clúster Distribuido LAN / WiFi (Mínimo 3 Nodos)", fontsize=11, fontweight='bold', ha='center', color='#1E293B')

    # 3 Nodos del Clúster
    nodes_info = [
        {"name": "Nodo 1 (Líder)", "x": 36, "y": 42, "color": "#FEF3C7", "border": "#D97706", "role": "LEADER\nTerm: T"},
        {"name": "Nodo 2 (Seguidor)", "x": 68, "y": 55, "color": "#F1F5F9", "border": "#64748B", "role": "FOLLOWER\nReplicando"},
        {"name": "Nodo 3 (Seguidor)", "x": 68, "y": 20, "color": "#F1F5F9", "border": "#64748B", "role": "FOLLOWER\nReplicando"}
    ]

    for n in nodes_info:
        ax.add_patch(patches.FancyBboxPatch((n["x"], n["y"]), 24, 22, boxstyle="round,pad=1", facecolor=n["color"], edgecolor=n["border"], linewidth=2))
        ax.text(n["x"]+12, n["y"]+16, n["name"], fontsize=9, fontweight='bold', ha='center', color='#0F172A')
        ax.text(n["x"]+12, n["y"]+9, "• State Machine\n• Replicated Log\n• Sockets TCP", fontsize=7.5, ha='center', color='#475569')

    # Conexiones Clientes -> Líder
    ax.annotate("", xy=(36, 56), xytext=(26, 66), arrowprops=dict(arrowstyle="->", color="#1A73E8", lw=2))
    ax.annotate("", xy=(36, 50), xytext=(26, 29), arrowprops=dict(arrowstyle="->", color="#137333", lw=2))

    # Conexiones de Consenso entre Nodos
    ax.annotate("", xy=(68, 66), xytext=(60, 56), arrowprops=dict(arrowstyle="<->", color="#D97706", lw=2, linestyle='solid'))
    ax.annotate("", xy=(68, 31), xytext=(60, 50), arrowprops=dict(arrowstyle="<->", color="#D97706", lw=2, linestyle='solid'))
    ax.annotate("", xy=(80, 42), xytext=(80, 55), arrowprops=dict(arrowstyle="<->", color="#64748B", lw=1.5, linestyle='dotted'))

    ax.text(48, 65, "AppendEntries / Phase 2", fontsize=7.5, color='#B45309', fontweight='bold', rotation=22)
    ax.text(48, 35, "AppendEntries / Phase 2", fontsize=7.5, color='#B45309', fontweight='bold', rotation=-22)

    plt.tight_layout()
    plt.savefig("docs/figures/architecture_diagram.png", dpi=220)
    plt.close()
    print("✔ Diagrama de arquitectura generado en docs/figures/architecture_diagram.png")

def generate_protocol_diagram():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.5))
    fig.patch.set_facecolor('#FFFFFF')

    # 1. Diagrama Raft
    ax1.set_xlim(0, 100)
    ax1.set_ylim(0, 100)
    ax1.axis('off')
    ax1.set_title("Protocolo Raft (RPCs Nativos)", fontsize=11, fontweight='bold', color='#1A73E8')

    # Líneas de vida
    ax1.plot([25, 25], [10, 85], color='#94A3B8', linestyle='--', lw=1.5)
    ax1.plot([75, 75], [10, 85], color='#94A3B8', linestyle='--', lw=1.5)
    ax1.text(25, 88, "Líder (Node 1)", fontsize=9, fontweight='bold', ha='center', color='#1E293B')
    ax1.text(75, 88, "Seguidor (Node 2)", fontsize=9, fontweight='bold', ha='center', color='#1E293B')

    # RPC 1: Elección
    ax1.annotate("", xy=(75, 76), xytext=(25, 78), arrowprops=dict(arrowstyle="->", color="#EA4335", lw=1.5))
    ax1.text(50, 79, "RequestVote(term, id, lastLog)", fontsize=7.5, ha='center', color='#EA4335')
    ax1.annotate("", xy=(25, 70), xytext=(75, 72), arrowprops=dict(arrowstyle="->", color="#34A853", lw=1.5))
    ax1.text(50, 73, "VoteGranted(term, True)", fontsize=7.5, ha='center', color='#34A853')

    # RPC 2: Heartbeat
    ax1.annotate("", xy=(75, 58), xytext=(25, 60), arrowprops=dict(arrowstyle="->", color="#1A73E8", lw=1.2, linestyle=':'))
    ax1.text(50, 61, "AppendEntries(Heartbeat)", fontsize=7.5, ha='center', color='#1A73E8')

    # RPC 3: Log Replication
    ax1.annotate("", xy=(75, 46), xytext=(25, 48), arrowprops=dict(arrowstyle="->", color="#0D47A1", lw=1.8))
    ax1.text(50, 49, "AppendEntries(prevLog, entries)", fontsize=7.5, ha='center', color='#0D47A1', fontweight='bold')
    ax1.annotate("", xy=(25, 38), xytext=(75, 40), arrowprops=dict(arrowstyle="->", color="#2E7D32", lw=1.8))
    ax1.text(50, 41, "AppendEntriesResp(success=True)", fontsize=7.5, ha='center', color='#2E7D32', fontweight='bold')

    # Commit
    ax1.annotate("", xy=(75, 26), xytext=(25, 28), arrowprops=dict(arrowstyle="->", color="#F57C00", lw=1.5))
    ax1.text(50, 29, "AppendEntries(leaderCommit=K)", fontsize=7.5, ha='center', color='#F57C00')
    ax1.text(50, 15, "Commit & Apply to StateMachine", fontsize=8, ha='center', color='#1E293B', bbox=dict(boxstyle="round,pad=0.3", facecolor="#E2E8F0"))

    # 2. Diagrama Multi-Paxos
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, 100)
    ax2.axis('off')
    ax2.set_title("Protocolo Multi-Paxos (Slots & Fases)", fontsize=11, fontweight='bold', color='#E37400')

    ax2.plot([25, 25], [10, 85], color='#94A3B8', linestyle='--', lw=1.5)
    ax2.plot([75, 75], [10, 85], color='#94A3B8', linestyle='--', lw=1.5)
    ax2.text(25, 88, "Proposer (Líder)", fontsize=9, fontweight='bold', ha='center', color='#1E293B')
    ax2.text(75, 88, "Acceptor / Learner", fontsize=9, fontweight='bold', ha='center', color='#1E293B')

    # Fase 1: Prepare / Promise
    ax2.annotate("", xy=(75, 76), xytext=(25, 78), arrowprops=dict(arrowstyle="->", color="#9C27B0", lw=1.5))
    ax2.text(50, 79, "Phase 1a: Prepare(prop_n)", fontsize=7.5, ha='center', color='#9C27B0')
    ax2.annotate("", xy=(25, 70), xytext=(75, 72), arrowprops=dict(arrowstyle="->", color="#00897B", lw=1.5))
    ax2.text(50, 73, "Phase 1b: Promise(prop_n, slots)", fontsize=7.5, ha='center', color='#00897B')

    # Fase 2: Accept / Accepted
    ax2.annotate("", xy=(75, 54), xytext=(25, 56), arrowprops=dict(arrowstyle="->", color="#E65100", lw=1.8))
    ax2.text(50, 57, "Phase 2a: Accept(slot, prop_n, val)", fontsize=7.5, ha='center', color='#E65100', fontweight='bold')
    ax2.annotate("", xy=(25, 46), xytext=(75, 48), arrowprops=dict(arrowstyle="->", color="#2E7D32", lw=1.8))
    ax2.text(50, 49, "Phase 2b: Accepted(slot, prop_n)", fontsize=7.5, ha='center', color='#2E7D32', fontweight='bold')

    # Fase 3: Commit / Learn
    ax2.annotate("", xy=(75, 34), xytext=(25, 36), arrowprops=dict(arrowstyle="->", color="#1565C0", lw=1.5))
    ax2.text(50, 37, "Phase 3: Commit(slot, val)", fontsize=7.5, ha='center', color='#1565C0')
    ax2.text(50, 15, "Apply slot sequentially to SM", fontsize=8, ha='center', color='#1E293B', bbox=dict(boxstyle="round,pad=0.3", facecolor="#E2E8F0"))

    plt.tight_layout()
    plt.savefig("docs/figures/protocol_diagram.png", dpi=220)
    plt.close()
    print("✔ Diagrama de protocolos generado en docs/figures/protocol_diagram.png")

if __name__ == "__main__":
    generate_architecture_diagram()
    generate_protocol_diagram()
