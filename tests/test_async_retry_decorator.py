import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

import aiohttp

from kmdr.core.utils import async_retry
from kmdr.core.error import RedirectError

class TestAsyncRetryDecorator(unittest.TestCase):

    def test_success_on_first_try(self):
        mocked_successful_func = AsyncMock(return_value="Success")

        @async_retry(attempts=3)
        async def func_to_test():
            return await mocked_successful_func()

        result = asyncio.run(func_to_test())

        # 验证函数在第一次尝试时成功
        self.assertEqual(result, "Success")
        mocked_successful_func.assert_awaited_once()

    def test_retry_on_transient_error_and_succeeds(self):
        mock_conn_key = MagicMock(name="ConnectionKey")
        mocked_flaky_func = AsyncMock(side_effect=[
            aiohttp.ClientConnectorError(mock_conn_key, OSError("Connection failed")),
            aiohttp.ClientConnectorError(mock_conn_key, OSError("Connection failed again")),
            "Success on the third try"
        ])

        @async_retry(attempts=3, delay=0.01)
        async def func_to_test():
            return await mocked_flaky_func()

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = asyncio.run(func_to_test())

        # 验证函数在第三次尝试时成功
        self.assertEqual(result, "Success on the third try")
        self.assertEqual(mocked_flaky_func.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_fail_after_all_attempts(self):
        mocked_failing_func = AsyncMock(side_effect=asyncio.TimeoutError("Request timed out"))

        @async_retry(attempts=3, delay=0.01)
        async def func_to_test():
            return await mocked_failing_func()

        with self.assertRaises(asyncio.TimeoutError):
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                asyncio.run(func_to_test())
        
        # 验证三次尝试都失败
        self.assertEqual(mocked_failing_func.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_no_retry_on_non_retryable_status(self):
        mocked_404_func = AsyncMock(side_effect=aiohttp.ClientResponseError(
            history=(), request_info=MagicMock(), status=404, message="Not Found"
        ))

        @async_retry(attempts=3)
        async def func_to_test():
            return await mocked_404_func()

        with self.assertRaises(aiohttp.ClientResponseError) as cm:
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                asyncio.run(func_to_test())
        
        # 验证 404 错误没有重试
        self.assertEqual(cm.exception.status, 404)
        mocked_404_func.assert_awaited_once()
        mock_sleep.assert_not_called()

    def test_exponential_backoff_delay(self):
        mocked_failing_func = AsyncMock(side_effect=aiohttp.ClientError("Generic error"))

        @async_retry(attempts=4, delay=1, backoff=2)
        async def func_to_test():
            return await mocked_failing_func()

        with self.assertRaises(aiohttp.ClientError):
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                asyncio.run(func_to_test())

        # 验证指数退避的延迟时间
        self.assertEqual(mock_sleep.call_args_list[0].args[0], 1)
        self.assertEqual(mock_sleep.call_args_list[1].args[0], 2)
        self.assertEqual(mock_sleep.call_args_list[2].args[0], 4)
    
    def test_base_url_setter_called_on_redirect(self):
        mocked_failing_func = AsyncMock(side_effect=[
            RedirectError("redirected", "http://new-url.com"),
            "Success after redirect"
        ])

        url = "http://original-url.com"
        
        def base_url_setter(new_url):
            nonlocal url
            url = new_url

        @async_retry(base_url_setter=base_url_setter)
        async def func_to_test():
            return await mocked_failing_func()
        
        asyncio.run(func_to_test())

        # 验证 base_url_setter 被调用并更新了 URL
        self.assertEqual(url, "http://new-url.com")
        mocked_failing_func.assert_awaited()
