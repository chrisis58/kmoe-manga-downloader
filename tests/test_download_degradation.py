"""验证辅助流程失败时下载继续，核心数据损坏时仍明确报错。"""

import asyncio
from argparse import Namespace
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from kmdr.core.error import HtmlResolveError, LoginError, QuotaExceededError, RangeNotSupportedError
from kmdr.core.pool import CredentialPool, PooledCredential
from kmdr.core.structure import BookInfo, Credential, CredentialStatus, QuotaInfo, VolInfo, VolumeType
from kmdr.module.authenticator import utils as auth_utils
from kmdr.module.authenticator.CookieAuthenticator import CookieAuthenticator
from kmdr.module.downloader import download_utils
from kmdr.module.downloader.FailoverDownloader import FailoverDownloader
from kmdr.module.lister import utils as lister_utils
from kmdr.module.lister.FollowedBookLister import FollowedBookLister
from kmdr.module.pool.PoolLister import PoolLister

PROFILE = """
<script>var unrelated = 1;</script>
<script>
var is_vip = 0;
var user_level = 2;
</script>
<table><tr id="div_nickname_display"><td>昵称</td><td>测试用户</td></tr></table>
<div id="div_user_nor">Lv2 額度 : 每月 1 日 Lv2 每月額度 : 100 M 本月已用免費額度 : 10 M</div>
"""
BOOK_PAGE = '<font class="text_bglight_big">测试书籍</font><input name="bookid" value="1"><script>Kmoe.book("hash")</script>'
VOLUME_ROW = ["vol-id", "0", "0", "單行本", "1", "第一卷", "20", "", "", "", "", "10"]
BOOK = BookInfo("1", "测试书籍", "/c/1.htm", "", "", "")
VOLUME = VolInfo("vol-id", "无", False, VolumeType.VOLUME, 1, "第一卷", 20, 10.0)


def credential(username="user", total=100.0, known=True):
    return Credential(username, {"token": "test"}, QuotaInfo(1, total, 0.0, update_at=0), 2, quota_known=known)


def http_session(html="", data=None):
    response = MagicMock()
    response.history = []
    response.cookies = {}
    response.text = AsyncMock(return_value=html)
    response.json = AsyncMock(return_value=data)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    session = MagicMock()
    session.get.return_value = context
    return session, response


def test_status_reads_all_scripts():
    session, _ = http_session(PROFILE)
    cred = asyncio.run(auth_utils.check_status(session, MagicMock(), "user", {}))
    assert cred.level == 2
    assert cred.quota_known
    assert cred.quota_remaining == 90


@pytest.mark.parametrize("html", ["<html>不完整页面</html>", PROFILE.replace("user_level = 2", "user_level = unknown")])
def test_optional_profile_fields_do_not_abort(html):
    session, _ = http_session(html)
    cred = asyncio.run(auth_utils.check_status(session, MagicMock(), "user", {"token": "test"}))
    assert cred.cookies == {"token": "test"}
    assert cred.status == CredentialStatus.ACTIVE
    if "不完整" in html:
        assert not cred.quota_known
        assert cred.quota_remaining == 0


def test_login_redirect_still_fails():
    session, response = http_session()
    response.history = [SimpleNamespace(status=302)]
    response.url = "https://example.com/login.php"
    with pytest.raises(LoginError):
        asyncio.run(auth_utils.check_status(session, MagicMock(), "user", {}))


@pytest.mark.parametrize("command", ["download", "status"])
@pytest.mark.parametrize("error", [aiohttp.ClientConnectionError("断线"), asyncio.TimeoutError(), LoginError("登录失效")])
def test_cookie_fallback_only_for_download_and_recoverable_errors(monkeypatch, command, error):
    authenticator = CookieAuthenticator(command=command)
    authenticator._configurer = SimpleNamespace(cookie={"token": "test"}, config=SimpleNamespace(username="user", cred_pool=[]))
    authenticator._session = MagicMock()
    monkeypatch.setattr(auth_utils, "check_status", AsyncMock(side_effect=error))
    if command == "status" or isinstance(error, LoginError):
        with pytest.raises(type(error)):
            asyncio.run(authenticator._authenticate())
    else:
        cred = asyncio.run(authenticator._authenticate())
        assert cred.cookies == {"token": "test"}
        assert not cred.quota_known


def test_credential_save_failure_does_not_abort_authentication(monkeypatch):
    authenticator = CookieAuthenticator(command="download")
    authenticator._configurer = MagicMock()
    authenticator._configurer.save_credential.side_effect = OSError("只读目录")
    cred = credential()
    monkeypatch.setattr(authenticator, "_authenticate", AsyncMock(return_value=cred, __name__="_authenticate"))
    assert asyncio.run(authenticator.authenticate()) is cred


def test_unknown_quota_survives_config_roundtrip_and_reservation():
    cred = Credential.from_dict(asdict(credential(total=0, known=False)))
    assert not cred.quota_known
    pooled = PooledCredential(cred)
    with pooled.quota_transaction(10) as finalize:
        assert finalize is not None
        finalize(True)
    assert pooled.reserved == 0
    assert cred.user_quota.unsynced_usage == 10


def test_old_config_defaults_to_known_quota():
    data = asdict(credential())
    del data["quota_known"]
    assert Credential.from_dict(data).quota_known


def test_pool_refresh_updates_quota_certainty_and_vip_membership():
    pooled = PooledCredential(credential(total=0, known=False))
    vip = credential()
    vip.vip_quota = QuotaInfo(1, 500.0, 0.0)
    pooled.update_cred(vip, force=True)
    assert pooled.inner.quota_known
    assert pooled.inner.is_vip
    pooled.update_cred(credential(), force=True)
    assert not pooled.inner.is_vip


@pytest.mark.parametrize(
    "error", [HtmlResolveError("页面变化", code="TEST_PARSE_FAILURE"), aiohttp.ClientConnectionError("断线"), LoginError("失效")]
)
def test_pool_refresh_only_invalidates_login_errors(monkeypatch, error):
    lister = PoolLister()
    cred = credential()
    monkeypatch.setattr(auth_utils, "check_status", AsyncMock(side_effect=error))
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    asyncio.run(lister._check_and_update_single(MagicMock(), cred, MagicMock()))
    assert cred.status == (CredentialStatus.INVALID if isinstance(error, LoginError) else CredentialStatus.ACTIVE)
    assert cred.user_quota.total == 100


def failover_for(monkeypatch, credentials):
    configurer = MagicMock()
    configurer.config.cred_pool = credentials
    pool = CredentialPool(configurer)
    with patch("asyncio.Semaphore", return_value=MagicMock()):
        downloader = FailoverDownloader(method=2)
    downloader._configurer = configurer
    downloader._session = MagicMock()
    monkeypatch.setattr("kmdr.core.context._lazy_cred_pool", pool)
    downloader._delegate = SimpleNamespace(_download=AsyncMock())
    return downloader, pool


def test_refresh_failure_does_not_block_next_pool_candidate(monkeypatch):
    first, second = credential("first", total=0), credential("second")
    downloader, _ = failover_for(monkeypatch, [first, second])
    monkeypatch.setattr(auth_utils, "check_status", AsyncMock(side_effect=HtmlResolveError("页面变化", code="TEST_PARSE_FAILURE")))
    asyncio.run(downloader._download(first, BOOK, VOLUME))
    assert downloader._delegate._download.await_args.args[0] is second
    assert first.status == CredentialStatus.ACTIVE


def test_server_quota_error_still_switches_accounts_when_refresh_fails(monkeypatch):
    first, second = credential("first", total=0, known=False), credential("second")
    downloader, _ = failover_for(monkeypatch, [first, second])
    downloader._delegate._download.side_effect = [QuotaExceededError("额度不足"), None]
    monkeypatch.setattr(auth_utils, "check_status", AsyncMock(side_effect=HtmlResolveError("页面变化", code="TEST_PARSE_FAILURE")))
    asyncio.run(downloader._download(first, BOOK, VOLUME))
    assert downloader._delegate._download.await_count == 2
    assert first.status == CredentialStatus.QUOTA_EXCEEDED


def test_unknown_quota_and_pool_save_failure_do_not_block_download(monkeypatch):
    cred = credential(total=0, known=False)
    downloader, _ = failover_for(monkeypatch, [cred])
    downloader._configurer.update.side_effect = OSError("只读目录")
    monkeypatch.setattr(auth_utils, "check_status", AsyncMock(side_effect=HtmlResolveError("页面变化", code="TEST_PARSE_FAILURE")))
    monkeypatch.setattr("kmdr.core.bases.Confirm.ask", MagicMock(side_effect=AssertionError("未知额度不应询问余额不足")))
    asyncio.run(downloader.download(cred, BOOK, [VOLUME]))
    downloader._delegate._download.assert_awaited_once()


@pytest.mark.parametrize("value", ["", ' value=""'])
def test_missing_book_id_is_core_failure(value):
    session, _ = http_session(BOOK_PAGE.replace(' value="1"', value))
    with pytest.raises(HtmlResolveError):
        asyncio.run(lister_utils.extract_book_info_and_volumes(session, "/c/1.htm"))


@pytest.mark.parametrize("data", [[], {}, {"voldata": "wrong"}, {"voldata": [["id"]]}, {"voldata": [VOLUME_ROW[:4] + ["bad"] + VOLUME_ROW[5:]]}])
def test_invalid_volume_data_is_core_failure(data):
    session, _ = http_session(BOOK_PAGE, data)
    with pytest.raises(HtmlResolveError):
        asyncio.run(lister_utils.extract_book_info_and_volumes(session, "/c/1.htm"))


@pytest.mark.parametrize(
    ("field", "code"),
    [(0, "VOLUME_ID_INVALID"), (3, "VOLUME_TYPE_INVALID"), (4, "VOLUME_INDEX_INVALID"), (5, "VOLUME_NAME_INVALID"), (11, "VOLUME_SIZE_INVALID")],
)
def test_volume_diagnostics_identify_the_invalid_field(field, code):
    row = list(VOLUME_ROW)
    row[field] = ""
    session, _ = http_session(BOOK_PAGE, {"voldata": [row]})
    with pytest.raises(HtmlResolveError) as exc_info:
        asyncio.run(lister_utils.extract_book_info_and_volumes(session, "/c/1.htm"))
    assert exc_info.value.code == code
    assert f"字段 {field}" in exc_info.value.message
    assert code in str(exc_info.value)


def test_quota_downgrade_warning_keeps_error_code(monkeypatch):
    output = MagicMock()
    monkeypatch.setattr(auth_utils, "info", output)
    session, _ = http_session("<html>缺少额度区域</html>")
    cred = asyncio.run(auth_utils.check_status(session, MagicMock(), "user", {}))
    assert not cred.quota_known
    assert any("PROFILE_USER_TOTAL_MISSING" in str(call) for call in output.call_args_list)


@pytest.mark.parametrize("rows", [[], [VOLUME_ROW]])
def test_valid_volume_data_including_empty_list(rows):
    session, _ = http_session(BOOK_PAGE, {"voldata": rows})
    book, volumes = asyncio.run(lister_utils.extract_book_info_and_volumes(session, "/c/1.htm"))
    assert book.id == "1"
    assert len(volumes) == len(rows)


def test_missing_volume_pages_does_not_abort_download():
    row = list(VOLUME_ROW)
    row[6] = None
    session, _ = http_session(BOOK_PAGE, {"voldata": [row]})
    _, volumes = asyncio.run(lister_utils.extract_book_info_and_volumes(session, "/c/1.htm"))
    assert volumes[0].pages == 0
    assert volumes[0].id == VOLUME_ROW[0]


def test_follow_list_keeps_books_with_missing_metadata_and_skips_bad_rows():
    html = (
        '<tr style="height:36px;"><td>1</td><td>坏链接</td></tr>'
        '<tr style="height:36px;"><td>2</td><td><a href="/c/1.htm">测试</a></td><td>作者</td><td>状态</td></tr>'
    )
    lister = FollowedBookLister()
    lister._session, _ = http_session(html)
    books = asyncio.run(lister._list_followed_books({}))
    assert len(books) == 1
    assert books[0].author == "作者"
    assert books[0].last_update == ""


def test_unrecognized_follow_page_is_not_empty_list():
    lister = FollowedBookLister()
    lister._session, _ = http_session("<html>错误页面</html>")
    with pytest.raises(HtmlResolveError):
        asyncio.run(lister._list_followed_books({}))


@pytest.mark.parametrize("multipart", [False, True])
def test_callback_failure_preserves_completed_file_without_retry(monkeypatch, tmp_path, multipart):
    session, response = http_session()
    response.headers = {"content-length": "4"}

    async def chunks(_):
        yield b"book"

    response.content.iter_chunked = chunks
    callback = MagicMock(side_effect=RuntimeError("回调失败"))
    progress = MagicMock()
    if multipart:
        monkeypatch.setattr(download_utils, "_fetch_content_length", AsyncMock(side_effect=RangeNotSupportedError("不支持分片")))
        download = download_utils.download_file_multipart
    else:
        download = download_utils.download_file
    asyncio.run(download(session, MagicMock(), progress, "https://example.com/book", str(tmp_path), "book.epub", callback=callback))
    assert (tmp_path / "book.epub").read_bytes() == b"book"
    assert session.get.call_count == 1
    callback.assert_called_once()


def test_profile_network_failure_still_reaches_main_download(monkeypatch):
    import kmdr.main as main_module
    from kmdr.core.bases import AUTHENTICATOR, DOWNLOADER, LISTERS, PICKERS, SESSION_MANAGER

    cred_config = MagicMock()
    cred_config.cookie = {"token": "test"}
    cred_config.config.username = "user"
    cred_config.config.cred_pool = []
    authenticator = CookieAuthenticator(command="download")
    authenticator._configurer = cred_config
    authenticator._session = MagicMock()
    monkeypatch.setattr(auth_utils, "check_status", AsyncMock(side_effect=aiohttp.ClientConnectionError("断线")))
    session_manager = SimpleNamespace(session=AsyncMock(return_value=MagicMock()))
    lister = SimpleNamespace(list=AsyncMock(return_value=(BOOK, [VOLUME])))
    downloader = SimpleNamespace(download=AsyncMock())
    for registry, result in [
        (AUTHENTICATOR, authenticator),
        (SESSION_MANAGER, session_manager),
        (LISTERS, lister),
        (DOWNLOADER, downloader),
        (PICKERS, SimpleNamespace(pick=lambda volumes: volumes)),
    ]:
        monkeypatch.setattr(registry, "get", lambda args, result=result: result)
    asyncio.run(main_module.main(Namespace(command="download")))
    args = downloader.download.await_args.args
    assert args[0].cookies == {"token": "test"}
    assert not args[0].quota_known
    assert args[1:] == (BOOK, [VOLUME])


def test_pool_status_refresh_updates_unknown_quota_flag(monkeypatch):
    existing = credential()
    refreshed = credential(total=0, known=False)
    lister = PoolLister()
    monkeypatch.setattr(auth_utils, "check_status", AsyncMock(return_value=refreshed))
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    asyncio.run(lister._check_and_update_single(MagicMock(), existing, MagicMock()))
    assert not existing.quota_known
