#!/usr/bin/env python3
"""
Test script pro ověření správné funkčnosti Datovka API
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datovka import DatovkaMessage, DatovkaMessageFilter, DatovkaStatistics

def test_datovka_message():
    """Test DatovkaMessage třídy"""
    print("=" * 60)
    print("TEST: DatovkaMessage")
    print("=" * 60)
    
    msg = DatovkaMessage(
        message_id="001",
        sender="TEST_SENDER",
        subject="Test message",
        read=False
    )
    
    assert msg.message_id == "001"
    assert not msg.read
    print("OK: DatovkaMessage")
    
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
    print("TEST: DatovkaMessageFilter")
    print("=" * 60)
    
    messages = [
        DatovkaMessage(message_id="1", sender="A", subject="Test 1", read=False),
        DatovkaMessage(message_id="2", sender="B", subject="Test 2", read=True),
        DatovkaMessage(message_id="3", sender="A", subject="Info", read=False),
    ]
    
    # Test unread_only
    unread = DatovkaMessageFilter.unread_only(messages)
    assert len(unread) == 2
    print("OK: unread_only()")
    
    # Test by_sender
    from_a = DatovkaMessageFilter.by_sender(messages, "A")
    assert len(from_a) == 2
    print("OK: by_sender()")
    
    # Test by_subject
    test_msgs = DatovkaMessageFilter.by_subject(messages, "Test")
    assert len(test_msgs) == 2
    print("OK: by_subject()")
    
    print()

def test_statistics():
    """Test statistik"""
    print("=" * 60)
    print("TEST: DatovkaStatistics")
    print("=" * 60)
    
    messages = [
        DatovkaMessage(message_id="1", sender="A", subject="Test 1", read=False, size=100),
        DatovkaMessage(message_id="2", sender="B", subject="Test 2", read=True, size=200),
        DatovkaMessage(message_id="3", sender="A", subject="Info", read=False, size=150),
    ]
    
    # Test count
    total = DatovkaStatistics.count_total(messages)
    assert total == 3
    print("OK: count_total()")
    
    unread = DatovkaStatistics.count_unread(messages)
    assert unread == 2
    print("OK: count_unread()")
    
    read = DatovkaStatistics.count_read(messages)
    assert read == 1
    print("OK: count_read()")
    
    # Test total size
    size = DatovkaStatistics.total_size(messages)
    assert size == 450
    print("OK: total_size()")
    
    # Test senders list
    senders = DatovkaStatistics.senders_list(messages)
    assert senders["A"] == 2
    assert senders["B"] == 1
    print("OK: senders_list()")
    
    print()

def test_dependencies():
    """Test závislostí"""
    print("=" * 60)
    print("TEST: Závislosti")
    print("=" * 60)
    
    try:
        import zeep
        print("OK: zeep")
    except ImportError:
        print("ERROR: zeep - CHYBI")
        print("  Instalace: pip install zeep")
    
    try:
        import dateutil
        print("OK: python-dateutil")
    except ImportError:
        print("WARN: python-dateutil - (volitelna)")
    
    try:
        import lxml
        print("OK: lxml")
    except ImportError:
        print("WARN: lxml - (volitelna)")
    
    try:
        import requests
        print("OK: requests")
    except ImportError:
        print("WARN: requests - (volitelna)")
    
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
