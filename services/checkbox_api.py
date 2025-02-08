# services/checkbox_api.py
import aiohttp
import logging
from config.settings import BASE_URL, CLIENT_NAME, CLIENT_VERSION

logger = logging.getLogger(__name__)

async def get_cashier_token(license_key, pin_code):
    headers = {
        'Content-Type': 'application/json',
        'X-License-Key': license_key,
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION,
    }
    url = f"{BASE_URL}/cashier/signinPinCode"
    data = {'pin_code': pin_code}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get('access_token')
                else:
                    logger.error(f"get_cashier_token: {resp.status}")
                    return None
        except Exception as e:
            logger.exception(f"get_cashier_token exception: {e}")
            return None

async def get_current_shift_id(license_key, cashier_token):
    headers = {
        'Authorization': f'Bearer {cashier_token}',
        'X-License-Key': license_key,
        'Accept': 'application/json',
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION,
    }
    url = f"{BASE_URL}/shifts"
    params = {
        'limit': 1,
        'offset': 0,
        'desc': 'false',
        'statuses': ['OPENED']
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get('results', [])
                    if results:
                        return results[0].get('id')
                    return None
                else:
                    logger.error(f"get_current_shift_id: {resp.status}")
                    return None
        except Exception as e:
            logger.exception(f"get_current_shift_id exception: {e}")
            return None

async def get_shift_info(license_key, cashier_token, shift_id):
    headers = {
        'Authorization': f'Bearer {cashier_token}',
        'X-License-Key': license_key,
        'Accept': 'application/json',
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION,
    }
    url = f"{BASE_URL}/shifts/{shift_id}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"get_shift_info: {resp.status}")
                    return None
        except Exception as e:
            logger.exception(f"get_shift_info exception: {e}")
            return None

async def get_kasa_name(license_key, cashier_token):
    headers = {
        'Authorization': f'Bearer {cashier_token}',
        'X-License-Key': license_key,
        'Accept': 'application/json',
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION,
    }
    url = f"{BASE_URL}/cash-register"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('title', 'Невідома каса')
                else:
                    logger.error(f"get_kasa_name: {resp.status}")
                    return 'Невідома каса'
        except Exception as e:
            logger.exception(f"get_kasa_name exception: {e}")
            return 'Невідома каса'

async def get_recent_receipts(license_key, cashier_token, shift_id, from_date, to_date):
    headers = {
        'Authorization': f'Bearer {cashier_token}',
        'X-License-Key': license_key,
        'Accept': 'application/json',
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION,
    }
    url = f"{BASE_URL}/receipts/search"
    params = {
        'shift_id': [shift_id],
        'self_receipts': 'true',
        'desc': 'false',
        'limit': 1000,
        'offset': 0,
        'from_date': from_date.isoformat(),
        'to_date': to_date.isoformat()
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('results', [])
                else:
                    logger.error(f"get_recent_receipts: {resp.status}")
        except Exception as e:
            logger.exception(f"get_recent_receipts exception: {e}")
    return []

async def get_receipt_pdf(kasa_info, receipt_id):
    headers = {
        'Authorization': f'Bearer {kasa_info.get("cashier_token")}',
        'X-License-Key': kasa_info.get('license_key'),
        'Accept': 'application/json',
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION
    }
    url = f"{BASE_URL}/receipts/{receipt_id}/pdf"

    import aiohttp
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    logger.error(f"get_receipt_pdf: {resp.status}")
                    return None
        except Exception as e:
            logger.exception(f"get_receipt_pdf exception: {e}")
            return None