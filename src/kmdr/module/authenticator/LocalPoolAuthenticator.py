from kmdr.core import AUTHENTICATOR, Authenticator, LoginError
from kmdr.core.console import emit
from kmdr.core.structure import Credential


@AUTHENTICATOR.register(hasvalues={"fast_auth": True}, order=-10)
class LocalPoolAuthenticator(Authenticator):
    """
    当启用 --fast-auth 参数时接管鉴权逻辑
    它不发起任何网络请求，而是直接从凭证池中检索默认的凭证
    """

    def __init__(self, *args, **kwargs):
        super().__init__(auto_save=False, *args, **kwargs)

    async def _authenticate(self) -> Credential:
        pool = self._configurer.config.cred_pool

        if not pool:
            raise LoginError(
                "未找到本地关联账号凭证，无法请求配置数据。请先执行 login 或者取消 --fast-auth", 
                ["kmdr login -u <username>"]
            )

        for cred in pool:
            if cred.status.value == "active" and cred.username == self._configurer.config.username:
                emit(cred)
                return cred

        raise LoginError(
            "本地凭证池中没有状态为 active 的可用凭证。请重新登录或取消 --fast-auth 进行联网验证。", 
            ["kmdr login -u <username>"]
        )
