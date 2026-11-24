"""
Protocolo de red para Dog Messenger sobre sockets TCP puros.
Implementa serialización JSON con prefijo de longitud de 4 bytes (Big-Endian).
Cumple con la restricción estricta de NO usar WebSockets ni frameworks externos.
"""

import json
import struct
import socket
import logging

logger = logging.getLogger("Protocol")

def send_msg(sock: socket.socket, msg_dict: dict) -> bool:
    """Envía un diccionario serializado en JSON con encabezado de longitud de 4 bytes."""
    try:
        data = json.dumps(msg_dict, ensure_ascii=False).encode('utf-8')
        header = struct.pack('>I', len(data))
        sock.sendall(header + data)
        return True
    except (socket.error, BrokenPipeError, ConnectionResetError, OSError) as e:
        return False

def recv_msg(sock: socket.socket, timeout: float = None) -> dict:
    """Recibe un mensaje con encabezado de longitud de 4 bytes. Retorna dict o None."""
    if timeout is not None:
        sock.settimeout(timeout)
    try:
        # Leer exactamente 4 bytes para el tamaño
        raw_length = _recv_all(sock, 4)
        if not raw_length:
            return None
        msg_length = struct.unpack('>I', raw_length)[0]
        
        # Leer el payload completo
        raw_data = _recv_all(sock, msg_length)
        if not raw_data:
            return None
        return json.loads(raw_data.decode('utf-8'))
    except (socket.timeout, socket.error, json.JSONDecodeError, OSError):
        return None

def _recv_all(sock: socket.socket, n_bytes: int) -> bytes:
    """Lee exactamente n_bytes del socket TCP manejando fragmentación de stream."""
    buffer = bytearray()
    while len(buffer) < n_bytes:
        packet = sock.recv(n_bytes - len(buffer))
        if not packet:
            return None
        buffer.extend(packet)
    return bytes(buffer)
