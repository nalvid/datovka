"""
Datovka (Czech Data Box) API - Python Client Module

Modul pro komunikaci s Datovka API (ISDS - Informační systém datových schránek)

API Reference:
- Official documentation: https://info.mojedatovaschranka.cz/info/cs/74.html
- Official WSDL/XSD: package data in datovka/wsdl/
"""

import argparse
import base64
import html
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from zeep import Client, Settings
from zeep.transports import Transport


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

__version__ = "1.0.0"
__all__ = [
    'DatovkaClient',
    'DatovkaMessage',
    'DatovkaMessageFilter',
    'DatovkaStatistics',
    'DatovkaExporter',
    'DatovkaCLI',
    'cli_main',
]


class DatovkaClient:
    """
    Klient pro komunikaci s Datovka API (ISDS)
    """

    PROD_HOST = "ws1.mojedatovaschranka.cz"
    TEST_HOST = "ws1.czebox.cz"

    INFO_ENDPOINT = "https://{host}/DS/dx"
    OPERATIONS_ENDPOINT = "https://{host}/DS/dz"
    ACCESS_ENDPOINT = "https://{host}/DS/DsManage"

    WSDL_DIR = Path(__file__).with_name("wsdl")
    INFO_WSDL = WSDL_DIR / "dm_info.wsdl"
    OPERATIONS_WSDL = WSDL_DIR / "dm_operations.wsdl"
    ACCESS_WSDL = WSDL_DIR / "db_access.wsdl"
    NAMESPACE = "{http://isds.czechpoint.cz/v20}"

    def __init__(self, username: str, password: str, test_env: bool = True):
        """
        Inicializace klienta

        Args:
            username: Uživatelské jméno do Datovky
            password: Heslo
            test_env: Používat testovací prostředí (True) nebo produkci (False)
        """
        self.username = username
        self.password = password
        self.test_env = test_env
        self.client: Optional[Client] = None
        self.info_client: Optional[Client] = None
        self.operations_client: Optional[Client] = None
        self.access_client: Optional[Client] = None
        self.info_service: Any = None
        self.operations_service: Any = None
        self.access_service: Any = None

    @classmethod
    def _host(cls, test_env: bool) -> str:
        return cls.TEST_HOST if test_env else cls.PROD_HOST

    @staticmethod
    def _wsdl_uri(wsdl_path: Path) -> str:
        if not wsdl_path.exists():
            raise FileNotFoundError(f"Chybi WSDL soubor: {wsdl_path}")
        return wsdl_path.resolve().as_uri()

    @staticmethod
    def _format_owner_name(owner_info: Any) -> str:
        firm_name = getattr(owner_info, 'firmName', None)
        if firm_name:
            return firm_name

        parts = [
            getattr(owner_info, 'pnFirstName', None),
            getattr(owner_info, 'pnMiddleName', None),
            getattr(owner_info, 'pnLastName', None),
        ]
        return ' '.join(part for part in parts if part) or 'N/A'

    @staticmethod
    def _format_owner_address(owner_info: Any) -> str:
        parts = [
            getattr(owner_info, 'adStreet', None),
            getattr(owner_info, 'adNumberInStreet', None),
            getattr(owner_info, 'adNumberInMunicipality', None),
            getattr(owner_info, 'adCity', None),
            getattr(owner_info, 'adZipCode', None),
            getattr(owner_info, 'adState', None),
        ]
        return ', '.join(str(part) for part in parts if part) or 'N/A'

    def connect(self) -> bool:
        """
        Připojení k ISDS API

        Returns:
            True pokud se podařilo připojit, False jinak
        """
        try:
            host = self._host(self.test_env)
            env = "TEST" if self.test_env else "PROD"
            info_endpoint = self.INFO_ENDPOINT.format(host=host)
            operations_endpoint = self.OPERATIONS_ENDPOINT.format(host=host)
            access_endpoint = self.ACCESS_ENDPOINT.format(host=host)

            logger.info(f"Připojování k Datovka API ({env})...")
            logger.info(f"Info endpoint: {info_endpoint}")
            logger.info(f"Operations endpoint: {operations_endpoint}")
            logger.info(f"Access endpoint: {access_endpoint}")

            session = requests.Session()
            session.auth = HTTPBasicAuth(self.username, self.password)

            settings = Settings(strict=False, xml_huge_tree=True)
            transport = Transport(session=session)

            self.info_client = Client(
                wsdl=self._wsdl_uri(self.INFO_WSDL),
                settings=settings,
                transport=transport,
            )
            self.operations_client = Client(
                wsdl=self._wsdl_uri(self.OPERATIONS_WSDL),
                settings=settings,
                transport=transport,
            )
            self.access_client = Client(
                wsdl=self._wsdl_uri(self.ACCESS_WSDL),
                settings=settings,
                transport=transport,
            )

            self.info_service = self.info_client.create_service(
                f'{self.NAMESPACE}dmInfoBinding',
                info_endpoint,
            )
            self.operations_service = self.operations_client.create_service(
                f'{self.NAMESPACE}dmOperationsBinding',
                operations_endpoint,
            )
            self.access_service = self.access_client.create_service(
                f'{self.NAMESPACE}DataBoxAccessBinding',
                access_endpoint,
            )
            self.client = self.info_client

            logger.info("OK: Uspesne pripojeno k API")
            return True

        except FileNotFoundError as e:
            logger.error(f"ERROR: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"ERROR: Chyba pri pripojovani: {str(e)}")
            return False

    def authenticate(self) -> bool:
        """
        Overeni prihlasovacich udaju.

        ISDS pouziva HTTP Basic Auth na transportni vrstve, takze autentifikace
        probiha pri kazdem volani. Tato metoda provede lehky test, aby overila,
        ze prihlasovaci udaje fungují.

        Returns:
            True pokud je autentifikace úspěšná
        """
        if not self.access_client or self.access_service is None:
            logger.error("Nejdříve se musíte připojit (connect)")
            return False

        try:
            logger.info("Overuji prihlasovaci udaje...")

            with self.access_client.settings(raw_response=True):
                response = self.access_service.GetPasswordInfo(dbDummy='')

            if response.status_code == 200:
                logger.info("OK: Autentifikace uspesna")
                return True

            if response.status_code == 401:
                logger.error("ERROR: Server odmitl prihlasovaci udaje (401 Unauthorized)")
                return False

            logger.error(
                f"ERROR: Neocekavana HTTP odpoved pri autentifikaci: {response.status_code}"
            )
            return False


        except Exception as e:
            logger.error(f"ERROR: Chyba pri autentifikaci: {str(e)}")
            return False

    def get_databox_info(self) -> Optional[Dict]:
        """
        Získání informací o datové schránce

        Returns:
            Slovník s informacemi o schránce nebo None
        """
        if self.access_service is None:
            logger.error("Nejdříve se musíte připojit (connect)")
            return None

        try:
            logger.info("Stahování informací o datové schránce...")

            response = self.access_service.GetOwnerInfoFromLogin(dbDummy='')
            owner_info = getattr(response, 'dbOwnerInfo', None)

            if owner_info:
                info = {
                    'databox_id': getattr(owner_info, 'dbID', 'N/A'),
                    'owner': self._format_owner_name(owner_info),
                    'address': self._format_owner_address(owner_info),
                }
                logger.info(f"OK: Datova schranka: {info['databox_id']}")
                return info
            else:
                logger.warning("Nelze získat informace o datové schránce")
                return None

        except Exception as e:
            logger.error(f"ERROR: Chyba pri stahovani informaci: {str(e)}")
            return None

    def get_received_messages(self, days: int = 90, limit: int = 100) -> Optional[List[Dict]]:
        """
        Listování přijatých zpráv

        Args:
            days: Počet dní zpět (default 90)
            limit: Maximum zpráv k návratu (default 100)

        Returns:
            Seznam přijatých zpráv nebo None
        """
        if self.info_service is None:
            logger.error("Nejdříve se musíte připojit (connect)")
            return None

        try:
            logger.info(f"Stahování přijatých zpráv (posledních {days} dnů)...")

            from_date = datetime.now() - timedelta(days=days)

            response = self.info_service.GetListOfReceivedMessages(
                dmFromTime=from_date,
                dmToTime=datetime.now(),
                dmRecipientOrgUnitNum=0,
                dmStatusFilter=-1,
                dmOffset=1,
                dmLimit=limit,
            )

            records = self._extract_records(response)
            if not records:
                logger.info("Žádné zprávy k dispozici")
                return []

            messages = []

            for msg in records:
                acceptance_time = getattr(msg, 'dmAcceptanceTime', None)
                message = {
                    'message_id': getattr(msg, 'dmID', 'N/A'),
                    'sender': getattr(msg, 'dmSender', 'N/A'),
                    'subject': getattr(msg, 'dmAnnotation', '(bez předmětu)'),
                    'delivery_time': getattr(msg, 'dmDeliveryTime', 'N/A'),
                    'acceptance_time': acceptance_time,
                    'read': acceptance_time is not None,
                }
                messages.append(message)

            logger.info(f"OK: Nalezeno {len(messages)} zprav")
            return messages

        except Exception as e:
            logger.error(f"ERROR: Chyba pri listovani zprav: {str(e)}")
            return None

    @staticmethod
    def _extract_records(response: Any) -> List[Any]:
        """Vytahne seznam dmRecord z odpovedi ISDS bez ohledu na verzi schematu."""
        if response is None:
            return []
        container = getattr(response, 'dmRecords', None)
        inner = None
        if container is not None:
            inner = getattr(container, 'dmRecord', None)
            if inner is None:
                value_items = getattr(container, '_value_1', None)
                if value_items:
                    records: List[Any] = []
                    for item in value_items:
                        record = item.get('dmRecord') if isinstance(item, dict) else getattr(item, 'dmRecord', None)
                        if record is None:
                            continue
                        if isinstance(record, list):
                            records.extend(record)
                        else:
                            records.append(record)
                    if records:
                        return records
        if inner is None:
            inner = getattr(response, 'dmRecord', None)
        if inner is None:
            return []
        return inner if isinstance(inner, list) else [inner]

    def download_message(self, message_id: str, output_dir: str = ".") -> Optional[str]:
        """
        Stažení podepsané zprávy (ZFO formát)

        Args:
            message_id: ID zprávy
            output_dir: Výstupní adresář

        Returns:
            Cesta k staženému souboru nebo None
        """
        if self.operations_service is None:
            logger.error("Nejdříve se musíte připojit (connect)")
            return None

        try:
            logger.info(f"Stahování zprávy {message_id}...")

            response = self.operations_service.SignedMessageDownload(dmID=message_id)

            content = None
            if response is not None:
                content = getattr(response, 'dmSignature', None)
                if content is None:
                    content = getattr(response, 'dmEncodedContent', None)

            if content is not None:
                output_path = Path(output_dir).expanduser()
                if not output_path.is_absolute():
                    output_path = Path.cwd() / output_path
                output_path.mkdir(parents=True, exist_ok=True)

                filename = f"message_{message_id}.zfo"
                filepath = (output_path / filename).resolve()

                with filepath.open('wb') as f:
                    if isinstance(content, str):
                        content = content.encode('utf-8')
                    f.write(content)

                logger.info(f"OK: Zprava stazena: {filepath}")
                return str(filepath)
            else:
                logger.error(f"ERROR: Nepodarilo se stahnout zpravu {message_id}")
                return None

        except Exception as e:
            logger.error(f"ERROR: Chyba pri stahovani zpravy: {str(e)}")
            return None


class DatovkaZfo:
    """Práce se staženým ZFO kontejnerem bez nutnosti připojení k ISDS."""

    NAMESPACES = {
        'q': 'http://isds.czechpoint.cz/v20/message',
        'p': 'http://isds.czechpoint.cz/v20',
    }

    @staticmethod
    def _resolve_path(path_value: Path) -> Path:
        path = path_value.expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    @staticmethod
    def _find_openssl() -> str:
        openssl = os.environ.get('OPENSSL') or shutil.which('openssl')
        if not openssl:
            raise RuntimeError(
                "OpenSSL neni dostupny v PATH. Nastav OPENSSL nebo nainstaluj openssl."
            )
        return openssl

    @classmethod
    def _load_payload(cls, zfo_path: Path) -> bytes:
        path = cls._resolve_path(zfo_path)
        if not path.exists():
            raise FileNotFoundError(f"ZFO soubor neexistuje: {path}")

        result = subprocess.run(
            [
                cls._find_openssl(),
                'cms',
                '-verify',
                '-inform',
                'DER',
                '-in',
                str(path),
                '-noverify',
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='replace').strip()
            raise RuntimeError(f"Nepodarilo se nacist ZFO payload: {stderr or 'neznamy error'}")
        return result.stdout

    @classmethod
    def _load_xml_root(cls, zfo_path: Path) -> ET.Element:
        payload = cls._load_payload(zfo_path)
        try:
            return ET.fromstring(payload)
        except ET.ParseError as exc:
            raise RuntimeError(f"ZFO neobsahuje validni XML payload: {exc}") from exc

    @classmethod
    def _text(cls, parent: Optional[ET.Element], path: str) -> Optional[str]:
        if parent is None:
            return None
        elem = parent.find(path, cls.NAMESPACES)
        if elem is None or elem.text is None:
            return None
        text = elem.text.strip()
        return text or None

    @staticmethod
    def _safe_name(name: Optional[str], fallback: str) -> str:
        candidate = Path(name or fallback).name
        return candidate or fallback

    @staticmethod
    def _resolve_output_path(output_path: Path) -> Path:
        path = output_path.expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    @classmethod
    def _collect_files(cls, root: ET.Element) -> List[Dict[str, Any]]:
        files: List[Dict[str, Any]] = []
        nodes = root.findall('q:dmReturnedMessage/p:dmDm/p:dmFiles/p:dmFile', cls.NAMESPACES)
        for index, node in enumerate(nodes, 1):
            content = cls._text(node, 'p:dmEncodedContent') or ''
            raw_bytes = b''
            if content:
                raw_bytes = base64.b64decode(content)

            files.append(
                {
                    'name': cls._safe_name(node.attrib.get('dmFileDescr'), f'attachment_{index}'),
                    'mime_type': node.attrib.get('dmMimeType') or 'application/octet-stream',
                    'meta_type': node.attrib.get('dmFileMetaType') or 'unknown',
                    'content': raw_bytes,
                    'size': len(raw_bytes),
                }
            )
        return files

    @classmethod
    def _select_body_file(cls, files: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not files:
            return None

        for predicate in (
            lambda item: item['meta_type'] == 'main' and item['mime_type'] == 'text/html',
            lambda item: item['mime_type'] == 'text/html',
            lambda item: item['meta_type'] == 'main',
        ):
            for file_info in files:
                if predicate(file_info):
                    return file_info

        return files[0]

    @classmethod
    def get_body_html(cls, zfo_path: Path) -> str:
        root = cls._load_xml_root(zfo_path)
        files = cls._collect_files(root)
        body_file = cls._select_body_file(files)
        if body_file is None:
            raise RuntimeError("ZFO neobsahuje telo zpravy")

        return body_file['content'].decode('utf-8', errors='replace')

    @classmethod
    def export_body(
        cls,
        zfo_path: Path,
        format_name: str,
        output_path: Optional[Path] = None,
    ) -> Path:
        source_path = cls._resolve_path(zfo_path)
        html_content = cls.get_body_html(source_path)

        if format_name == 'html':
            body_bytes = html_content.encode('utf-8')
            default_path = source_path.with_name(f"{source_path.stem}.body.html")
        elif format_name == 'txt':
            body_text = _html_to_text(html_content)
            body_bytes = body_text.encode('utf-8')
            default_path = source_path.with_name(f"{source_path.stem}.body.txt")
        else:
            raise ValueError(f"Nepodporovany format tela zpravy: {format_name}")

        final_path = cls._resolve_output_path(output_path or default_path)
        final_path.write_bytes(body_bytes)
        return final_path

    @classmethod
    def inspect(cls, zfo_path: Path) -> Dict[str, Any]:
        resolved_path = cls._resolve_path(zfo_path)
        root = cls._load_xml_root(resolved_path)
        returned_message = root.find('q:dmReturnedMessage', cls.NAMESPACES)
        dm_message = root.find('q:dmReturnedMessage/p:dmDm', cls.NAMESPACES)
        files = cls._collect_files(root)

        return {
            'path': str(resolved_path),
            'message_id': cls._text(dm_message, 'p:dmID'),
            'sender': cls._text(dm_message, 'p:dmSender'),
            'recipient': cls._text(dm_message, 'p:dmRecipient'),
            'subject': cls._text(dm_message, 'p:dmAnnotation'),
            'message_type': cls._text(dm_message, 'p:dmType'),
            'delivery_time': cls._text(returned_message, 'q:dmDeliveryTime'),
            'acceptance_time': cls._text(returned_message, 'q:dmAcceptanceTime'),
            'message_status': cls._text(returned_message, 'q:dmMessageStatus'),
            'attachment_size': cls._text(returned_message, 'q:dmAttachmentSize'),
            'files': files,
        }

    @classmethod
    def extract(cls, zfo_path: Path, output_dir: Optional[Path] = None) -> List[Path]:
        source_path = cls._resolve_path(zfo_path)
        root = cls._load_xml_root(source_path)
        files = cls._collect_files(root)
        if not files:
            return []

        target_dir = cls._resolve_path(output_dir) if output_dir is not None else source_path.with_suffix('')
        target_dir.mkdir(parents=True, exist_ok=True)

        written_files: List[Path] = []
        used_names = set()

        for index, file_info in enumerate(files, 1):
            filename = cls._safe_name(file_info.get('name'), f'attachment_{index}')
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            candidate = filename
            counter = 2
            while candidate.lower() in used_names:
                candidate = f"{stem}_{counter}{suffix}"
                counter += 1
            used_names.add(candidate.lower())

            output_path = target_dir / candidate
            output_path.write_bytes(file_info['content'])
            written_files.append(output_path.resolve())

        return written_files


@dataclass()
class DatovkaMessage:
    """
    Reprezentace zprávy z Datovky
    """
    message_id: str
    sender: str
    recipient: Optional[str] = None
    subject: str = "(bez předmětu)"
    delivery_time: Optional[datetime] = None
    read: bool = False
    personal_delivery: bool = False
    size: int = 0
    attachments: Optional[List[str]] = None

    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []

    def mark_as_read(self):
        """Označit zprávu jako přečtenou"""
        self.read = True

    def to_dict(self) -> Dict[str, Any]:
        """Konverze na slovník"""
        return {
            'message_id': self.message_id,
            'sender': self.sender,
            'recipient': self.recipient,
            'subject': self.subject,
            'delivery_time': self.delivery_time.isoformat() if self.delivery_time else None,
            'read': self.read,
            'personal_delivery': self.personal_delivery,
            'size': self.size,
            'attachments': self.attachments,
        }

    def to_json(self) -> str:
        """Konverze na JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __str__(self) -> str:
        status = "READ" if self.read else "NEW"
        return f"{status} [{self.message_id}] {self.subject} od {self.sender}"


class _HtmlTextExtractor(HTMLParser):
    """Jednoduchý převod HTML těla zprávy do čitelného textu."""

    BLOCK_TAGS = {
        'address', 'article', 'aside', 'blockquote', 'br', 'div', 'dl', 'fieldset',
        'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre', 'section', 'table',
        'tbody', 'td', 'tfoot', 'th', 'thead', 'tr', 'ul'
    }

    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Any]) -> None:
        if tag == 'li':
            self.parts.append('- ')
        elif tag in {'br', 'hr'}:
            self.parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCK_TAGS:
            self.parts.append('\n')

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        raw_text = html.unescape(''.join(self.parts)).replace('\xa0', ' ')
        lines = [' '.join(line.split()) for line in raw_text.splitlines()]
        non_empty_lines: List[str] = []
        previous_blank = False
        for line in lines:
            if line:
                non_empty_lines.append(line)
                previous_blank = False
            elif not previous_blank:
                non_empty_lines.append('')
                previous_blank = True
        return '\n'.join(non_empty_lines).strip() + '\n'


def _html_to_text(html_content: str) -> str:
    extractor = _HtmlTextExtractor()
    extractor.feed(html_content)
    extractor.close()
    return extractor.get_text()


class DatovkaMessageFilter:
    """
    Filtr pro zprávy
    """

    @staticmethod
    def unread_only(messages: List[DatovkaMessage]) -> List[DatovkaMessage]:
        """Vrátit pouze nepřečtené zprávy"""
        return [m for m in messages if not m.read]

    @staticmethod
    def by_sender(messages: List[DatovkaMessage], sender: str) -> List[DatovkaMessage]:
        """Filtrovat podle odesílatele"""
        return [m for m in messages if sender.lower() in m.sender.lower()]

    @staticmethod
    def by_subject(messages: List[DatovkaMessage], keyword: str) -> List[DatovkaMessage]:
        """Filtrovat podle klíčového slova v předmětu"""
        return [m for m in messages if keyword.lower() in m.subject.lower()]

    @staticmethod
    def after_date(messages: List[DatovkaMessage], date: datetime) -> List[DatovkaMessage]:
        """Filtrovat zprávy po určitém datu"""
        return [m for m in messages if m.delivery_time and m.delivery_time >= date]

    @staticmethod
    def with_attachments(messages: List[DatovkaMessage]) -> List[DatovkaMessage]:
        """Filtrovat pouze zprávy s přílohami"""
        return [m for m in messages if m.attachments]


class DatovkaStatistics:
    """
    Statistika pro zprávy
    """

    @staticmethod
    def count_total(messages: List[DatovkaMessage]) -> int:
        """Počet všech zpráv"""
        return len(messages)

    @staticmethod
    def count_unread(messages: List[DatovkaMessage]) -> int:
        """Počet nepřečtených zpráv"""
        return len([m for m in messages if not m.read])

    @staticmethod
    def count_read(messages: List[DatovkaMessage]) -> int:
        """Počet přečtených zpráv"""
        return len([m for m in messages if m.read])

    @staticmethod
    def total_size(messages: List[DatovkaMessage]) -> int:
        """Celková velikost zpráv v bytech"""
        return sum(m.size for m in messages)

    @staticmethod
    def senders_list(messages: List[DatovkaMessage]) -> Dict[str, int]:
        """Počet zpráv od každého odesílatele"""
        senders = {}
        for msg in messages:
            senders[msg.sender] = senders.get(msg.sender, 0) + 1
        return dict(sorted(senders.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def print_summary(messages: List[DatovkaMessage]) -> None:
        """Vytisknout shrnutí statistiky"""
        total = DatovkaStatistics.count_total(messages)
        unread = DatovkaStatistics.count_unread(messages)
        read = DatovkaStatistics.count_read(messages)
        size_mb = DatovkaStatistics.total_size(messages) / (1024 * 1024)
        senders = DatovkaStatistics.senders_list(messages)

        print("=" * 60)
        print("STATISTIKA ZPRÁV")
        print("=" * 60)
        print(f"Celkový počet zpráv:     {total}")
        print(f"  - Přečtené:            {read}")
        print(f"  - Nepřečtené:          {unread}")
        print(f"Celková velikost:        {size_mb:.2f} MB")
        print()
        print("Počet zpráv od odesílatelů:")
        for sender, count in senders.items():
            print(f"  {count:3d}x  {sender}")
        print("=" * 60)


class DatovkaExporter:
    """
    Export zpráv do různých formátů
    """

    @staticmethod
    def to_csv(messages: List[DatovkaMessage], filepath: str) -> None:
        """Export do CSV"""
        import csv

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['message_id', 'sender', 'subject', 'delivery_time', 'read']
            )
            writer.writeheader()

            for msg in messages:
                writer.writerow({
                    'message_id': msg.message_id,
                    'sender': msg.sender,
                    'subject': msg.subject,
                    'delivery_time': msg.delivery_time.isoformat() if msg.delivery_time else '',
                    'read': 'Ano' if msg.read else 'Ne',
                })

        print(f"OK: Zpravy exportovany do: {filepath}")

    @staticmethod
    def to_json(messages: List[DatovkaMessage], filepath: str) -> None:
        """Export do JSON"""
        data = [msg.to_dict() for msg in messages]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"OK: Zpravy exportovany do: {filepath}")

    @staticmethod
    def to_html(messages: List[DatovkaMessage], filepath: str) -> None:
        """Export do HTML"""
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Datovka - Seznam zpráv</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .read { color: #888; }
        .unread { font-weight: bold; }
    </style>
</head>
<body>
    <h1>Datovka - Přijaté zprávy</h1>
    <p>Vygenerováno: """ + datetime.now().isoformat() + """</p>
    <table>
        <tr>
            <th>ID zprávy</th>
            <th>Odesílatel</th>
            <th>Předmět</th>
            <th>Čas doručení</th>
            <th>Přečtena</th>
        </tr>
"""

        for msg in messages:
            read_class = "read" if msg.read else "unread"
            read_text = "Ano" if msg.read else "Ne"
            html += f"""        <tr class="{read_class}">
            <td>{msg.message_id}</td>
            <td>{msg.sender}</td>
            <td>{msg.subject}</td>
            <td>{msg.delivery_time.isoformat() if msg.delivery_time else 'N/A'}</td>
            <td>{read_text}</td>
        </tr>
"""

        html += """    </table>
</body>
</html>
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"OK: Zpravy exportovany do: {filepath}")


class DatovkaCLI:
    """CLI interface pro Datovka API"""

    def __init__(self, test_env: bool = True, env_file: Optional[Path] = None):
        self.client = None
        self.authenticated = False
        self.test_env = test_env
        self.env_file = env_file

    def init_client(self) -> bool:
        """Inicializace a autentifikace klienta"""
        username = os.environ.get('DATOVKA_USERNAME')
        password = os.environ.get('DATOVKA_PASSWORD')

        if not username or not password:
            if self.env_file is not None:
                env_path = self.env_file
                if not env_path.exists():
                    logger.error(f"ERROR: env soubor neexistuje: {env_path}")
                    return False
            else:
                env_path = Path.cwd() / ".env"
                if not env_path.exists():
                    logger.error(f"ERROR: .env soubor nenalezen v {Path.cwd()}")
                    logger.error("Použij --env-file PATH nebo nastav proměnné prostředí")
                    logger.error("DATOVKA_USERNAME, DATOVKA_PASSWORD")
                    return False

            load_dotenv(env_path, override=False)
            username = os.environ.get('DATOVKA_USERNAME')
            password = os.environ.get('DATOVKA_PASSWORD')

        if not username or not password:
            logger.error("ERROR: Chybí DATOVKA_USERNAME nebo DATOVKA_PASSWORD")
            return False

        self.client = DatovkaClient(username, password, test_env=self.test_env)

        if not self.client.connect():
            return False

        if not self.client.authenticate():
            return False

        self.authenticated = True
        return True

    def cmd_info(self, args):
        """Příkaz: info - Informace o datové schránce"""
        if not self.init_client():
            return 1

        print("\n" + "=" * 60)
        print("INFORMACE O DATOVÉ SCHRÁNCE")
        print("=" * 60)

        info = self.client.get_databox_info()
        if info:
            print(f"ID schránky:    {info['databox_id']}")
            print(f"Vlastník:       {info['owner']}")
            print(f"Adresa:         {info['address']}")
            print("=" * 60 + "\n")
            return 0
        return 1

    def cmd_list(self, args):
        """Příkaz: list - Listovat zprávy"""
        if not self.init_client():
            return 1

        days = args.days if hasattr(args, 'days') and args.days else 30
        limit = args.limit if hasattr(args, 'limit') and args.limit else 50

        print("\n" + "=" * 70)
        print(f"PŘIJATÉ ZPRÁVY (posledních {days} dní)")
        print("=" * 70)

        messages = self.client.get_received_messages(days=days, limit=limit)

        if not messages:
            print("Žádné zprávy k dispozici.")
            print("=" * 70 + "\n")
            return 0

        for i, msg in enumerate(messages, 1):
            status = "READ" if msg['read'] else "NEW"
            print(f"\n{i}. {status} {msg['subject']}")
            print(f"   ID:     {msg['message_id']}")
            print(f"   Od:     {msg['sender']}")
            print(f"   Čas:    {msg['delivery_time']}")

        print("\n" + "=" * 70)
        print(f"Celkem: {len(messages)} zpráv")
        print("=" * 70 + "\n")

        return 0

    def cmd_download(self, args):
        """Příkaz: download - Stáhnout zprávu"""
        if not self.init_client():
            return 1

        if getattr(args, 'body_output', None) and not getattr(args, 'body_format', None):
            print("\nERROR: --body-output vyzaduje --body-format\n")
            print("=" * 60 + "\n")
            return 1

        if getattr(args, 'extract_output', None) and not getattr(args, 'extract', False):
            print("\nERROR: --extract-output vyzaduje --extract\n")
            print("=" * 60 + "\n")
            return 1

        message_id = args.message_id
        output_dir = args.output if hasattr(args, 'output') and args.output else "./downloads"

        print("\n" + "=" * 60)
        print(f"STAHOVÁNÍ ZPRÁVY {message_id}")
        print("=" * 60 + "\n")

        filepath = self.client.download_message(message_id, output_dir=output_dir)

        if filepath:
            zfo_path = Path(filepath)
            print(f"\nOK: Zprava stazena: {filepath}\n")

            try:
                if getattr(args, 'inspect', False):
                    print("Metadata ZFO:")
                    self._print_zfo_info(DatovkaZfo.inspect(zfo_path))

                if getattr(args, 'extract', False):
                    extracted_files = DatovkaZfo.extract(
                        zfo_path,
                        output_dir=Path(args.extract_output) if getattr(args, 'extract_output', None) else None,
                    )
                    self._print_extracted_files(extracted_files)

                if getattr(args, 'body_format', None):
                    body_path = DatovkaZfo.export_body(
                        zfo_path,
                        args.body_format,
                        output_path=Path(args.body_output) if getattr(args, 'body_output', None) else None,
                    )
                    print(f"Telo zpravy exportovano do: {body_path}")
            except Exception as e:
                print(f"ERROR: {str(e)}\n")
                print("=" * 60 + "\n")
                return 1

            print("=" * 60 + "\n")
            return 0
        else:
            print("\nERROR: Chyba pri stahovani\n")
            print("=" * 60 + "\n")
            return 1

    @staticmethod
    def _print_zfo_info(info: Dict[str, Any]) -> None:
        print(f"Soubor:          {info['path']}")
        print(f"ID zprávy:       {info.get('message_id') or 'N/A'}")
        print(f"Odesílatel:      {info.get('sender') or 'N/A'}")
        print(f"Příjemce:        {info.get('recipient') or 'N/A'}")
        print(f"Předmět:         {info.get('subject') or 'N/A'}")
        print(f"Typ zprávy:      {info.get('message_type') or 'N/A'}")
        print(f"Doručení:        {info.get('delivery_time') or 'N/A'}")
        print(f"Přijetí:         {info.get('acceptance_time') or 'N/A'}")
        print(f"Stav zprávy:     {info.get('message_status') or 'N/A'}")
        print(f"Velikost příloh: {info.get('attachment_size') or 'N/A'}")

        files = info.get('files', [])
        print(f"Počet souborů:   {len(files)}")
        for index, file_info in enumerate(files, 1):
            print(
                f"  {index}. {file_info['name']} "
                f"({file_info['mime_type']}, {file_info['meta_type']}, {file_info['size']} B)"
            )

    @staticmethod
    def _print_extracted_files(files: List[Path]) -> None:
        if not files:
            print("Žádné soubory k extrakci.")
            return

        print("Extrahované soubory:")
        for file_path in files:
            print(f"  - {file_path}")

    def cmd_inspect(self, args):
        """Příkaz: inspect - Vypsat metadata ze ZFO souboru"""
        zfo_path = Path(args.zfo_path)

        print("\n" + "=" * 60)
        print(f"INSPEKT ZFO {zfo_path}")
        print("=" * 60 + "\n")

        try:
            info = DatovkaZfo.inspect(zfo_path)
        except Exception as e:
            print(f"ERROR: {str(e)}\n")
            print("=" * 60 + "\n")
            return 1

        self._print_zfo_info(info)

        print("\n" + "=" * 60 + "\n")
        return 0

    def cmd_extract(self, args):
        """Příkaz: extract - Rozbalit soubory ze ZFO"""
        zfo_path = Path(args.zfo_path)
        output_dir = Path(args.output) if hasattr(args, 'output') and args.output else None

        print("\n" + "=" * 60)
        print(f"EXTRAKCE ZFO {zfo_path}")
        print("=" * 60 + "\n")

        try:
            files = DatovkaZfo.extract(zfo_path, output_dir=output_dir)
        except Exception as e:
            print(f"ERROR: {str(e)}\n")
            print("=" * 60 + "\n")
            return 1

        self._print_extracted_files(files)

        print("\n" + "=" * 60 + "\n")
        return 0

    def cmd_export(self, args):
        """Příkaz: export - Exportovat zprávy"""
        if not self.init_client():
            return 1

        days = args.days if hasattr(args, 'days') and args.days else 30
        limit = args.limit if hasattr(args, 'limit') and args.limit else 100
        fmt = args.format if hasattr(args, 'format') and args.format else 'json'
        output = args.output if hasattr(args, 'output') and args.output else None

        print("\n" + "=" * 60)
        print(f"EXPORT ZPRÁV ({fmt.upper()} formát)")
        print("=" * 60 + "\n")

        logger.info(f"Stahování zpráv...")
        raw_messages = self.client.get_received_messages(days=days, limit=limit)

        if not raw_messages:
            print("Žádné zprávy k export.")
            print("=" * 60 + "\n")
            return 0

        messages = [
            DatovkaMessage(
                message_id=msg['message_id'],
                sender=msg['sender'],
                subject=msg['subject'],
                delivery_time=datetime.fromisoformat(str(msg['delivery_time']))
                    if msg['delivery_time'] else None,
                read=msg['read']
            )
            for msg in raw_messages
        ]

        os.makedirs("exports", exist_ok=True)

        if fmt == 'csv':
            filename = output or "exports/zpravy.csv"
            DatovkaExporter.to_csv(messages, filename)
        elif fmt == 'json':
            filename = output or "exports/zpravy.json"
            DatovkaExporter.to_json(messages, filename)
        elif fmt == 'html':
            filename = output or "exports/zpravy.html"
            DatovkaExporter.to_html(messages, filename)
        else:
            logger.error(f"Neznámý formát: {fmt}")
            return 1

        print("=" * 60 + "\n")
        return 0

    def cmd_stats(self, args):
        """Příkaz: stats - Statistika zpráv"""
        if not self.init_client():
            return 1

        days = args.days if hasattr(args, 'days') and args.days else 30
        limit = args.limit if hasattr(args, 'limit') and args.limit else 1000

        print("\nStahování zpráv...")
        raw_messages = self.client.get_received_messages(days=days, limit=limit)

        if not raw_messages:
            print("Žádné zprávy.")
            return 0

        messages = [
            DatovkaMessage(
                message_id=msg['message_id'],
                sender=msg['sender'],
                subject=msg['subject'],
                delivery_time=datetime.fromisoformat(str(msg['delivery_time']))
                    if msg['delivery_time'] else None,
                read=msg['read']
            )
            for msg in raw_messages
        ]

        print()
        DatovkaStatistics.print_summary(messages)
        print()
        return 0

    @staticmethod
    def configure_logging(level_name: str) -> None:
        """Nastaví úroveň logování pro root logger i lokální modul."""
        level = LOG_LEVELS[level_name]
        logging.getLogger().setLevel(level)
        logger.setLevel(level)

    @staticmethod
    def main():
        """CLI entry point"""
        parser = argparse.ArgumentParser(
            prog='datovka',
            description='Datovka (Czech Data Box) - CLI nástroj',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
    Příklady:
    datovka info                  Informace o datové schránce (testovací prostředí)
    datovka -p info               Informace o schránce (produkce)
    datovka list --days 30        Listovat zprávy za 30 dní
    datovka download <msg_id>     Stáhnout zprávu
    datovka download <msg_id> --inspect --extract --body-format txt
    datovka inspect <soubor.zfo>  Vypsat metadata ze ZFO
    datovka extract <soubor.zfo>  Rozbalit soubory ze ZFO
    datovka export --format csv   Exportovat do CSV
    datovka stats --days 30       Statistika zpráv
    datovka selftest              Spustit unit testy

    Defaultně se používá testovací prostředí. Pro produkci přidej -p / --production.

    Přihlašovací údaje se načítají z .env nebo proměnných prostředí
    (DATOVKA_USERNAME, DATOVKA_PASSWORD).
            """
        )

        common = argparse.ArgumentParser(add_help=False)
        common.add_argument('-p', '--production', action='store_true',
                            help='Použít produkční prostředí (default: testovací dry-run)')
        common.add_argument('--env-file', type=Path, default=None,
                            help='Cesta k env souboru (default: .env v CWD)')
        common.add_argument('--log-level', type=str.upper, choices=LOG_LEVELS.keys(), default='INFO',
                    help='Úroveň logování (default: INFO)')

        parser.add_argument('-p', '--production', action='store_true',
                            help='Použít produkční prostředí (default: testovací dry-run)')
        parser.add_argument('--env-file', type=Path, default=None,
                            help='Cesta k env souboru (default: .env v CWD)')
        parser.add_argument('--log-level', type=str.upper, choices=LOG_LEVELS.keys(), default='INFO',
                    help='Úroveň logování (default: INFO)')
        parser.add_argument('--version', action='version', version='Datovka CLI 1.0')

        subparsers = parser.add_subparsers(dest='command', help='Dostupné příkazy')

        subparsers.add_parser('info', parents=[common], help='Informace o datové schránce')

        list_parser = subparsers.add_parser('list', parents=[common], help='Listovat zprávy')
        list_parser.add_argument('--days', type=int, default=30, help='Počet dní (default: 30)')
        list_parser.add_argument('--limit', type=int, default=50, help='Maximálně zpráv (default: 50)')

        download_parser = subparsers.add_parser('download', parents=[common], help='Stáhnout zprávu')
        download_parser.add_argument('message_id', help='ID zprávy')
        download_parser.add_argument('-o', '--output', help='Výstupní adresář')
        download_parser.add_argument('--inspect', action='store_true',
                         help='Po stažení rovnou vypsat metadata ze ZFO')
        download_parser.add_argument('--extract', action='store_true',
                         help='Po stažení rovnou rozbalit soubory ze ZFO')
        download_parser.add_argument('--extract-output',
                         help='Výstupní adresář pro --extract')
        download_parser.add_argument('--body-format', choices=['txt', 'html'],
                         help='Exportovat tělo zprávy do TXT nebo HTML')
        download_parser.add_argument('--body-output',
                         help='Výstupní soubor pro --body-format')

        inspect_parser = subparsers.add_parser('inspect', parents=[common], help='Vypsat metadata ze ZFO')
        inspect_parser.add_argument('zfo_path', help='Cesta k ZFO souboru')

        extract_parser = subparsers.add_parser('extract', parents=[common], help='Rozbalit soubory ze ZFO')
        extract_parser.add_argument('zfo_path', help='Cesta k ZFO souboru')
        extract_parser.add_argument('-o', '--output', help='Výstupní adresář')

        export_parser = subparsers.add_parser('export', parents=[common], help='Exportovat zprávy')
        export_parser.add_argument('--format', choices=['csv', 'json', 'html'], default='json',
                                help='Formát exportu (default: json)')
        export_parser.add_argument('--days', type=int, default=30, help='Počet dní')
        export_parser.add_argument('--limit', type=int, default=100, help='Maximálně zpráv')
        export_parser.add_argument('-o', '--output', help='Výstupní soubor')

        stats_parser = subparsers.add_parser('stats', parents=[common], help='Statistika zpráv')
        stats_parser.add_argument('--days', type=int, default=30, help='Počet dní')
        stats_parser.add_argument('--limit', type=int, default=1000, help='Maximálně zpráv')

        subparsers.add_parser('selftest', help='Spustit unit testy balíčku')

        args = parser.parse_args()

        DatovkaCLI.configure_logging(args.log_level)

        if not args.command:
            parser.print_help()
            return 0

        if args.command == 'selftest':
            return run_tests(args)

        cli = DatovkaCLI(test_env=not args.production, env_file=args.env_file)

        if args.command == 'info':
            return cli.cmd_info(args)
        elif args.command == 'list':
            return cli.cmd_list(args)
        elif args.command == 'download':
            return cli.cmd_download(args)
        elif args.command == 'inspect':
            return cli.cmd_inspect(args)
        elif args.command == 'extract':
            return cli.cmd_extract(args)
        elif args.command == 'export':
            return cli.cmd_export(args)
        elif args.command == 'stats':
            return cli.cmd_stats(args)
        else:
            parser.print_help()
            return 1


def cli_main():
    """Top-level CLI entry point for python -m datovka and console_scripts."""
    return DatovkaCLI.main()
