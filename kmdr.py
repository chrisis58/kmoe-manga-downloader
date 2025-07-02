from typing import Callable
from argparse import Namespace

from core import *
from module import *

def main(args: Namespace, fallback: Callable[[], None] = lambda: print('NOT IMPLEMENTED!')) -> None:

    if args.command == 'login':
        AUTHENTICATOR.get(args).authenticate()

    elif args.command == 'status':
        AUTHENTICATOR.get(args).authenticate()

    elif args.command == 'download':    

        if not AUTHENTICATOR.get(args).authenticate():
            print("Authentication failed. Please check your credentials.")
            return

        book, volumes = LISTERS.get(args).list()

        volumes = PICKERS.get(args).pick(volumes)

        DOWNLOADER.get(args).download(book, volumes)

    else:
        fallback()

if __name__ == '__main__':

    parser = argument_parser()
    args = parser.parse_args()

    main(args, lambda: parser.print_help())
