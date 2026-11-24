"""
Módulo de generación y visualización de códigos QR para Dog Messenger.
Permite clonar sesiones de chat y sincronizar el historial completo entre dispositivos.
"""

import io
import qrcode
from PIL import Image

class DogQR:
    @staticmethod
    def generate_qr_image(payload: str, box_size: int = 8, border: int = 2) -> Image.Image:
        """Genera un objeto PIL Image con el código QR de sincronización/clonación."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#002D62", back_color="white")
        return img.convert("RGBA")

    @staticmethod
    def generate_ascii_qr(payload: str) -> str:
        """Genera una versión en caracteres ASCII/Unicode para terminales móviles y CLI."""
        qr = qrcode.QRCode()
        qr.add_data(payload)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        
        lines = []
        for row in matrix:
            line = "".join("██" if cell else "  " for cell in row)
            lines.append(line)
        return "\n".join(lines)
