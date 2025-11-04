from bs4 import BeautifulSoup
import re
from typing import Optional

from yarl import URL
from aiohttp import ClientSession as Session

from kmdr.core import BookInfo, VolInfo, VolumeType
from kmdr.core.utils import async_retry
from kmdr.core.console import debug
from kmdr.core.error import KmdrError

@async_retry()
async def extract_book_info_and_volumes(session: Session, url: str, book_info: Optional[BookInfo] = None) -> tuple[BookInfo, list[VolInfo]]:
    """
    从指定的书籍页面 URL 中提取书籍信息和卷信息。

    :param session: 已经建立的 HTTP 会话。
    :param url: 书籍页面的 URL。
    :return: 包含书籍信息和卷信息的元组。
    """
    structured_url = URL(url)

    # 移除移动端路径部分，统一为桌面端路径
    # 因为移动端页面的结构与桌面端不同，可能会影响解析
    route = structured_url.path
    if structured_url.path.startswith('/m/'):
        debug("检测到移动端链接，转换为桌面端链接进行处理。")
        route = structured_url.path[2:]

    async with session.get(route) as response:
        response.raise_for_status()

        # 如果后续有性能问题，可以先考虑使用 lxml 进行解析
        book_page = BeautifulSoup(await response.text(), 'html.parser')

        book_info = __extract_book_info(url, book_page, book_info)
        volumes = await __extract_volumes(session, book_page)

        return book_info, volumes

def __extract_book_info(url: str, book_page: BeautifulSoup, book_info: Optional[BookInfo]) -> BookInfo:
    book_name = book_page.find('font', class_='text_bglight_big').text

    if '為符合要求，此書內容已屏蔽' in book_name:
        raise KmdrError(
            "[yellow]该书籍内容已被屏蔽，请检查代理配置。[/yellow]", 
            solution=["kmdr config -s proxy=<your_proxy>  # 设置可用的代理地址"]
        )

    id = book_page.find('input', attrs={'name': 'bookid'})['value']

    return BookInfo(
        id = id,
        name = book_name,
        url = url,
        author = book_info.author if book_info else '',
        status = book_info.status if book_info else '',
        last_update = book_info.last_update if book_info else ''
    )
    

async def __extract_volumes(session: Session, book_page: BeautifulSoup) -> list[VolInfo]:
    script = book_page.find_all('script', language="javascript")[-1].text

    pattern = re.compile(r'/book_data.php\?h=\w+')
    book_data_url = pattern.search(script).group(0)
    
    async with session.get(url = book_data_url) as response:
        response.raise_for_status()

        book_data = (await response.text()).split('\n')
        book_data = filter(lambda x: 'volinfo' in x, book_data)
        book_data = map(lambda x: x.split("\"")[1], book_data)
        book_data = map(lambda x: x[8:].split(','), book_data)
        
        volume_data = list(map(lambda x: VolInfo(
                id = x[0],
                extra_info = __extract_extra_info(x[1]),
                is_last = x[2] == '1',
                vol_type = __extract_volume_type(x[3]),
                index = int(x[4]),
                pages = int(x[6]),
                name = x[5],
                size = float(x[11])), book_data))
        volume_data: list[VolInfo] = volume_data

        return volume_data

def __extract_extra_info(value: str) -> str:
    if value == '0':
        return '无'
    elif value == '1':
        return '最近一週更新'
    elif value == '2':
        return '90天內曾下載/推送'
    else:
        return f'未知({value})'
    
def __extract_volume_type(value: str) -> VolumeType:
    if value == '單行本':
        return VolumeType.VOLUME
    elif value == '番外篇':
        return VolumeType.EXTRA
    elif value == '話':
        return VolumeType.SERIALIZED
    else:
        raise ValueError(f'未知的卷类型: {value}')