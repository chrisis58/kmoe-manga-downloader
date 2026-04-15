import asyncio
from argparse import Namespace
from typing import Callable

from kmdr import __version__


async def main(args: Namespace, fallback: Callable[[], None] = lambda: print("NOT IMPLEMENTED!")) -> None:
    from kmdr.core.console import _console, debug, emit, info, log

    with _console.status("初始化中..."):
        import kmdr.module  # noqa: F401
        from kmdr.core.bases import (
            AUTHENTICATOR,
            CONFIGURER,
            DOWNLOADER,
            LISTERS,
            PICKERS,
            POOL_MANAGER,
            SESSION_MANAGER,
        )

    log("[Lifecycle:Start] 启动 kmdr, 版本", __version__)
    debug("[bold green]以调试模式启动[/bold green]")
    debug("接收到的参数:", args)

    if args.command == "version":
        info(f"[green]{__version__}[/green]")
        emit(version=__version__)

    elif args.command == "query":
        from kmdr.core.task_query import query_task_status
        query_task_status(args.log_file)

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

    elif args.command == "search":
        async with await SESSION_MANAGER.get(args).session():
            from kmdr.core.bases import CATALOGERS
            from kmdr.core.utils import SharedAwaitable

            authenticator = AUTHENTICATOR.get(args)
            cataloger = CATALOGERS.get(args)

            t_auth = SharedAwaitable(authenticator.authenticate())
            t_catalog = cataloger.catalog(awaitable_cred=t_auth)

            _, books = await asyncio.gather(t_auth, t_catalog)
            debug("搜索成功，获取到", len(books), "本漫画。")

    elif args.command == "download":
        async with await SESSION_MANAGER.get(args).session():
            from kmdr.core.utils import SharedAwaitable

            authenticator = AUTHENTICATOR.get(args)
            lister = LISTERS.get(args)

            t_auth = SharedAwaitable(authenticator.authenticate())
            t_list = lister.list(awaitable_cred=t_auth)

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
    from kmdr.core.console import emit, exception, info, log
    from kmdr.core.defaults import argument_parser, post_init
    from kmdr.core.error import KmdrError

    try:
        parser = argument_parser()
        args = parser.parse_args()
        post_init(args)

        if getattr(args, "background", False) and args.command == "download":
            import sys

            from kmdr.core.background import start_background

            log_file, pid = start_background(sys.argv[1:])

            if getattr(args, "mode", "interactive") == "toolcall":
                emit(log_file=log_file, pid=pid)
            else:
                info("[green]后台任务已启动[/green]")
                info(f"日志文件: {log_file}")
                info(f"进程 PID: {pid}")
            return

        main_coro = main(args, parser.print_help)
        asyncio.run(main_coro)
    except KmdrError as e:
        info(f"[red]错误: {e}[/red]")
        emit(e)
    except KeyboardInterrupt:
        info("\n操作已取消（KeyboardInterrupt）", style="yellow")
        emit("操作已取消（KeyboardInterrupt）")
    except Exception as e:
        exception(e)
        emit(e)
    finally:
        log("[Lifecycle:End] 运行结束，kmdr 已退出")


if __name__ == "__main__":
    entry_point()
