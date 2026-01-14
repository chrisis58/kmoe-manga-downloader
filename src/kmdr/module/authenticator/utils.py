from typing import Optional, Union
import re

from aiohttp import ClientSession
from rich.console import Console
from bs4 import BeautifulSoup, Tag
from yarl import URL

from kmdr.core.error import LoginError
from kmdr.core.utils import async_retry, extract_cookies
from kmdr.core.constants import API_ROUTE
from kmdr.core.console import *
from kmdr.core.structure import Credential, QuotaInfo

NICKNAME_ID = 'div_nickname_display'

VIP_ID = 'div_user_vip'
NOR_ID = 'div_user_nor'
LV1_ID = 'div_user_lv1'

PATTERN_USER_RESET = r'Lv\d+\s*額度\s*:\s*每月\s*(\d+)\s*日'
PATTERN_USER_TOTAL = r'Lv\d+\s*每月額度\s*:\s*([\d.]+)\s*M'
PATTERN_USER_USED = r'本月已用免費額度\s*:\s*([\d.]+)\s*M'

PATTERN_VIP_RESET = r'VIP\s*額度\s*:\s*每月\s*(\d+)\s*日'
PATTERN_VIP_TOTAL = r'VIP\s*每月額度\s*:\s*([\d.]+)\s*M'
PATTERN_VIP_USED = r'本月已經用VIP額度\s*:\s*([\d.]+)\s*M'

@async_retry()
async def check_status(
        session: ClientSession,
        console: Console,
        username: str,
        cookies: dict[str, str],
        show_quota: bool = False,
) -> Credential:
    async with session.get(url = API_ROUTE.PROFILE, cookies=cookies) as response:
        response.raise_for_status()
        
        if response.history and any(resp.status in (301, 302, 307) for resp in response.history) \
                and URL(response.url).path == API_ROUTE.LOGIN:
            raise LoginError("凭证已失效，请重新登录。", ['kmdr config -c cookie', 'kmdr login -u <username>'])
        
        cookies = extract_cookies(response)

        # 如果后续有性能问题，可以先考虑使用 lxml 进行解析
        soup = BeautifulSoup(await response.text(), 'html.parser')

        script = soup.find('script', language="javascript")

        if script:
            var_define = extract_var_define(script.text[:100])

            is_vip = int(var_define.get('is_vip', '0'))
            user_level = int(var_define.get('user_level', '0'))

            debug("解析到用户状态: is_vip=", is_vip, ", user_level=", user_level)

        else:
            is_vip = None
            user_level = None
        
        nickname = soup.find('div', id=NICKNAME_ID).text.strip().split(' ')[0].replace('\xa0', '')
        raw_quota = soup.find('div', id=__resolve_quota_id(is_vip, user_level)).text.strip().replace('\xa0', '')

        if show_quota:
            if console.is_interactive:
                info(f"\n当前登录为 [bold cyan]{nickname}[/bold cyan]\n\n{raw_quota}")
            else:
                info(f"当前登录为 {nickname}")

        user_quota, vip_quota = extract_quota(soup)
        
        return Credential(
            username=username,
            nickname=nickname,
            cookies=cookies,
            user_quota=user_quota,
            vip_quota=vip_quota,
            level=user_level or 0,
        )

def extract_var_define(script_text) -> dict[str, str]:
    var_define = {}
    for line in script_text.splitlines():
        line = line.strip()
        if line.startswith("var ") and "=" in line:
            var_name, var_value = line[4:].split("=", 1)
            var_value = var_value.strip().strip(";").strip('"')
            if var_name and var_value:
                var_define[var_name.strip()] = var_value
    debug("解析到变量定义: ", var_define)
    return var_define

def extract_quota(soup: BeautifulSoup) -> tuple[QuotaInfo, Union[QuotaInfo, None]]:
    is_vip = False
    vip_div = soup.find('div', id=VIP_ID)
    
    if isinstance(vip_div, Tag):
        style = vip_div.get('style', '')
        if isinstance(style, list):
            style = ' '.join(style)

        style_str = style.lower().replace(' ', '') if style else ''

        if 'display:none' not in style_str:
            is_vip = True
            
    raw_text = soup.get_text(separator=' ', strip=True)

    user_quota = QuotaInfo(
        reset_day=_extract_int(PATTERN_USER_RESET, raw_text, default=1),
        total=_extract_float(PATTERN_USER_TOTAL, raw_text, default=0.0),
        used=_extract_float(PATTERN_USER_USED, raw_text, default=0.0)
    )

    vip_quota = None
    if is_vip:
        vip_quota = QuotaInfo(
            reset_day=_extract_int(PATTERN_VIP_RESET, raw_text, default=1),
            total=_extract_float(PATTERN_VIP_TOTAL, raw_text, default=0.0),
            used=_extract_float(PATTERN_VIP_USED, raw_text, default=0.0)
        )

    return user_quota, vip_quota

def _extract_int(pattern: str, text: str, default: int = 0) -> int:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else default

def _extract_float(pattern: str, text: str, default: float = 0.0) -> float:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else default

def __resolve_quota_id(is_vip: Optional[int] = None, user_level: Optional[int] = None):
    if is_vip is not None and is_vip >= 1:
        return VIP_ID
    
    if user_level is not None and user_level <= 1:
        return LV1_ID
    
    return NOR_ID
