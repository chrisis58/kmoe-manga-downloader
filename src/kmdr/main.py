from kmdr import __version__

from typing import Callable
from argparse import Namespace
import asyncio

from kmdr.core import *
from kmdr.module import *

async def main(args: Namespace, fallback: Callable[[], None] = lambda: print('NOT IMPLEMENTED!')) -> None:

    if args.command == 'version':
        info(f"[green]{__version__}[/green]")

    elif args.command == 'config':
        CONFIGURER.get(args).operate()

    elif args.command == 'login':
        async with (await SESSION_MANAGER.get(args).session()):
            await AUTHENTICATOR.get(args).authenticate()

    elif args.command == 'status':
        async with (await SESSION_MANAGER.get(args).session()):
            await AUTHENTICATOR.get(args).authenticate()

    elif args.command == 'download':
        async with (await SESSION_MANAGER.get(args).session()):
            await AUTHENTICATOR.get(args).authenticate()

            book, volumes = await LISTERS.get(args).list()

            volumes = PICKERS.get(args).pick(volumes)

            await DOWNLOADER.get(args).download(book, volumes)

    else:
        fallback()

def main_sync(args: Namespace, fallback: Callable[[], None] = lambda: print('NOT IMPLEMENTED!')) -> None:
    asyncio.run(main(args, fallback))

def entry_point():
    try:
        parser = argument_parser()
        args = parser.parse_args()

        main_coro = main(args, lambda: parser.print_help())
        asyncio.run(main_coro)
    except KmdrError as e:
        info(f"[red]错误: {e}[/red]")
        exit(1)
    except KeyboardInterrupt:
        info("\n操作已取消（KeyboardInterrupt）", style="yellow")
        exit(130)
    except Exception as e:
        exception(e)
        exit(1)
    

if __name__ == '__main__':
    entry_point()