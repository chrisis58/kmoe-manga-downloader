import re
from typing import Optional, Union

from aiohttp import ClientSession
from bs4 import BeautifulSoup, Tag
from rich.console import Console
from yarl import URL

from kmdr.core.console import debug, info
from kmdr.core.constants import API_ROUTE
from kmdr.core.error import HtmlResolveError, LoginError
from kmdr.core.structure import Credential, CredentialStatus, QuotaInfo
from kmdr.core.utils import async_retry, extract_cookies

NICKNAME_ID = "div_nickname_display"

NOT_APPLICABLE = "N/A"

VIP_ID = "div_user_vip"
NOR_ID = "div_user_nor"
LV1_ID = "div_user_lv1"

PATTERN_USER_RESET = r"Lv\d+\s*額度\s*:\s*每月\s*(\d+)\s*日"
PATTERN_USER_TOTAL = r"Lv\d+\s*每月額度\s*:\s*([\d.]+)\s*M"
PATTERN_USER_USED = r"本月已用免費額度\s*:\s*([\d.]+)\s*M"

PATTERN_VIP_RESET = r"VIP\s*額度\s*:\s*每月\s*(\d+)\s*日"
PATTERN_VIP_TOTAL = r"VIP\s*每月額度\s*:\s*([\d.]+)\s*M"
PATTERN_VIP_USED = r"本月已經用VIP額度\s*:\s*([\d.]+)\s*M"


@async_retry()
async def check_status(
    session: ClientSession,
    console: Console,
    username: str,
    cookies: dict[str, str],
    show_quota: bool = False,
) -> Credential:
    async with session.get(url=API_ROUTE.PROFILE, cookies=cookies) as response:
        response.raise_for_status()

        if response.history and any(resp.status in (301, 302, 307) for resp in response.history) and URL(response.url).path == API_ROUTE.LOGIN:
            raise LoginError(
                "凭证已失效，请重新登录。",
                ["kmdr config -c cookie", "kmdr login -u <username>"],
            )

        cookies = {**cookies, **extract_cookies(response)}

        # 如果后续有性能问题，可以先考虑使用 lxml 进行解析
        soup = BeautifulSoup(await response.text(), "html.parser")

        var_define = {}
        for script in soup.find_all("script"):
            var_define.update(extract_var_define(script.text))

        is_vip = _extract_status_int(var_define, "is_vip")
        user_level = _extract_status_int(var_define, "user_level")

        debug("解析到用户状态: is_vip=", is_vip, ", user_level=", user_level)

        nickname = _extract_text_by_selector(soup, f"tr#{NICKNAME_ID} td:nth-of-type(2)")
        raw_quota = _extract_text_by_selector(soup, f"div#{__resolve_quota_id(is_vip, user_level)}")

        if show_quota:
            if console.is_interactive:
                info(f"\n当前登录为 [bold cyan]{nickname}[/bold cyan]\n\n{raw_quota}")
            else:
                info(f"当前登录为 {nickname}")

        quota_known = True
        try:
            user_quota, vip_quota = extract_quota(soup)
        except HtmlResolveError as e:
            info(f"[yellow]无法解析账号额度，将继续尝试下载，以服务器返回结果为准：{e.message}[/yellow]")
            quota_known = False
            user_quota = QuotaInfo(reset_day=1, total=0.0, used=0.0)
            vip_quota = QuotaInfo(reset_day=1, total=0.0, used=0.0) if is_vip or _has_vip_quota(soup) else None

        total_remaining = user_quota.total - user_quota.used + (vip_quota.total - vip_quota.used if vip_quota else 0.0)
        debug(f"用户 {username} 当前剩余额度: {f'{total_remaining:.2f} MB' if quota_known else '未知'}")

        return Credential(
            username=username,
            nickname=nickname,
            cookies=cookies,
            user_quota=user_quota,
            vip_quota=vip_quota,
            level=user_level or 0,
            status=CredentialStatus.ACTIVE if not quota_known or total_remaining > 0.1 else CredentialStatus.QUOTA_EXCEEDED,
            quota_known=quota_known,
        )


def _extract_status_int(var_define: dict[str, str], name: str) -> int:
    try:
        return int(var_define[name])
    except (KeyError, ValueError):
        info(f"[yellow]无法解析用户状态变量 {name}，使用默认值继续。[/yellow]")
        return 0


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


def _has_vip_quota(soup: BeautifulSoup) -> bool:
    vip_div = soup.find("div", id=VIP_ID)

    if isinstance(vip_div, Tag):
        style = vip_div.get("style", "")
        if isinstance(style, list):
            style = " ".join(style)

        style_str = style.lower().replace(" ", "") if style else ""

        if "display:none" not in style_str:
            return True
    return False


def extract_quota(soup: BeautifulSoup) -> tuple[QuotaInfo, Union[QuotaInfo, None]]:
    is_vip = _has_vip_quota(soup)

    raw_text = soup.get_text(separator=" ", strip=True)

    user_quota = QuotaInfo(
        reset_day=_extract_int(PATTERN_USER_RESET, raw_text, default=1),
        total=_extract_float(PATTERN_USER_TOTAL, raw_text, field="USER_TOTAL"),
        used=_extract_float(PATTERN_USER_USED, raw_text, field="USER_USED"),
    )

    vip_quota = None
    if is_vip:
        vip_quota = QuotaInfo(
            reset_day=_extract_int(PATTERN_VIP_RESET, raw_text, default=1),
            total=_extract_float(PATTERN_VIP_TOTAL, raw_text, field="VIP_TOTAL"),
            used=_extract_float(PATTERN_VIP_USED, raw_text, field="VIP_USED"),
        )

    return user_quota, vip_quota


def _extract_int(pattern: str, text: str, default: int = 0) -> int:
    match = re.search(pattern, text)
    if match:
        return int(match.group(1))
    info(f"[yellow]解析整数失败 (pattern={pattern})，如果重复出现请提交 issue[/yellow]")
    return default


def _extract_float(pattern: str, text: str, *, field: str) -> float:
    match = re.search(pattern, text)
    if match:
        try:
            return float(match.group(1))
        except ValueError as e:
            raise HtmlResolveError(f"账号资料页的 {field} 额度数值无效 (pattern={pattern})", code=f"PROFILE_{field}_INVALID") from e
    raise HtmlResolveError(f"账号资料页未找到 {field} 额度字段 (pattern={pattern})", code=f"PROFILE_{field}_MISSING")


def _extract_text_by_selector(soup: BeautifulSoup, selector: str) -> str:
    tag = soup.select_one(selector)
    if not isinstance(tag, Tag):
        info(f"[yellow]解析文本失败 (selector={selector})，如果重复出现请提交 issue[/yellow]")
        return NOT_APPLICABLE

    return tag.text.strip().replace("\xa0", "")


def __resolve_quota_id(is_vip: Optional[int] = None, user_level: Optional[int] = None):
    if is_vip is not None and is_vip >= 1:
        return VIP_ID

    if user_level is not None and user_level <= 1:
        return LV1_ID

    return NOR_ID
