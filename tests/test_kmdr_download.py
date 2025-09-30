import os

import time
import unittest
from argparse import Namespace

from kmdr.main import main_sync as kmdr_main
from kmdr.core.constants import BASE_URL

BASE_DIR = os.environ.get('KMDR_TEST_DIR', './tests')
KMOE_USERNAME = os.environ.get('KMOE_USERNAME')
KMOE_PASSWORD = os.environ.get('KMOE_PASSWORD')

@unittest.skipUnless(KMOE_USERNAME and KMOE_PASSWORD, "KMOE_USERNAME and KMOE_PASSWORD must be set in environment variables")
class TestKmdrDownload(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        kmdr_main(
            Namespace(
                command='login',
                username=KMOE_USERNAME,
                password=KMOE_PASSWORD,
                show_quota=False
            )
        )

        if not os.path.exists(BASE_DIR):
            os.makedirs(BASE_DIR, exist_ok=True)

    @classmethod
    def tearDownClass(cls):

        from shutil import rmtree
        test_methods = [method for method in dir(cls) if method.startswith('test_')]

        for method in test_methods:
            dir_path = f"{BASE_DIR}/{method}"
            
            if os.path.exists(dir_path):
                rmtree(dir_path)

    def tearDown(self):
        # avoiding rate limit
        print("Waiting", end='')
        for i in range(3):
            print('.', end='', flush=True)
            time.sleep(1)
        print()

    def test_download_multiple_volumes(self):
        dest = f'{BASE_DIR}/{self.test_download_multiple_volumes.__name__}'

        kmdr_main(
            Namespace(
                command='download',
                dest=dest,
                book_url=f'{BASE_URL.DEFAULT}/c/51044.htm',
                vol_type='extra',
                volume='all',
                max_size=0.6,
                limit=3,
                retry=3,
            )
        )

        assert len(sub_dir := os.listdir(dest)) == 1, "Expected one subdirectory in the destination"
        assert os.path.isdir(os.path.join(dest, book_dir := sub_dir[0])), "Expected the subdirectory to be a directory"
        assert len(os.listdir(os.path.join(dest, book_dir))) == 3, "Expected 3 volumes to be downloaded"

        total_size = sum(
            os.path.getsize(os.path.join(dest, book_dir, f)) for f in os.listdir(os.path.join(dest, book_dir)) if os.path.isfile(os.path.join(dest, book_dir, f))
        )
        assert total_size < 3 * 0.6 * 1024 * 1024, "Total size of downloaded files exceeds 0.6 MB"
    
    def test_download_multiple_volumes_mirror(self):
        dest = f'{BASE_DIR}/{self.test_download_multiple_volumes_mirror.__name__}'

        kmdr_main(
            Namespace(
                command='download',
                dest=dest,
                ##################### WARNING #####################
                # 这个 URL 可能会在未来失效，因为 MOX 站点不保证长期可用
                # 这里使用 MOX 站点是为了测试多源下载功能
                # 如果确认是镜像站失效，请替换为其他可用的镜像站
                book_url=f'{BASE_URL.MOX}/c/51044.htm',
                vol_type='extra',
                volume='all',
                max_size=0.6,
                limit=1,
                retry=3,
            )
        )

        assert len(sub_dir := os.listdir(dest)) == 1, "Expected one subdirectory in the destination"
        assert os.path.isdir(os.path.join(dest, book_dir := sub_dir[0])), "Expected the subdirectory to be a directory"
        assert len(os.listdir(os.path.join(dest, book_dir))) == 1, "Expected 1 volume to be downloaded"

        total_size = sum(
            os.path.getsize(os.path.join(dest, book_dir, f)) for f in os.listdir(os.path.join(dest, book_dir)) if os.path.isfile(os.path.join(dest, book_dir, f))
        )
        assert total_size < 1 * 0.6 * 1024 * 1024, "Total size of downloaded files exceeds 0.6 MB"
    
    def test_download_single_volumes_mobile(self):
        dest = f'{BASE_DIR}/{self.test_download_single_volumes_mobile.__name__}'

        kmdr_main(
            Namespace(
                command='download',
                dest=dest,
                book_url=f'{BASE_URL.DEFAULT}/m/c/51044.htm',
                vol_type='extra',
                volume='all',
                max_size=0.6,
                limit=1,
                retry=3,
            )
        )

        assert len(sub_dir := os.listdir(dest)) == 1, "Expected one subdirectory in the destination"
        assert os.path.isdir(os.path.join(dest, book_dir := sub_dir[0])), "Expected the subdirectory to be a directory"
        assert len(os.listdir(os.path.join(dest, book_dir))) == 1, "Expected 1 volume to be downloaded"

        total_size = sum(
            os.path.getsize(os.path.join(dest, book_dir, f)) for f in os.listdir(os.path.join(dest, book_dir)) if os.path.isfile(os.path.join(dest, book_dir, f))
        )
        assert total_size < 1 * 0.6 * 1024 * 1024, "Total size of downloaded files exceeds 0.6 MB"

    def test_download_multiple_volumes_with_multiple_workers(self):
        dest = f'{BASE_DIR}/{self.test_download_multiple_volumes_with_multiple_workers.__name__}'

        kmdr_main(
            Namespace(
                command='download',
                dest=dest,
                book_url=f'{BASE_URL.DEFAULT}/c/51044.htm',
                vol_type='extra',
                volume='all',
                max_size=0.6,
                limit=3,
                retry=3,
                num_workers=3
            )
        )

        assert len(sub_dir := os.listdir(dest)) == 1, "Expected one subdirectory in the destination"
        assert os.path.isdir(os.path.join(dest, book_dir := sub_dir[0])), "Expected the subdirectory to be a directory"
        assert len(os.listdir(os.path.join(dest, book_dir))) == 3, "Expected 3 volumes to be downloaded"

        total_size = sum(
            os.path.getsize(os.path.join(dest, book_dir, f)) for f in os.listdir(os.path.join(dest, book_dir)) if os.path.isfile(os.path.join(dest, book_dir, f))
        )
        assert total_size < 3 * 0.6 * 1024 * 1024, "Total size of downloaded files exceeds 0.6 MB"

    def test_download_volume_with_callback(self):
        dest = f'{BASE_DIR}/{self.test_download_volume_with_callback.__name__}'

        kmdr_main(
            Namespace(
                command='download',
                dest=dest,
                book_url=f'{BASE_URL.DEFAULT}/c/51044.htm',
                vol_type='extra',
                volume='all',
                max_size=0.4,
                limit=1,
                retry=3,
                callback="echo 'CALLBACK: {b.name} {v.name} has been downloaded!'" + f" > {dest}/callback.log"
            )
        )

        assert len(files := os.listdir(dest)) == 2, "Expected one subdirectory and one callback log file in the destination"
        assert 'callback.log' in files, "Expected callback log file to be present"
        with open(os.path.join(dest, 'callback.log'), 'r') as f:
            log_content = f.read()
            assert "CALLBACK:" in log_content, "Expected callback log to contain the correct message"
        files.remove('callback.log')
        assert os.path.isdir(os.path.join(dest, book_dir := files[0])), "Expected the subdirectory to be a directory"
        assert len(os.listdir(os.path.join(dest, book_dir))) == 1, "Expected 1 volume to be downloaded"

    def test_download_volume_with_direct_downloader(self):
        dest = f'{BASE_DIR}/{self.test_download_volume_with_direct_downloader.__name__}'

        kmdr_main(
            Namespace(
                command='download',
                dest=dest,
                book_url=f'{BASE_URL.DEFAULT}/c/51043.htm',
                vol_type='extra',
                volume='all',
                max_size=0.4,
                method=1, # use direct download method
                limit=1,
                retry=3,
                num_workers=1
            )
        )

        assert len(sub_dir := os.listdir(dest)) == 1, "Expected one subdirectory in the destination"
        assert os.path.isdir(os.path.join(dest, book_dir := sub_dir[0])), "Expected the subdirectory to be a directory"
        assert len(os.listdir(os.path.join(dest, book_dir))) == 1, "Expected 1 volume to be downloaded"