# services/checkbox_api.py
import aiohttp
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from config.settings import BASE_URL, CLIENT_NAME, CLIENT_VERSION
from datetime import datetime

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
        
async def get_receipt_pdf(kasa, receipt_id):
    """
    Отримання PDF представлення чека за заданим receipt_id.
    Використовується GET /api/v1/receipts/{receipt_id}/pdf із параметрами:
      - is_second_copy: false
      - download: false
    """
    headers = {
        'Authorization': f'Bearer {kasa["cashier_token"]}',
        'X-License-Key': kasa["license_key"],
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION,
        'Accept': 'application/pdf'
    }
    params = {
        'is_second_copy': 'false',
        'download': 'false'
    }
    url = f"{BASE_URL}/receipts/{receipt_id}/pdf"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    pdf_data = await resp.read()
                    if pdf_data.startswith(b'%PDF-'):
                        logger.info(f"[get_receipt_pdf] Successfully retrieved PDF for receipt {receipt_id}")
                        return pdf_data
                    else:
                        logger.error(f"[get_receipt_pdf] Returned data does not look like a PDF for receipt {receipt_id}.")
                        return None
                else:
                    text = await resp.text()
                    logger.error(f"[get_receipt_pdf] Error fetching receipt PDF: Status {resp.status}, Response: {text}")
                    return None
        except Exception as e:
            logger.error(f"[get_receipt_pdf] Exception while fetching receipt PDF: {str(e)}")
            return None

async def get_report_receipt_info(license_key, cashier_token, is_z_report, shift_id, from_date, to_date):
    """
    Запит до GET /api/v1/reports для отримання звітів (X або Z) за заданий часовий діапазон.
    Повертається список звітів (results).
    Параметри:
      - is_z_report: True для Z звіту, False для X звіту.
      - shift_id: рядок (передається як масив із одним елементом).
      - from_date, to_date: часові діапазони (ISO‑рядки).
      - Додатково: desc=false, offset=0, limit=25.
    """
    headers = {
        'Authorization': f'Bearer {cashier_token}',
        'X-License-Key': license_key,
        'X-Client-Name': CLIENT_NAME,
        'X-Client-Version': CLIENT_VERSION,
        'Accept': 'application/json'
    }
    
    params = {
        'from_date': from_date,
        'to_date': to_date,
        'shift_id': [shift_id],
        'is_z_report': 'true' if is_z_report else 'false',
        'desc': 'false',
        'offset': 0,
        'limit': 25
    }
    
    url = f"{BASE_URL}/reports"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    json_resp = await resp.json()
                    results = json_resp.get("results", [])
                    if results:
                        logger.info(f"[get_report_receipt_info] Found {len(results)} report(s) for shift {shift_id}")
                        return results
                    else:
                        logger.error(f"[get_report_receipt_info] No reports found for shift {shift_id}")
                        return []
                else:
                    text = await resp.text()
                    logger.error(f"[get_report_receipt_info] Error fetching reports: Status {resp.status}, Response: {text}")
                    return []
        except Exception as e:
            logger.error(f"[get_report_receipt_info] Exception while fetching reports: {str(e)}")
            return []

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