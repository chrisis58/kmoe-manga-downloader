import os
from typing import Optional, Callable

from requests import Session
from tqdm import tqdm

import threading
import requests
from requests import Session

_session_instance: Optional[Session] = None

_session_lock = threading.Lock()\

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_singleton_session() -> Session:
    global _session_instance

    if _session_instance is None:
        with _session_lock:
            if _session_instance is None:
                _session_instance = requests.Session()
                _session_instance.headers.update(HEADERS)

    return _session_instance

def download_file(
            session: Session, 
            url: str,
            dest_path: str, 
            filename: str, 
            retry_times: int = 0, 
            headers: dict = dict(), 
            callback: Optional[Callable] = None,
    ):
    filename_downloading = f'{filename}.downloading'
        
    file_path = f'{dest_path}/{filename}'
    tmp_file_path = f'{dest_path}/{filename_downloading}'
    
    if not os.path.exists(dest_path):
        os.makedirs(dest_path, exist_ok=True)
        
    if os.path.exists(file_path):
        print(f"\n{filename} already exists")
        return

    resume_from = 0
    total_size_in_bytes = 0
    
    if os.path.exists(tmp_file_path):
        resume_from = os.path.getsize(tmp_file_path)
    
    if resume_from:
        headers['Range'] = f'bytes={resume_from}-'
        
    try:
        with session.get(url = url, stream=True, headers=headers) as r:
            r.raise_for_status()
            
            total_size_in_bytes = int(r.headers.get('content-length', 0)) + resume_from
            block_size = 8192
            
            with open(tmp_file_path, 'ab') as f:
                with tqdm(total=total_size_in_bytes, unit='B', unit_scale=True, desc=f'{filename}', initial=resume_from) as progress_bar:
                    for chunk in r.iter_content(chunk_size=block_size):
                        if chunk:
                            f.write(chunk)
                            progress_bar.update(len(chunk))
            
            if (os.path.getsize(tmp_file_path) == total_size_in_bytes):
                os.rename(tmp_file_path, file_path)
                
                if callback:
                    callback()
    except Exception as e:
        print(f"\n{type(e).__name__}: {e} occurred while downloading {filename}")
        if retry_times > 0:
            # 重试下载
            print(f"Retry download {filename}...")
            download_file(session, url, dest_path, filename, retry_times - 1, headers, callback)
        else:
            print(f"\nMeet max retry times, download failed")
            raise e
