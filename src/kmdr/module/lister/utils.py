import re
from collections.abc import Awaitable
from typing import Callable, Optional

from aiohttp import ClientSession as Session
from bs4 import BeautifulSoup
from yarl import URL

from kmdr.core import BookInfo, Credential, VolInfo, VolumeType
from kmdr.core.console import debug
from kmdr.core.error import ContentBlockedError
from kmdr.core.utils import async_retry, extract_cookies


@async_retry()
async def extract_book_info_and_volumes(
    session: Session,
    url: str,
    book_info: Optional[BookInfo] = None,
    awaitable_cred: Optional[Callable[[], Awaitable[Optional[Credential]]]] = None,
    cookies: Optional[dict[str, str]] = None,
) -> tuple[BookInfo, list[VolInfo]]:
    """
    从指定的书籍页面 URL 中提取书籍信息和卷信息。

    :param session: 已经建立的 HTTP 会话。
    :param url: 书籍页面的 URL。
    :param book_info: 可选的书籍信息，用于补充作者、状态等字段。
    :param awaitable_cred: 当遇到需要登录才能访问的内容时，可以调用此回调获取凭证并重试。
    :return: 包含书籍信息和卷信息的元组。
    """
    structured_url = URL(url)

    # 移除移动端路径部分，统一为桌面端路径
    # 因为移动端页面的结构与桌面端不同，可能会影响解析
    route = structured_url.path
    if structured_url.path.startswith("/m/"):
        debug("检测到移动端链接，转换为桌面端链接进行处理。")
        route = structured_url.path[2:]

    return await __do_extract(session, route, url, book_info, awaitable_cred, cookies)


async def __do_extract(
    session: Session,
    route: str,
    url: str,
    book_info: Optional[BookInfo],
    awaitable_cred: Optional[Callable[[], Awaitable[Optional[Credential]]]] = None,
    cookies: Optional[dict[str, str]] = None,
) -> tuple[BookInfo, list[VolInfo]]:
    """实际执行提取操作的内部函数，支持在遇到需要登录的内容时重试。"""
    async with session.get(route, cookies=cookies) as response:
        response.raise_for_status()

        # 如果后续有性能问题，可以先考虑使用 lxml 进行解析
        book_page = BeautifulSoup(await response.text(), "html.parser")

        # 如果携带凭证访问主页，服务器不会设置新的 cookies，所以需要复用旧的
        resp_cookies = extract_cookies(response) if cookies is None else cookies

        try:
            extracted_book_info = __extract_book_info(url, book_page, book_info)
        except ContentBlockedError:
            if awaitable_cred is not None:
                debug("检测到内容被屏蔽，尝试等待凭证获取后重试")
                cred = await awaitable_cred()
                if cred is not None:
                    debug("已获取凭证，正在重试获取书籍信息")
                    # 使用新凭证的 cookies 重试请求
                    return await __do_extract(session, route, url, book_info, None, cred.cookies)
            elif cookies is not None:
                debug("使用凭证也无法访问内容")
            raise

        volumes = await __extract_volumes(session, book_page, resp_cookies)

        return extracted_book_info, volumes


# 书籍详情页中的标签图标 id → 显示名称 映射
_TAG_ID_MAP = {
    "logo_r15": "R15",
    "logo_r18": "R18",
    "logo_jpn": "日文",
    "logo_eng": "英文",
    "logo_hd": "HD",
    "logo_color2": "全彩",
    "logo_color": "彩色",
    "logo_rtl": "點左翻頁",
}


def __extract_tags(book_page: BeautifulSoup) -> tuple[str, ...]:
    """从书籍详情页 HTML 中提取活跃的标签列表。"""
    tags: list[str] = []

    # 图片类标签：.author 下的直接 img 子元素
    for img in book_page.select(".author > img"):
        style = str(img.get("style") or "")
        if "display:none" not in style:
            tag_id = str(img.get("id") or "")
            tag = _TAG_ID_MAP.get(tag_id)
            if tag:
                tags.append(tag)

    return tuple(tags)


def __extract_book_info(url: str, book_page: BeautifulSoup, book_info: Optional[BookInfo]) -> BookInfo:
    book_name = book_page.find("font", class_="text_bglight_big").text

    if "為符合要求，此書內容已屏蔽" in book_name:
        raise ContentBlockedError(
            "[yellow]该书籍内容已被屏蔽，请检查代理配置。[/yellow]",
            solution=["kmdr config -s proxy=<your_proxy>  # 设置可用的代理地址"],
        )

    id = book_page.find("input", attrs={"name": "bookid"})["value"]

    return BookInfo(
        id=id,
        name=book_name,
        url=url,
        author=book_info.author if book_info else "",
        status=book_info.status if book_info else "",
        last_update=book_info.last_update if book_info else "",
        tags=__extract_tags(book_page),
    )


async def __extract_volumes(session: Session, book_page: BeautifulSoup, cookies: dict[str, str]) -> list[VolInfo]:
    pattern = re.compile(r'data_book\(\s*"(\w+)"\s*\)')
    match = None
    for script in book_page.find_all("script"):
        match = pattern.search(script.text)
        if match:
            break
    if not match:
        return []
    book_hash = match.group(1)

    async with session.get(url=f"/data_book.php?h={book_hash}", cookies=cookies) as response:
        response.raise_for_status()

        result = await response.json(content_type=None)
        voldata = result.get("voldata", [])

        volume_data = [
            VolInfo(
                id=x[0],
                extra_info=__extract_extra_info(x[1]),
                is_last=x[2] == "1",
                vol_type=__extract_volume_type(x[3]),
                index=int(x[4]),
                pages=int(x[6]),
                name=x[5],
                size=float(x[11]),
            )
            for x in voldata
        ]

        return volume_data


def __extract_extra_info(value: str) -> str:
    if value == "0":
        return "无"
    elif value == "1":
        return "最近一週更新"
    elif value == "2":
        return "90天內曾下載/推送"
    else:
        return f"未知({value})"


def __extract_volume_type(value: str) -> VolumeType:
    if value == "單行本":
        return VolumeType.VOLUME
    elif value == "番外篇":
        return VolumeType.EXTRA
    elif value == "話":
        return VolumeType.SERIALIZED
    else:
        raise ValueError(f"未知的卷类型: {value}")
