from typing import Callable
from argparse import Namespace

from kmdr.core import *
from kmdr.module import *

def main(args: Namespace, fallback: Callable[[], None] = lambda: print('NOT IMPLEMENTED!')) -> None:

    if args.command == 'login':
        AUTHENTICATOR.get(args).authenticate()

    elif args.command == 'status':
        AUTHENTICATOR.get(args).authenticate()

    elif args.command == 'download':
        AUTHENTICATOR.get(args).authenticate()

        book, volumes = LISTERS.get(args).list()

        volumes = PICKERS.get(args).pick(volumes)

        DOWNLOADER.get(args).download(book, volumes)

    elif args.command == 'config':
        CONFIGURER.get(args).operate()

    else:
        fallback()

def entry_point():
    try:
        parser = argument_parser()
        args = parser.parse_args()
        main(args, lambda: parser.print_help())
    except KeyboardInterrupt:
        print("\n操作已取消（KeyboardInterrupt）")
        exit(130)

if __name__ == '__main__':
    entry_point()