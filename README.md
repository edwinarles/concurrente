# Dog Messenger - Práctica 04: Consenso Replicado (CC4P1)

**Escuela Profesional de Ciencia de la Computación**  
**Programación Concurrente y Distribuida (CC4P1) - 2026-II**  
**Proyecto:** Sistema de Mensajería Distribuida Dog Messenger con Consenso Replicado (Raft vs. Multi-Paxos)

---

## 🐶 Descripción General

Dog Messenger es un sistema de mensajería distribuida cliente-servidor tolerante a fallos (CFT) que garantiza la consistencia del historial de mensajes, imágenes, archivos y grupos mediante **Máquinas de Estados Replicadas (State Machine Replication - SMR)**.

El proyecto implementa desde cero dos algoritmos de consenso:
1. **Raft (Algoritmo Obligatorio):** Algoritmo basado en líder fuerte, con elección aleatorizada por términos, replicación mediante `AppendEntries` y garantía de commit por mayoría.
2. **Multi-Paxos (Segundo Algoritmo Comparativo):** Algoritmo clásico de líder distinguido (Proposer/Acceptor/Learner) optimizado para flujos continuos de mensajes mediante slots secuenciales y consolidación de Fase 1 (Prepare/Promise).

---

## 📌 Cumplimiento de Restricciones Técnicas Estrictas

- ✅ **Solo Sockets TCP nativos:** Prohibido WebSockets, Socket.io, RabbitMQ, ZeroMQ o cualquier framework de alto nivel. Toda la comunicación se realiza mediante tramas binarias TCP delimitadas por un encabezado de 4 bytes (Big-Endian).
- ✅ **Uso de Hilos (Threading):** Control concurrente mediante `threading.Thread`, `threading.RLock` y colas protegidas para evitar la corrupción de registros y del log replicado.
- ✅ **Sin librerías externas de consenso:** Implementación 100% propia de la lógica de Raft y Multi-Paxos.
- ✅ **Cifrado Punto a Punto (E2EE):** Cifrado autenticado *Encrypt-then-MAC* con derivación de claves PBKDF2-HMAC-SHA256 (100,000 iteraciones). El consenso replica el estado cifrado garantizando privacidad total.
- ✅ **Clonación de Chats vía QR:** Sincronización atómica de snapshots de estado a través de la red para dispositivos móviles y de escritorio.
- ✅ **Despliegue en Clúster Real (Mínimo 3 nodos):** Soporta ejecución distribuida en red local LAN/WiFi o virtual local en puertos independientes.

---

## 📂 Estructura del Proyecto

```text
Tarea concurrente/
├── DogMessenger_Informe_CC4P1.pdf       # Informe técnico completo en PDF
├── DogMessenger_Presentacion_CC4P1.pdf   # Diapositivas en PDF para la defensa
├── assets/
│   └── doge_shield.png                 # Mascota Doge con escudo (interfaz gráfica)
├── docs/
│   ├── benchmark_results.json          # Datos empíricos de rendimiento
│   └── figures/                        # Gráficos y diagramas en alta resolución
│       ├── architecture_diagram.png    # Diagrama de arquitectura de nodos
│       ├── protocol_diagram.png        # Diagrama de secuencia RPC Raft y Paxos
│       ├── latency_comparison.png      # Comparativa de latencia (Media y P95)
│       ├── throughput_comparison.png   # Throughput de mensajes/seg
│       ├── failover_comparison.png     # Tiempo de recuperación de líder
│       └── messages_overhead.png       # Sobrecarga de mensajes de red
├── src/
│   ├── consensus/                      # Motores de consenso
│   │   ├── protocol.py                 # Protocolo binario TCP y framing de 4B
│   │   ├── state_machine.py            # Máquina de estados replicada (SMR)
│   │   ├── raft_node.py                # Implementación completa de Raft
│   │   └── paxos_node.py               # Implementación completa de Multi-Paxos
│   ├── crypto/
│   │   └── e2ee.py                     # Cifrado E2EE PBKDF2-HMAC-SHA256
│   ├── server/
│   │   ├── config.py                   # Configuración de IPs y puertos LAN
│   │   └── server_node.py              # Servidor TCP multihilo del nodo
│   ├── client/
│   │   ├── qr_code.py                  # Generador de códigos QR (PIL y ASCII)
│   │   ├── dog_gui.py                  # Interfaz gráfica Desktop Tkinter
│   │   └── mobile_client.py            # Cliente móvil interactivo para CLI/Terminal
│   └── benchmark/
│       └── benchmark_runner.py         # Suite automatizada de pruebas y gráficos
├── tests/
│   ├── test_chat.py                    # Pruebas unitarias de E2EE, QR y StateMachine
│   └── test_consensus.py               # Pruebas de consenso, elección y failover
├── run_cluster.py                      # Lanzador del clúster de 3 nodos
├── run_client.py                       # Lanzador del cliente Desktop GUI
├── run_mobile.py                       # Lanzador del cliente Móvil
├── generate_diagrams.py                # Generador de diagramas de arquitectura
└── generate_docs.py                    # Compilador de PDFs (Informe y Presentación)
```

---

## 🚀 Guía de Ejecución Rápida

### 1. Iniciar el Clúster de 3 Nodos (Raft)
Para levantar el clúster con el algoritmo obligatorio **Raft**:
```bash
python run_cluster.py --algo raft
```
*(Para probar con **Multi-Paxos**, simplemente ejecute: `python run_cluster.py --algo paxos`)*

### 2. Iniciar el Cliente Desktop (Dog Messenger GUI)
En una nueva terminal:
```bash
python run_client.py --user 0812 --node node1
```
Aparecerá la ventana de Dog Messenger con la mascota Doge, la barra azul superior, selector de grupos, cifrado E2EE, botón de clonación QR y envío de archivos/imágenes.

### 3. Iniciar un Segundo Cliente (Simulación Móvil / CLI)
En otra terminal o dispositivo conectado a la misma red WiFi:
```bash
python run_mobile.py --user Fulano --node node2
```
Podrá intercambiar mensajes en tiempo real; todos los mensajes serán replicados y ordenados por consenso entre los nodos.

---

## 🧪 Pruebas Unitarias y Benchmarks

### Ejecutar Suite de Pruebas Unitarias
```bash
python -m unittest tests/test_chat.py
python -m unittest tests/test_consensus.py
```

### Ejecutar Benchmarks y Regenerar Gráficas Estadísticas
```bash
python src/benchmark/benchmark_runner.py
```
Este comando ejecuta una ráfaga de mensajes sobre Raft y Multi-Paxos, simula la caída forzosa del nodo líder en ambos algoritmos, mide la recuperación y genera las figuras en `docs/figures/`.

### Recompilar los Documentos PDF
```bash
python generate_diagrams.py
python generate_docs.py
```

---

## 🎯 Guía de Demostración en Vivo para la Defensa

1. **Nodos Sincronizados:**
   - Inicie el clúster (`python run_cluster.py --algo raft`).
   - Abra dos clientes GUI (`python run_client.py --user 0812` y `python run_client.py --user 9999 --node node2`).
   - Envíe un mensaje desde el cliente 1; verifique que el cliente 2 conectado a un nodo diferente recibe el mensaje de inmediato con idéntico orden.
2. **Caída del Líder y Nueva Elección (Raft):**
   - En la consola del clúster observe cuál es el nodo líder (ej. `node1`).
   - Detenga el nodo líder (o cierre su proceso).
   - Observe cómo en menos de 3 segundos los seguidores inician votación y eligen automáticamente un nuevo líder (`node2` o `node3`), manteniendo la disponibilidad del chat.
3. **Clonación de Chats vía QR:**
   - En el cliente Desktop haga clic en `📱 Clonar QR`.
   - Se abrirá la ventana con el código QR y el token de sesión.
   - Haga clic en `📲 Simular Escaneo en Móvil` (o ingrese el comando `/sync` en el cliente móvil); observará cómo el historial completo de mensajes anteriores se replica de inmediato en el nuevo cliente.
4. **Cifrado Punto a Punto (E2EE):**
   - Active o desactive el botón `🔒 E2EE: ON`.
   - Al estar activo, los paquetes transmitidos por los sockets TCP contienen únicamente el payload cifrado y el sello HMAC, demostrando que el clúster mantiene el consenso sin necesidad de descifrar la información confidencial de los usuarios.
