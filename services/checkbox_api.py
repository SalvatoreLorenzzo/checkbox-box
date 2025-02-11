# services/checkbox_api.py
import aiohttp
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from config.settings import BASE_URL, CLIENT_NAME, CLIENT_VERSION

logger = logging.getLogger(__name__)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_cashier_token(license_key, pin_code):
    headers = {
        'X-License-Key': license_key,
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION,
        'Content-Type': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BASE_URL}/cashier/signinPinCode",
                headers=headers,
                json={'pin_code': pin_code}
            ) as resp:
                if resp.status == 200:
                    return (await resp.json()).get('access_token')
                logger.error(f"Auth error: {await resp.text()}")
                return None
        except Exception as e:
            logger.error(f"Auth request error: {str(e)}")
            raise

async def get_current_shift_id(license_key, cashier_token):
    headers = {
        'Authorization': f'Bearer {cashier_token}',
        'X-License-Key': license_key,
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION
    }
    
    params = {
        'statuses[]': ['OPENED', 'OPENING'],  # Фікс параметрів запиту
        'limit': 1,
        'desc': 'true'  # Отримуємо останню активну зміну
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{BASE_URL}/shifts",
                headers=headers,
                params=params
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.debug(f"Shifts API response: {data}")  # Додаткове логування
                    return data['results'][0]['id'] if data['results'] else None
                logger.error(f"Shifts error {resp.status}: {await resp.text()}")
                return None
        except Exception as e:
            logger.error(f"Shifts request error: {str(e)}")
            return None
        
async def get_receipt_info(receipt_id, license_key, cashier_token):
    """
    Отримання повної інформації про чек за ID.
    Використовує GET /api/v1/receipts/{receipt_id}.
    """
    headers = {
        'X-License-Key': license_key,
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION,
        'Authorization': f'Bearer {cashier_token}',
        'Accept': 'application/json'
    }
    url = f"{BASE_URL}/receipts/{receipt_id}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    receipt_data = await resp.json()
                    logger.info(f"[get_receipt_info] Successfully retrieved receipt info for {receipt_id}")
                    return receipt_data
                else:
                    text = await resp.text()
                    logger.error(f"[get_receipt_info] Error fetching receipt {receipt_id}: Status {resp.status}, Response: {text}")
                    return None
        except Exception as err:
            logger.error(f"[get_receipt_info] Exception while fetching receipt {receipt_id}: {str(err)}")
            return None

async def get_shift_info(license_key, cashier_token, shift_id):
    headers = {
        'Authorization': f'Bearer {cashier_token}',
        'X-License-Key': license_key,
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{BASE_URL}/shifts/{shift_id}",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.error(f"Shift info error {resp.status}: {await resp.text()}")
                return None
        except Exception as e:
            logger.error(f"Shift info request error: {str(e)}")
            return None

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{BASE_URL}/shifts/{shift_id}",
                headers=headers
            ) as resp:
                return await resp.json() if resp.status == 200 else None
        except Exception as e:
            logger.error(f"Помилка інформації зміни: {str(e)}")
            return None

async def get_kasa_name(license_key, cashier_token):
    headers = {
        'Authorization': f'Bearer {cashier_token}',
        'X-License-Key': license_key,
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/cash-register", headers=headers) as resp:
                if resp.status == 200:
                    return (await resp.json()).get('title', 'Невідома каса')
                return 'Невідома каса'
        except Exception as e:
            logger.error(f"Помилка назви каси: {str(e)}")
            return 'Невідома каса'

async def get_recent_receipts(license_key, cashier_token, shift_id, from_date, to_date):
    all_receipts = []
    limit = 100
    offset = 0
    
    headers = {
        'Authorization': f'Bearer {cashier_token}',
        'X-License-Key': license_key,
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION
    }
    
    async with aiohttp.ClientSession() as session:
        while True:
            params = {
                'shift_id[]': shift_id,
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat(),
                'limit': limit,
                'offset': offset
            }
            
            try:
                async with session.get(
                    f"{BASE_URL}/receipts/search",
                    headers=headers,
                    params=params
                ) as resp:
                    if resp.status != 200:
                        break
                    
                    data = await resp.json()
                    results = data.get('results', [])
                    all_receipts.extend(results)
                    
                    if len(results) < limit:
                        break
                    offset += limit
            except Exception as e:
                logger.error(f"Помилка пошуку чеків: {str(e)}")
                break
    
    return all_receipts

async def get_receipt_pdf(kasa_info, receipt_id):
    headers = {
        'Authorization': f'Bearer {kasa_info["cashier_token"]}',
        'X-License-Key': kasa_info['license_key'],
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{BASE_URL}/receipts/{receipt_id}/pdf",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    pdf_data = await resp.read()
                    return pdf_data if pdf_data.startswith(b'%PDF-') else None
                return None
        except Exception as e:
            logger.error(f"Помилка PDF: {str(e)}")
            return None