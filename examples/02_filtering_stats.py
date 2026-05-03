#!/usr/bin/env python3
"""
Příklad 2: Filtrování a statistika zpráv
"""

import os
from pathlib import Path
from datetime import datetime
from datovka import DatovkaClient, DatovkaMessage, DatovkaMessageFilter, DatovkaStatistics
from dotenv import load_dotenv

def main():
    # Načtení z .env souboru
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    username = os.environ.get('DATOVKA_USERNAME')
    password = os.environ.get('DATOVKA_PASSWORD')
    
    if not username or not password:
        print("ERROR: Nastavte DATOVKA_USERNAME a DATOVKA_PASSWORD")
        print("Vytvořte .env soubor v kořenu projektu")
        return
    
    # Připojení
    client = DatovkaClient(username, password, test_env=True)
    if not client.connect() or not client.authenticate():
        return
    
    # Stažení zpráv
    print("Načítám zprávy...")
    raw_messages = client.get_received_messages(days=30)
    
    if not raw_messages:
        print("Žádné zprávy")
        return
    
    # Konverze na DatovkaMessage objekty
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
    
    print(f"\nLoaded {len(messages)} messages\n")
    
    # Filtrování
    print("=" * 60)
    print("FILTROVÁNÍ ZPRÁV")
    print("=" * 60)
    
    # Nepřečtené
    unread = DatovkaMessageFilter.unread_only(messages)
    print(f"\nNepřečtené zprávy: {len(unread)}")
    for msg in unread[:3]:
        print(f"  - {msg.subject}")
    
    # Statistika
    print("\n" + "=" * 60)
    DatovkaStatistics.print_summary(messages)

if __name__ == "__main__":
    main()

