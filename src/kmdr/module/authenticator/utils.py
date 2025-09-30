from typing import Optional, Callable

from aiohttp import ClientSession
from rich.console import Console
from urllib.parse import urljoin, urlsplit

from kmdr.core.error import LoginError
from kmdr.core.utils import async_retry
from kmdr.core.constants import API_ROUTE, BASE_URL

NICKNAME_ID = 'div_nickname_display'

VIP_ID = 'div_user_vip'
NOR_ID = 'div_user_nor'
LV1_ID = 'div_user_lv1'

@async_retry()
async def check_status(
        session: ClientSession,
        console: Console,
        base_url: str = BASE_URL.KXO,
        show_quota: bool = False,
        is_vip_setter: Optional[Callable[[int], None]] = None,
        level_setter: Optional[Callable[[int], None]] = None,
) -> bool:
    async with session.get(url = urljoin(base_url, API_ROUTE.PROFILE)) as response:
        try:
            response.raise_for_status()
        except Exception as e:
            console.print(f"Error: {type(e).__name__}: {e}")
            return False
        
        if response.history and any(resp.status in (301, 302, 307) for resp in response.history) \
                and str(response.url) == urljoin(base_url, API_ROUTE.LOGIN):
            raise LoginError("凭证已失效，请重新登录。", ['kmdr config -c cookie', 'kmdr login -u <username>'])

        if not is_vip_setter and not level_setter and not show_quota:
            return True
        
        from bs4 import BeautifulSoup

        # 如果后续有性能问题，可以先考虑使用 lxml 进行解析
        soup = BeautifulSoup(await response.text(), 'html.parser')

        script = soup.find('script', language="javascript")

        if script:
            var_define = extract_var_define(script.text[:100])

            is_vip = int(var_define.get('is_vip', '0'))
            user_level = int(var_define.get('user_level', '0'))

            if is_vip_setter:
                is_vip_setter(is_vip)
            if level_setter:
                level_setter(user_level)
        
        if not show_quota:
            return True

        nickname = soup.find('div', id=NICKNAME_ID).text.strip().split(' ')[0]
        quota = soup.find('div', id=__resolve_quota_id(is_vip, user_level)).text.strip()

        console.print(f"\n当前登录为 [bold cyan]{nickname}[/bold cyan]\n\n{quota}")
        return True

def extract_var_define(script_text) -> dict[str, str]:
    var_define = {}
    for line in script_text.splitlines():
        line = line.strip()
        if line.startswith("var ") and "=" in line:
            var_name, var_value = line[4:].split("=", 1)
            var_define[var_name.strip()] = var_value.strip().strip(";").strip('"')
    return var_define

def __resolve_quota_id(is_vip: Optional[int] = None, user_level: Optional[int] = None):
    if is_vip is not None and is_vip >= 1:
        return VIP_ID
    
    if user_level is not None and user_level <= 1:
        return LV1_ID
    
    return NOR_ID

def extract_base_url(url: Optional[str], default: Optional[str] = None) -> Optional[str]:
    if not url:
        return default

    parsed = urlsplit(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"

    return default
