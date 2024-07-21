"""
author: @chrisis58
description: A simple script to download manga from kox.moe
usage: python kox_sync.py login -u your_username -p your_password
usage: python kox_sync.py download -d /path/to/download/destination --book-id 123 --volume 1,2,3
"""


import os
import threading
import concurrent.futures
from typing import Callable

import argparse
from dataclasses import dataclass
import json
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import re


## ---- Constants ---- ##
HOME_URL = 'https://kox.moe/'
LOGIN_URL = 'https://kox.moe/login.php'
PROFILE_URL = 'https://kox.moe/my.php'
MY_FOLLOW_URL = 'https://kox.moe/myfollow.php'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
## ------------------- ##


#### ---- argparse init ---- ####
argparser = argparse.ArgumentParser(description='Kox Sync')
subparsers = argparser.add_subparsers(title='subcommands', dest='command')

download_parser = subparsers.add_parser('download', help='Download books')
download_parser.add_argument('-d', '--dest', type=str, help='Download destination', required=True)
download_parser.add_argument('--book-id', type=int, help='Book id', required=False)
download_parser.add_argument('--book-name', type=str, help='Book name (searching only in followed)', required=False)
download_parser.add_argument('-v','--volume', type=str, help='Volume(s), split using commas, `all` for all', required=False)
download_parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files', required=False)
download_parser.add_argument('-p', '--proxy', type=str, help='Proxy server', required=False)
download_parser.add_argument('-r', '--retry', type=int, help='Retry times', required=False)

login_parser = subparsers.add_parser('login', help='Login to kox.moe')
login_parser.add_argument('-u', '--username', type=str, help='Your username', required=True)
login_parser.add_argument('-p', '--password', type=str, help='Your password', required=True)
#### ---- argparse parse ---- ####


@dataclass
class Book:
    name: str = None
    book_id: int = None
    url: str = None
    author: str = None
    status: str = None
    last_update: str = None
    
@dataclass
class Volume:
    url: str = None
    name: str = None
    size: str = None
    book: Book = None
    

def get_cookie(
    username: str,
    password: str,
) -> dict:
    session = requests.Session()
    session.headers.update(HEADERS)
    
    response = session.get(url = HOME_URL)
    response.raise_for_status()
    
    response = session.post(
        url = 'https://kox.moe/login_do.php', 
        data = {
            'email': username,
            'passwd': password,
            'keepalive': 'on'
        },
    )
    response.raise_for_status()
    
    code = re.search('"\w+"', response.text).group(0).split('"')[1]
    if code != 'm100':
        if code == 'e400':
            print("帳號或密碼錯誤。")
        elif code == 'e401':
            print("非法訪問，請使用瀏覽器正常打開本站")
        elif code == 'e402':
            print("帳號已經註銷。不會解釋原因，無需提問。")
        elif code == 'e403':
            print("驗證失效，請刷新頁面重新操作。")
        exit(1)
    
    response = session.get(url = PROFILE_URL)
    response.raise_for_status()
    
    # 保存 cookie
    with open(os.path.join(os.path.expanduser("~"), 'kox-cookie.json'), 'w') as f:
        json.dump(session.cookies.get_dict(), f)
    
    return session.cookies.get_dict()


def login(
    cookies: dict,
    proxy: dict = None
) -> requests.Session:
    session = requests.Session()
    
    session.headers.update(HEADERS)
    session.cookies.update(cookies)
    if proxy:
        session.proxies.update(proxy)
        
    response = session.get(url = PROFILE_URL)
    response.raise_for_status()
    
    threading.Thread(target=lambda: print(f"=========================\n\nlogged in as {BeautifulSoup(response.text, 'html.parser').find('div', id='div_nickname_display').text.strip().split(' ')[0]}\n\n=========================\n")).start()
    # profile = BeautifulSoup(response.text, 'html.parser')
    # profile = profile.find('div', id='div_nickname_display')
    # print(f"=========================\n\nLogged in as {profile.text.strip().split(' ')[0]}\n\n=========================\n")
    
    return session

    
def download(
    session: requests.Session,
    volume: Volume,
    resume_from: int = 0,
    callback: Callable[[Volume], None] = None
) -> str:
    """
    下载指定卷
    
    :param session: 用于下载的会话
    :param volume: 等待下载的卷
    :param callback: 下载完成后的回调函数
    :return: error
    """
    sub_dir = f'{volume.book.name}'
    filename = f'[Kox][{volume.book.name}]{volume.name}.epub'
    filename_downloading = f'{filename}.downloading'
    
    if os.path.exists(f'{argparser.parse_args().dest}/{sub_dir}') == False:
        os.makedirs(f'{argparser.parse_args().dest}/{sub_dir}')
        
    if argparser.parse_args().overwrite == False and os.path.exists(f'{argparser.parse_args().dest}/{sub_dir}/{filename}'):
        print(f"{filename} already exists")
        return None
    
    with session.get(url = volume.url, stream=True) as r:
        r.raise_for_status()
        
        total_size_in_bytes = int(r.headers.get('Content-Length', 0))
        block_size = 8192
        
        with open(f'{argparser.parse_args().dest}/{sub_dir}/{filename_downloading}', 'wb') as f:
            with tqdm(total=total_size_in_bytes, unit='B', unit_scale=True, desc=f'{filename}') as progress_bar:
                for chunk in r.iter_content(chunk_size=block_size):
                    f.write(chunk)
                    progress_bar.update(len(chunk))
        
        # 下载完成后，重命名文件
        os.rename(f'{argparser.parse_args().dest}/{sub_dir}/{filename_downloading}', f'{argparser.parse_args().dest}/{sub_dir}/{filename}')
        
        # 下载完成后，执行回调函数
        if callback:
            callback(volume)
            
        return None
    
def main():
    argparser.parse_args()
    
    if argparser.parse_args().command is None:
        argparser.print_help()
        exit(1)
        
    if argparser.parse_args().command == 'login':
        username = argparser.parse_args().username
        password = argparser.parse_args().password
        
        cookies = get_cookie(username, password)
        print("Login success")
        exit(0)
    
    with open(os.path.join(os.path.expanduser("~"), 'kox-cookie.json'), 'r') as f:
        cookies = json.load(f)
        
    if argparser.parse_args().proxy:
        session = login(cookies, proxy = {'http': argparser.parse_args().proxy, 'https': argparser.parse_args().proxy})
    else:
        session = login(cookies)
       
    ## 选择要下载的书籍 
    book = None
    if argparser.parse_args().book_id:
        # 如果指定了book_id，直接下载
        book = Book(book_id = argparser.parse_args().book_id, url=f'https://kox.moe/c/{argparser.parse_args().book_id}.htm')
    else:
        # 查询用户的关注页，获取订阅的书籍
        followed_rows = BeautifulSoup(session.get(url = MY_FOLLOW_URL).text, 'html.parser').find_all('tr', style='height:36px;')
        mapped = map(lambda x: x.find_all('td'), followed_rows)
        filterd = filter(lambda x: '書名' not in x[1].text, mapped)
        books = map(lambda x: Book(name = x[1].text, url = x[1].find('a')['href'], author = x[2].text, status = x[-1].text, last_update = x[-2].text, book_id = int(re.search(r'\d+', x[1].find('a')['href']).group(0))), filterd)
        books = list(books)
        
        if argparser.parse_args().book_name:
            # 如果指定了book_name，只下载指定的书籍
            books = filter(lambda x: argparser.parse_args().book_name in x.name, books)
            books = list(books)
            if len(books) == 1:
                book = books[0]
            else:
                raise Exception("Too many books found")
        else:
            # 如果没有指定book_id，也没有指定book_name，列出所有订阅的书籍
            print("\t最后更新时间\t书名")
            for v in range(len(books)):
                print(f"[{v}]\t{books[v].last_update}\t{books[v].name}")
            
            choosed = input("choose a book to download: ")
            while not choosed.isdigit() or int(choosed) >= len(books) or int(choosed) < 0:
                choosed = input("choose a book to download: ")
            choosed = int(choosed)
            book = books[choosed]
            
    book_page: BeautifulSoup = BeautifulSoup(session.get(book.url).text, 'html.parser')
    script = book_page.find_all('script', language="javascript")[-1].text
    book.name = book_page.find('font', class_='text_bglight_big').text
    pattern = re.compile(r'/book_data.php\?h=\w+')
    book_data_url = pattern.search(script).group(0)
    
    book_data = session.get(url = f"https://kox.moe{book_data_url}").text.split('\n')
    book_data = filter(lambda x: 'volinfo' in x, book_data)
    book_data = map(lambda x: x.split("\"")[1], book_data)
    book_data = filter(lambda x: '單行本' in x, book_data)
    book_data = map(lambda x: x[8:].split(','), book_data)
    
    volume_data = map(lambda x: Volume(url = f'https://kox.moe/dl/{book.book_id}/{x[0]}/0/2/0/', name = x[5], size = x[9], book=book), book_data)
    volume_data: list[Volume] = list(volume_data)
    
    
    ## 选择要下载的卷
    volumes = []
    if argparser.parse_args().volume:
        # 如果指定了volume，只下载指定的卷
        if argparser.parse_args().volume == 'all':
            volumes = volume_data
        else:
            volumes = argparser.parse_args().volume.split(',')
            volume_data = filter(lambda x: sum([v in x.name for v in volumes]) > 0, volume_data)
            volumes = list(volume_data)
    else:
        # 如果没有指定volume，列出所有卷由用户选择
        print(f"漫画: {book.name}")
        print("\t卷名\t大小(MB)")
        for v in range(len(volume_data)):
            print(f"[{v}]\t{volume_data[v].name}\t{volume_data[v].size}")
    
        choosed = input("choose a volume to download (index or all): ")
        while choosed != 'all' and int(choosed) >= len(volume_data):
            choosed = input("choose a volume to download (index or all): ")
        
        if choosed == 'all':
            volumes = volume_data
        else:
            if choosed.isdigit() == False:
                raise Exception("Invalid input")
            else:
                choosed = int(choosed)
                volumes.append(volume_data[choosed])
         
    ## 开始下载
    if len(volumes) == 0:
        print("No volume selected")
        exit(1)

    ## 定义下载完成后的回调函数
    callback: Callable[[Volume], None] = lambda v: print(f"callback: wow! {v.name} downloaded!")   

    # 尝试次数，默认为 1
    max_retry = argparser.parse_args().retry if argparser.parse_args().retry else 1
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(volumes))) as executor:
        features = {executor.submit(download, session, volume, callback): volume for volume in volumes}
        
        for feature in concurrent.futures.as_completed(features):
            volume = features[feature]
            retry_count = 0
            while retry_count < max_retry:
                try:
                    error = feature.result()
                    if error:
                        print(f"An error occurred while downloading {volume.name}: {error}")
                        retry_count += 1
                        print(f"Retrying download of {volume.name} (Retry {retry_count})")
                        feature = executor.submit(download, session, volume, callback)
                    else:
                        break
                except KeyboardInterrupt:
                    print("Download interrupted")
                    exit(1)
                except Exception as e:
                    print(f"An error occurred: {e}")
                    retry_count += 1
                    print(f"Retrying download of {volume.name} (Retry {retry_count})")
                    feature = executor.submit(download, session, volume, callback)
            
            if retry_count == max_retry:
                print(f"Failed to download {volume.name} after {max_retry} retries")

    
if __name__ == '__main__':
    main()
    