#!/usr/bin/env python3
"""
Příklad 1: Základní připojení a listování zpráv
"""

import os
from pathlib import Path
from datovka import DatovkaClient

from dotenv import load_dotenv

def main():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Čtení přihlašovacích údajů
    username = os.environ.get('DATOVKA_USERNAME')
    password = os.environ.get('DATOVKA_PASSWORD')
    
    if not username or not password:
        print("ERROR: Nastavte DATOVKA_USERNAME a DATOVKA_PASSWORD")
        print("Vytvořte .env soubor v kořenu projektu")
        return
    
    # Inicializace
    client = DatovkaClient(username, password, test_env=True)
    
    # Připojení
    if not client.connect():
        return
    
    # Autentifikace
    if not client.authenticate():
        return
    
    # Informace
    info = client.get_databox_info()
    if info:
        print(f"\nDataová schránka: {info['databox_id']}")
    
    # Zprávy
    messages = client.get_received_messages(days=90, limit=50)
    if messages:
        print(f"\nZjistěno {len(messages)} zpráv:\n")
        for msg in messages:
            status = "READ" if msg['read'] else "NEW"
            print(f"{status} {msg['subject']}")
            print(f"   Od: {msg['sender']}")
            print(f"   ID: {msg['message_id']}")
            print()

if __name__ == "__main__":
    main()

