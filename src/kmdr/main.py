from typing import Callable
from argparse import Namespace
import asyncio

from kmdr import __version__


async def main(args: Namespace, fallback: Callable[[], None] = lambda: print("NOT IMPLEMENTED!")) -> None:
    from kmdr.core.console import info, debug, log, _console
    
    with _console.status("初始化中..."):
        from kmdr.core.bases import (
            SESSION_MANAGER,
            AUTHENTICATOR,
            LISTERS,
            PICKERS,
            DOWNLOADER,
            CONFIGURER,
            POOL_MANAGER,
        )
        from kmdr.core.defaults import post_init
        import kmdr.module  # Register plugins
    
    post_init(args)
    log("[Lifecycle:Start] 启动 kmdr, 版本", __version__)
    debug("[bold green]以调试模式启动[/bold green]")
    debug("接收到的参数:", args)

    if args.command == "version":
        info(f"[green]{__version__}[/green]")

    elif args.command == "config":
        CONFIGURER.get(args).operate()

    elif args.command == "login":
        async with await SESSION_MANAGER.get(args).session():
            cred = await AUTHENTICATOR.get(args).authenticate()
            debug("认证成功，凭证信息: ", cred)

    elif args.command == "status":
        async with await SESSION_MANAGER.get(args).session():
            cred = await AUTHENTICATOR.get(args).authenticate()
            debug("认证成功，凭证信息: ", cred)

    elif args.command == "download":
        async with await SESSION_MANAGER.get(args).session():
            t_auth = AUTHENTICATOR.get(args).authenticate()
            t_list = LISTERS.get(args).list()

            cred, (book, volumes) = await asyncio.gather(t_auth, t_list)
            debug("认证成功，凭证信息: ", cred)
            debug("获取到书籍《", book.name, "》及其", len(volumes), "个章节信息。")

            volumes = PICKERS.get(args).pick(volumes)
            debug("选择了", len(volumes), "个章节进行下载:", ", ".join(volume.name for volume in volumes))

            await DOWNLOADER.get(args).download(cred, book, volumes)

    elif args.command == "pool":
        await POOL_MANAGER.get(args).operate()

    else:
        fallback()


def main_sync(args: Namespace, fallback: Callable[[], None] = lambda: print("NOT IMPLEMENTED!")) -> None:
    asyncio.run(main(args, fallback))


def entry_point():
    from kmdr.core.defaults import argument_parser
    from kmdr.core.error import KmdrError
    from kmdr.core.console import info, exception, log
    
    try:
        parser = argument_parser()
        args = parser.parse_args()

        main_coro = main(args, parser.print_help)
        asyncio.run(main_coro)
    except KmdrError as e:
        info(f"[red]错误: {e}[/red]")
    except KeyboardInterrupt:
        info("\n操作已取消（KeyboardInterrupt）", style="yellow")
    except Exception as e:
        exception(e)
    finally:
        log("[Lifecycle:End] 运行结束，kmdr 已退出")


if __name__ == "__main__":
    entry_point()
