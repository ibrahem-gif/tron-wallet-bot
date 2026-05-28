"""
tron.py - التكامل مع شبكة TRON عبر TronGrid API
يعمل بدون أي وسيط خارجي - مباشر مع البلوكتشين
"""

import os
import time
import requests
import hashlib
import base58
import ecdsa
import binascii
from typing import Optional, Dict, Any

# ==================== الإعدادات ====================
TRON_API_KEY    = os.getenv("TRON_API_KEY", "")
WALLET_ADDRESS  = os.getenv("WALLET_ADDRESS", "")
PRIVATE_KEY_HEX = os.getenv("PRIVATE_KEY", "")   # لا يُطبع أبداً
USDT_CONTRACT   = os.getenv("USDT_CONTRACT", "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")

TRONGRID_BASE = "https://api.trongrid.io"
HEADERS = {
    "TRON-PRO-API-KEY": TRON_API_KEY,
    "Content-Type": "application/json",
}

USDT_DECIMALS = 6  # USDT TRC20 = 6 decimals


# ==================== مساعدات العنونة ====================

def base58check_to_hex(address: str) -> str:
    """تحويل عنوان TRON من Base58 إلى Hex"""
    decoded = base58.b58decode_check(address)
    return decoded.hex()


def hex_to_base58check(hex_addr: str) -> str:
    """تحويل عنوان Hex إلى Base58 TRON"""
    raw = bytes.fromhex(hex_addr)
    return base58.b58encode_check(raw).decode()


def address_to_hex_no_prefix(address: str) -> str:
    """تحويل عنوان TRON إلى hex بدون 0x للاستخدام في ABI"""
    raw_hex = base58check_to_hex(address)
    # أزل بادئة 41 (TRON prefix) واحصل على 20 بايت
    return raw_hex[2:].zfill(64)


def encode_transfer_data(to_address: str, amount_sun: int) -> str:
    """ترميز بيانات استدعاء دالة transfer(address,uint256) في TRC20"""
    # function selector: keccak256("transfer(address,uint256)")[:4]
    func_selector = "a9059cbb"
    # ترميز العنوان (32 بايت، محاذاة يسار)
    addr_hex = address_to_hex_no_prefix(to_address)
    # ترميز المبلغ (32 بايت، محاذاة يمين)
    amount_hex = hex(amount_sun)[2:].zfill(64)
    return func_selector + addr_hex + amount_hex


# ==================== التوقيع الرقمي ====================

def sign_transaction(tx_data: dict) -> Optional[dict]:
    """توقيع معاملة TRON بالمفتاح الخاص - المفتاح لا يُطبع أبداً"""
    try:
        if not PRIVATE_KEY_HEX:
            raise ValueError("PRIVATE_KEY غير محدد في متغيرات البيئة")

        raw_data_hex = tx_data.get("txID") or tx_data.get("raw_data_hex")
        if not raw_data_hex:
            # احسب raw_data_hex من raw_data إذا غير موجود
            import json
            raw_data_hex = tx_data.get("txID", "")

        txid = tx_data["txID"]
        txid_bytes = bytes.fromhex(txid)

        private_key_bytes = bytes.fromhex(PRIVATE_KEY_HEX)
        signing_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)

        signature = signing_key.sign_digest(txid_bytes, sigencode=ecdsa.util.sigencode_string)
        signature_hex = signature.hex() + "00"  # TRON يضيف recovery id

        tx_data["signature"] = [signature_hex]
        return tx_data

    except Exception as e:
        print(f"[TRON] خطأ في التوقيع: {e}")
        return None


# ==================== استعلامات TronGrid ====================

def get_trc20_balance(address: str) -> float:
    """الحصول على رصيد USDT TRC20 للعنوان"""
    try:
        url = f"{TRONGRID_BASE}/v1/accounts/{address}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()

        if "data" not in data or not data["data"]:
            return 0.0

        trc20_list = data["data"][0].get("trc20", [])
        for token in trc20_list:
            if USDT_CONTRACT in token:
                raw = int(token[USDT_CONTRACT])
                return raw / (10 ** USDT_DECIMALS)
        return 0.0

    except Exception as e:
        print(f"[TRON] خطأ في جلب الرصيد: {e}")
        return 0.0


def get_recent_trc20_transactions(address: str, limit: int = 20) -> list:
    """جلب آخر معاملات TRC20 الواردة إلى العنوان"""
    try:
        url = f"{TRONGRID_BASE}/v1/accounts/{address}/transactions/trc20"
        params = {
            "limit": limit,
            "contract_address": USDT_CONTRACT,
            "only_to": "true",
            "order_by": "block_timestamp,desc",
        }
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        data = resp.json()
        return data.get("data", [])

    except Exception as e:
        print(f"[TRON] خطأ في جلب المعاملات: {e}")
        return []


def get_transaction_info(txid: str) -> Optional[Dict[str, Any]]:
    """الحصول على تفاصيل معاملة بالـ TXID"""
    try:
        url = f"{TRONGRID_BASE}/wallet/gettransactionbyid"
        resp = requests.post(url, json={"value": txid}, headers=HEADERS, timeout=15)
        data = resp.json()
        return data if data else None
    except Exception as e:
        print(f"[TRON] خطأ في جلب المعاملة {txid}: {e}")
        return None


def verify_transaction_confirmed(txid: str) -> bool:
    """التحقق من أن المعاملة مؤكدة على البلوكتشين"""
    try:
        url = f"{TRONGRID_BASE}/wallet/gettransactioninfobyid"
        resp = requests.post(url, json={"value": txid}, headers=HEADERS, timeout=15)
        data = resp.json()
        # إذا وجد blockNumber فالمعاملة مؤكدة
        return bool(data.get("blockNumber"))
    except Exception as e:
        print(f"[TRON] خطأ في التحقق من التأكيد: {e}")
        return False


# ==================== إرسال USDT ====================

def build_trc20_transfer(to_address: str, amount_usdt: float) -> Optional[dict]:
    """بناء معاملة تحويل USDT TRC20"""
    try:
        amount_sun = int(amount_usdt * (10 ** USDT_DECIMALS))
        data_hex = encode_transfer_data(to_address, amount_sun)

        url = f"{TRONGRID_BASE}/wallet/triggersmartcontract"
        payload = {
            "owner_address": base58check_to_hex(WALLET_ADDRESS),
            "contract_address": base58check_to_hex(USDT_CONTRACT),
            "function_selector": "transfer(address,uint256)",
            "parameter": encode_transfer_data(to_address, amount_sun)[8:],  # بدون function selector
            "fee_limit": 40_000_000,  # 40 TRX حد أقصى للرسوم
            "call_value": 0,
            "visible": False,
        }
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=15)
        result = resp.json()

        if result.get("result", {}).get("result") is not True:
            print(f"[TRON] فشل بناء المعاملة: {result}")
            return None

        return result.get("transaction")

    except Exception as e:
        print(f"[TRON] خطأ في بناء المعاملة: {e}")
        return None


def broadcast_transaction(signed_tx: dict) -> Optional[str]:
    """إذاعة المعاملة الموقعة على الشبكة"""
    try:
        url = f"{TRONGRID_BASE}/wallet/broadcasttransaction"
        resp = requests.post(url, json=signed_tx, headers=HEADERS, timeout=20)
        result = resp.json()

        if result.get("result") is True:
            txid = signed_tx.get("txID", "")
            print(f"[TRON] ✅ تم الإرسال بنجاح: {txid}")
            return txid

        print(f"[TRON] فشل الإذاعة: {result}")
        return None

    except Exception as e:
        print(f"[TRON] خطأ في الإذاعة: {e}")
        return None


def send_usdt(to_address: str, amount_usdt: float) -> Optional[str]:
    """
    الدالة الرئيسية لإرسال USDT TRC20
    تُرجع TXID إذا نجح الإرسال، أو None إذا فشل
    المفتاح الخاص لا يُطبع ولا يُرسل أبداً
    """
    if not PRIVATE_KEY_HEX:
        print("[TRON] ❌ خطأ: لم يتم تعيين مفتاح التوقيع في .env")
        return None

    if not WALLET_ADDRESS:
        print("[TRON] ❌ WALLET_ADDRESS غير محدد")
        return None

    # التحقق من صحة العنوان
    if not is_valid_tron_address(to_address):
        print(f"[TRON] ❌ عنوان غير صحيح: {to_address}")
        return None

    # بناء المعاملة
    tx = build_trc20_transfer(to_address, amount_usdt)
    if not tx:
        return None

    # توقيع المعاملة
    signed_tx = sign_transaction(tx)
    if not signed_tx:
        return None

    # إذاعة على الشبكة
    txid = broadcast_transaction(signed_tx)
    return txid


def is_valid_tron_address(address: str) -> bool:
    """التحقق من صحة عنوان TRON"""
    try:
        if not address or not address.startswith("T"):
            return False
        decoded = base58.b58decode_check(address)
        return len(decoded) == 21 and decoded[0] == 0x41
    except Exception:
        return False


def sun_to_usdt(sun: int) -> float:
    """تحويل من Sun إلى USDT"""
    return sun / (10 ** USDT_DECIMALS)


def usdt_to_sun(usdt: float) -> int:
    """تحويل من USDT إلى Sun"""
    return int(usdt * (10 ** USDT_DECIMALS))