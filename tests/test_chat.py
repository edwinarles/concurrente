"""
Pruebas funcionales de E2EE, generación de QR y sincronización de snapshot.
"""

import unittest
from src.crypto.e2ee import DogE2EE
from src.client.qr_code import DogQR
from src.consensus.state_machine import DogChatStateMachine

class TestChatFeatures(unittest.TestCase):
    def test_e2ee_encryption_and_tampering(self):
        secret_key = "SuperSecretKey99"
        original_msg = "Cuales son mis pedidos de musica de ayer"
        
        # Cifrar
        encrypted = DogE2EE.encrypt(original_msg, secret_key)
        self.assertNotEqual(original_msg, encrypted)
        
        # Descifrar correctamente
        decrypted = DogE2EE.decrypt(encrypted, secret_key)
        self.assertEqual(original_msg, decrypted)
        
        # Clave incorrecta
        wrong_decrypted = DogE2EE.decrypt(encrypted, "WrongKey123")
        self.assertIn("Error", wrong_decrypted)

    def test_qr_code_generation(self):
        token = "DOG_CLONE_0812_987654321"
        ascii_qr = DogQR.generate_ascii_qr(token)
        self.assertTrue(len(ascii_qr) > 50)
        self.assertIn("██", ascii_qr)
        
        pil_img = DogQR.generate_qr_image(token)
        self.assertIsNotNone(pil_img)
        self.assertEqual(pil_img.mode, "RGBA")

    def test_chat_cloning_and_history_sync(self):
        # Nodo origen
        source_sm = DogChatStateMachine("node1")
        source_sm.apply({"type": "NEW_MESSAGE", "sender": "Yo", "group": "general", "content": "Mensaje 1"})
        source_sm.apply({"type": "NEW_MESSAGE", "sender": "Fulano", "group": "general", "content": "Mensaje 2"})
        source_sm.apply({"type": "CREATE_GROUP", "group_name": "pedidos"})
        
        # Generar snapshot
        snapshot = source_sm.create_clone_snapshot("idClientChat 0812")
        self.assertEqual(snapshot["total_messages"], 2)
        
        # Nodo/Cliente destino clonado
        cloned_sm = DogChatStateMachine("cloned_client")
        cloned_sm.restore_from_snapshot(snapshot)
        
        # Verificar consistencia perfecta
        cloned_msgs = cloned_sm.get_messages("general")
        self.assertEqual(len(cloned_msgs), 2)
        self.assertEqual(cloned_msgs[0]["content"], "Mensaje 1")
        self.assertEqual(cloned_msgs[1]["content"], "Mensaje 2")
        self.assertIn("pedidos", cloned_sm.get_groups())

if __name__ == "__main__":
    unittest.main()
