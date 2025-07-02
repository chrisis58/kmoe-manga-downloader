from typing import Callable
from argparse import Namespace

from core import *
from module import *

def main(args: Namespace, fallback: Callable[[], None] = lambda: print('NOT IMPLEMENTED!')) -> None:

    if args.command == 'login':
        if not AUTHENTICATOR.get(args).authenticate():
            raise RuntimeError("Authentication failed. Please check your credentials.")

    elif args.command == 'status':
        if not AUTHENTICATOR.get(args).authenticate():
            raise RuntimeError("Authentication failed. Please check your credentials.")

    elif args.command == 'download':    
        if not AUTHENTICATOR.get(args).authenticate():
            raise RuntimeError("Authentication failed. Please check your credentials.")

        book, volumes = LISTERS.get(args).list()

        volumes = PICKERS.get(args).pick(volumes)

        DOWNLOADER.get(args).download(book, volumes)

    else:
        fallback()

if __name__ == '__main__':

    parser = argument_parser()
    args = parser.parse_args()

    main(args, lambda: parser.print_help())
