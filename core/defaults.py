from typing import Optional
import argparse

parser: Optional[argparse.ArgumentParser] = None
args: Optional[argparse.Namespace] = None

def argument_parser():
    global parser
    if parser is not None:
        return parser

    parser = argparse.ArgumentParser(description='Kox Downloader')
    subparsers = parser.add_subparsers(title='subcommands', dest='command')

    download_parser = subparsers.add_parser('download', help='Download books')
    download_parser.add_argument('-d', '--dest', type=str, help='Download destination', required=True)
    download_parser.add_argument('--book-id', type=str, help='Book id', required=False)
    download_parser.add_argument('--book-name', type=str, help='Book name (searching only in followed)', required=False)
    download_parser.add_argument('-v','--volume', type=str, help='Volume(s), split using commas, `all` for all', required=False)
    download_parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files', required=False)
    download_parser.add_argument('-p', '--proxy', type=str, help='Proxy server', required=False)
    download_parser.add_argument('-r', '--retry', type=int, help='Retry times', required=False)
    download_parser.add_argument('--call-back', '-c', type=str, help='Callback sctipt, use as `echo {v.name} downloaded!`', required=False)

    login_parser = subparsers.add_parser('login', help='Login to kox.moe')
    login_parser.add_argument('-u', '--username', type=str, help='Your username', required=True)
    login_parser.add_argument('-p', '--password', type=str, help='Your password', required=True)

    status_parser = subparsers.add_parser('status', help='Show status of account and script')
    status_parser.add_argument('-p', '--proxy', type=str, help='Proxy server', required=False)

    return parser

def parse_args():
    global args
    if args is not None:
        return args

    parser = argument_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        exit(1)

    return args