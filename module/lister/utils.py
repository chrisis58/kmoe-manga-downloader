from requests import Session
from bs4 import BeautifulSoup
import re

from core import BookInfo, VolInfo, VolumeType

def extract_book_info_and_volumes(session: Session, url: str) -> tuple[BookInfo, list[VolInfo]]:
    """
    从指定的书籍页面 URL 中提取书籍信息和卷信息。

    :param session: 已经建立的 requests.Session 实例。
    :param url: 书籍页面的 URL。
    :return: 包含书籍信息和卷信息的元组。
    """
    book_page = BeautifulSoup(session.get(url).text, 'html.parser')

    book_info = __extract_book_info(url, book_page)
    volumes = __extract_volumes(session, book_page)

    return book_info, volumes

def __extract_book_info(url: str, book_page: BeautifulSoup) -> BookInfo:
    book_name = book_page.find('font', class_='text_bglight_big').text

    id = book_page.find('input', attrs={'name': 'bookid'})['value']

    return BookInfo(
        id = id,
        name = book_name,
        url = url,
        author = '',
        status = '',
        last_update = ''
    )
    

def __extract_volumes(session: Session, book_page: BeautifulSoup) -> list[VolInfo]:
    script = book_page.find_all('script', language="javascript")[-1].text

    pattern = re.compile(r'/book_data.php\?h=\w+')
    book_data_url = pattern.search(script).group(0)
    
    book_data = session.get(url = f"https://kox.moe{book_data_url}").text.split('\n')
    book_data = filter(lambda x: 'volinfo' in x, book_data)
    book_data = map(lambda x: x.split("\"")[1], book_data)

    # TODO: 这里的过滤条件可能需要根据实际情况调整
    #       目前只保留包含「單行本」的卷信息
    book_data = filter(lambda x: '單行本' in x, book_data)

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