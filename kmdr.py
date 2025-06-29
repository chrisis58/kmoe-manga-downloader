from core import *
from module import *

def main():
    parser = argument_parser()
    args = parser.parse_args()

    if args.command == 'login':
        AUTHENTICATOR.get(args).authenticate()

    elif args.command == 'status':
        ...

    elif args.command == 'download':    

        if not AUTHENTICATOR.get(args).authenticate():
            print("Authentication failed. Please check your credentials.")
            return

        book, volumes = LISTERS.get(args).list()

        volumes = PICKERS.get(args).pick(volumes)

        DOWNLOADER.get(args).download(book, volumes)

    else:
        parser.print_help()

if __name__ == '__main__':
    main()
