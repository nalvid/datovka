#!/usr/bin/env python3
"""
Test script pro ověření správné funkčnosti Datovka API
"""

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datovka import Message, MessageFilter, Statistics

def test_datovka_message():
    """Test třídy Message"""
    print("=" * 60)
    print("TEST: Message")
    print("=" * 60)
    
    msg = Message(
        message_id="001",
        sender="TEST_SENDER",
        subject="Test message",
        read=False
    )
    
    assert msg.message_id == "001"
    assert not msg.read
    print("OK: Message")
    
    # Test konverze na dict
    d = msg.to_dict()
    assert isinstance(d, dict)
    print("OK: to_dict()")
    
    # Test string reprezentace
    s = str(msg)
    assert "TEST" in s
    print("OK: __str__()")
    
    print()

def test_message_filter():
    """Test filtrů"""
    print("=" * 60)
    print("TEST: MessageFilter")
    print("=" * 60)
    
    messages = [
        Message(message_id="1", sender="A", subject="Test 1", read=False),
        Message(message_id="2", sender="B", subject="Test 2", read=True),
        Message(message_id="3", sender="A", subject="Info", read=False),
    ]
    
    # Test unread_only
    unread = MessageFilter.unread_only(messages)
    assert len(unread) == 2
    print("OK: unread_only()")
    
    # Test by_sender
    from_a = MessageFilter.by_sender(messages, "A")
    assert len(from_a) == 2
    print("OK: by_sender()")
    
    # Test by_subject
    test_msgs = MessageFilter.by_subject(messages, "Test")
    assert len(test_msgs) == 2
    print("OK: by_subject()")
    
    print()

def test_statistics():
    """Test statistik"""
    print("=" * 60)
    print("TEST: Statistics")
    print("=" * 60)
    
    messages = [
        Message(message_id="1", sender="A", subject="Test 1", read=False, size=100),
        Message(message_id="2", sender="B", subject="Test 2", read=True, size=200),
        Message(message_id="3", sender="A", subject="Info", read=False, size=150),
    ]
    
    # Test count
    total = Statistics.count_total(messages)
    assert total == 3
    print("OK: count_total()")
    
    unread = Statistics.count_unread(messages)
    assert unread == 2
    print("OK: count_unread()")
    
    read = Statistics.count_read(messages)
    assert read == 1
    print("OK: count_read()")
    
    # Test total size
    size = Statistics.total_size(messages)
    assert size == 450
    print("OK: total_size()")
    
    # Test senders list
    senders = Statistics.senders_list(messages)
    assert senders["A"] == 2
    assert senders["B"] == 1
    print("OK: senders_list()")
    
    print()

def test_dependencies():
    """Test závislostí"""
    print("=" * 60)
    print("TEST: Závislosti")
    print("=" * 60)

    if importlib.util.find_spec("zeep") is not None:
        print("OK: zeep")
    else:
        print("ERROR: zeep - CHYBI")
        print("  Instalace: pip install zeep")

    if importlib.util.find_spec("dateutil") is not None:
        print("OK: python-dateutil")
    else:
        print("WARN: python-dateutil - (volitelna)")

    if importlib.util.find_spec("lxml") is not None:
        print("OK: lxml")
    else:
        print("WARN: lxml - (volitelna)")

    print()

def main():
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " Datovka API - Test Suite ".center(58) + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    try:
        test_dependencies()
        test_datovka_message()
        test_message_filter()
        test_statistics()
        
        print("=" * 60)
        print("VYSLEDEK: OK: Vsechny testy prosly")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\nERROR: TEST SELHALA: {str(e)}")
        return 1
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
