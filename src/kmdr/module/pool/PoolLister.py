import asyncio
from datetime import datetime
import random
from typing import Set

from rich.live import Live
from rich.table import Table
from rich.spinner import Spinner
from rich import box

from kmdr.core.bases import PoolManager, POOL_MANAGER
from kmdr.core.session import KmdrSessionManager
from kmdr.core.structure import CredentialStatus, Credential
from kmdr.core.console import debug, info

from kmdr.module.authenticator.utils import check_status

@POOL_MANAGER.register(
    hasvalues={'pool_command': 'list'}
)
class PoolLister(PoolManager):
    
    def __init__(self, refresh: bool = False, num_workers: int = 3, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__refresh = refresh
        self.__num_workers = num_workers
        self._updating_users: Set[str] = set()

    
    async def operate(self) -> None:
        if not self._pool.pool:
            info("凭证池为空, 请先使用 'kmdr pool add' 命令添加凭证。")
            return

        candidates = self._pool.pool if self.__refresh else self._pool.refresh_candidates
        debug("需要刷新的凭证数：", len(candidates))
        if not candidates:
            self._console.print(self._generate_table())
            info("剩余可用总额度: ", str(sum(c.quota_remaining for c in self._pool.pool if c.status == CredentialStatus.ACTIVE)), " MB")
            return

        # 耗时操作，刷新所有凭证状态
        async with (await KmdrSessionManager().session()) as session:

            self._updating_users = {c.username for c in candidates}
            
            semaphore = asyncio.Semaphore(self.__num_workers)

            with Live(self._generate_table(), console=self._console, refresh_per_second=12) as live:
                
                tasks = [
                    self._check_and_update_single(session, cred, semaphore) 
                    for cred in candidates
                ]
                
                for future in asyncio.as_completed(tasks):
                    updated_cred = await future
                    self._updating_users.remove(updated_cred.username)
                    live.update(self._generate_table())

        info("剩余可用总额度: ", str(sum(c.quota_remaining for c in self._pool.pool if c.status == CredentialStatus.ACTIVE)), " MB")
        try:
            self._configurer.update()
            debug("[green]已更新", len(candidates), "个凭证。[/green]")
        except Exception as e:
            info(f"[red]保存配置文件失败: {e}[/red]")


    def _format_time(self, timestamp: float) -> str:
        if not timestamp:
            return "-"
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M")

    def _format_status(self, status: CredentialStatus) -> str:
        if status == CredentialStatus.ACTIVE:
            return "[bold green]正常[/bold green]"
        elif status == CredentialStatus.INVALID:
            return "[bold red]失效[/bold red]"
        elif status == CredentialStatus.QUOTA_EXCEEDED:
            return "[yellow]配额耗尽[/yellow]"
        elif status == CredentialStatus.DISABLED:
            return "[dim white]禁用[/dim white]"
        else:
            return f"[cyan]{status.name}[/cyan]"

    def _generate_table(self) -> Table:
        credentials = self._pool.pool
        
        table = Table(
            title="凭证池状态",
            box=box.ROUNDED,
            header_style="bold blue",
            expand=True
        )

        table.add_column("Order", justify="center", style="dim", width=6)
        table.add_column("用户名", justify="center", style="magenta")
        table.add_column("昵称", justify="center", style="green")
        table.add_column("剩余额度", justify="center")
        table.add_column("状态", justify="center")
        table.add_column("最后更新", justify="center", style="dim", width=22) 
        table.add_column("备注", justify="center", style="dim italic")

        if not credentials:
            return table

        sorted_creds = sorted(credentials, key=lambda x: x.order)

        for cred in sorted_creds:
            time_str = self._format_time(cred.user_quota.update_at)
            
            if cred.username in self._updating_users:
                status_renderable = Spinner("dots", text="更新中...", style="yellow")
                last_update_renderable = Spinner("dots", text=f" {time_str}", style="yellow")
                quota_str = Spinner("dots", text=f"{cred.quota_remaining:.1f} MB", style="yellow")
            else:
                status_renderable = self._format_status(cred.status)
                last_update_renderable = time_str
                quota_str = f"{cred.quota_remaining:.1f} MB"
            

            table.add_row(
                str(cred.order),
                cred.username,
                cred.nickname or "-",
                quota_str,
                status_renderable,
                last_update_renderable,
                cred.note or "-"
            )
        
        return table

    async def _check_and_update_single(self, session, cred: Credential, semaphore: asyncio.Semaphore):
        async with semaphore:
            # 防止瞬时并发过高
            await asyncio.sleep(random.uniform(0, 0.3))

            try:
                new_cred = await check_status(
                    session=session,
                    console=self._console,
                    username=cred.username,
                    cookies=cred.cookies,
                    show_quota=False 
                )

                # rich.Live 有可能会读到部分更新的数据
                # 但是不会影响最终结果，所以这里不加锁
                cred.user_quota = new_cred.user_quota
                cred.vip_quota = new_cred.vip_quota
                cred.status = new_cred.status
                cred.level = new_cred.level
                cred.nickname = new_cred.nickname
                cred.cookies = new_cred.cookies

                return cred

            except Exception as e:
                cred.status = CredentialStatus.INVALID
                info(f"[red]更新用户 {cred.username} 失败[/red]")
                debug(f"更新用户 {cred.username} 失败: {e}")
                return cred
