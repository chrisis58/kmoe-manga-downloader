import asyncio
from datetime import datetime
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
        credentials = self._pool.pool

        if not credentials:
            info("凭证池为空, 请先使用 'kmdr pool add' 命令添加凭证。")
            return

        if not self.__refresh:
            self._console.print(self._generate_table())
            info("剩余可用额度: ", str(sum(c.quota_remaining for c in credentials if c.status == CredentialStatus.ACTIVE)), " MB")
            return

        # 耗时操作，刷新所有凭证状态
        async with (await KmdrSessionManager().session()) as session:

            self._updating_users = {c.username for c in credentials}
            
            semaphore = asyncio.Semaphore(self.__num_workers)

            with Live(self._generate_table(), console=self._console, refresh_per_second=12) as live:
                
                tasks = [
                    self._check_and_update_single(session, cred, semaphore) 
                    for cred in credentials
                ]
                
                for future in asyncio.as_completed(tasks):
                    updated_cred = await future
                    self._updating_users.remove(updated_cred.username)
                    live.update(self._generate_table())

        info("剩余可用额度: ", str(sum(c.quota_remaining for c in credentials if c.status == CredentialStatus.ACTIVE)), " MB")
        try:
            self._configurer.update()
            debug("[green]已更新", len(credentials), "个凭证。[/green]")
        except Exception as e:
            info(f"[red]保存配置文件失败: {e}[/red]")


    def _format_time(self, timestamp: float) -> str:
        if not timestamp:
            return "-"
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M")

    def _format_status(self, status: CredentialStatus) -> str:
        if status == CredentialStatus.ACTIVE:
            return "[bold green]ACTIVE[/bold green]"
        elif status == CredentialStatus.INVALID:
            return "[bold red]INVALID[/bold red]"
        elif status == CredentialStatus.QUOTA_EXCEEDED:
            return "[yellow]EXCEEDED[/yellow]"
        elif status == CredentialStatus.DISABLED:
            return "[dim white]DISABLED[/dim white]"
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

        table.add_column("Order", justify="right", style="dim", width=6)
        table.add_column("用户名", style="magenta")
        table.add_column("昵称", style="green")
        table.add_column("剩余额度", justify="right")
        table.add_column("状态", justify="center")
        table.add_column("最后更新", style="dim", width=22) 
        table.add_column("备注", style="dim italic")

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
            try:
                new_cred = await check_status(
                    session=session,
                    console=self._console,
                    username=cred.username,
                    cookies=cred.cookies,
                    show_quota=False 
                )

                cred.user_quota = new_cred.user_quota
                cred.vip_quota = new_cred.vip_quota
                cred.status = new_cred.status
                cred.level = new_cred.level
                cred.nickname = new_cred.nickname
                cred.cookies = new_cred.cookies

                await asyncio.sleep(10)

                return cred

            except Exception as e:
                cred.status = CredentialStatus.INVALID
                info(f"[red]更新用户 {cred.username} 失败[/red]")
                return cred
