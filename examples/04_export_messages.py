#!/usr/bin/env python3
"""
Příklad 4: Export zpráv do různých formátů
"""

import os
from datovka import DatovkaClient, DatovkaMessage, DatovkaExporter
from datetime import datetime

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
    print("Načítám zprávy...")
    raw_messages = client.get_received_messages(days=30, limit=50)
    
    if not raw_messages:
        print("Žádné zprávy")
        return
    
    # Konverze
    messages = [
        DatovkaMessage(
            message_id=msg['message_id'],
            sender=msg['sender'],
            subject=msg['subject'],
            delivery_time=datetime.fromisoformat(str(msg['delivery_time'])) if msg['delivery_time'] else None,
            read=msg['read']
        )
        for msg in raw_messages
    ]
    
    # Vytvoření adresáře
    os.makedirs("exports", exist_ok=True)
    
    # Export
    print(f"\nExport {len(messages)} zpráv...\n")
    
    DatovkaExporter.to_csv(messages, "exports/zpravy.csv")
    DatovkaExporter.to_json(messages, "exports/zpravy.json")
    DatovkaExporter.to_html(messages, "exports/zpravy.html")
    
    print("\nExport dokončen!")

if __name__ == "__main__":
    main()
