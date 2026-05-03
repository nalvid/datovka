#!/usr/bin/env python3
"""
Příklad 3: Stažení zpráv
"""

import os
from datovka import DatovkaClient

def main():
    username = os.environ.get('DATOVKA_USERNAME')
    password = os.environ.get('DATOVKA_PASSWORD')
    
    if not username or not password:
        print("ERROR: Nastavte DATOVKA_USERNAME a DATOVKA_PASSWORD")
        return
    
    # Připojení
    client = DatovkaClient(username, password, test_env=True)
    if not client.connect() or not client.authenticate():
        return
    
    # Stažení zpráv
    messages = client.get_received_messages(days=30, limit=5)
    
    if not messages:
        print("Žádné zprávy k dispozici")
        return
    
    # Vytvoření adresáře
    os.makedirs("downloaded_messages", exist_ok=True)
    
    # Stažení prvních 3 zpráv
    print("\nStahování zpráv...\n")
    for i, msg in enumerate(messages[:3], 1):
        print(f"{i}. {msg['subject']}")
        print(f"   od: {msg['sender']}")
        
        filepath = client.download_message(
            msg['message_id'],
            output_dir="downloaded_messages"
        )
        
        if filepath:
            print("   OK: Stazeno\n")
        else:
            print("   ERROR: Chyba\n")

if __name__ == "__main__":
    main()

