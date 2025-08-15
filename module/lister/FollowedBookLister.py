from bs4 import BeautifulSoup

from core import Lister, LISTERS, BookInfo, VolInfo

from .utils import extract_book_info_and_volumes

MY_FOLLOW_URL = 'https://kox.moe/myfollow.php'

@LISTERS.register()
class FollowedBookLister(Lister):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self) -> tuple[BookInfo, list[VolInfo]]:
        followed_rows = BeautifulSoup(self._session.get(url = MY_FOLLOW_URL).text, 'html.parser').find_all('tr', style='height:36px;')
        mapped = map(lambda x: x.find_all('td'), followed_rows)
        filtered = filter(lambda x: '書名' not in x[1].text, mapped)
        books = map(lambda x: BookInfo(name = x[1].text, url = x[1].find('a')['href'], author = x[2].text, status = x[-1].text, last_update = x[-2].text, id = ''), filtered)
        books = list(books)

        print("\t最后更新时间\t书名")
        for v in range(len(books)):
            print(f"[{v + 1}]\t{books[v].last_update}\t{books[v].name}")
        
        choosed = input("choose a book to download: ")
        while not choosed.isdigit() or int(choosed) > len(books) or int(choosed) < 1:
            choosed = input("choose a book to download: ")
        choosed = int(choosed) - 1
        book = books[choosed]

        book_info, volumes = extract_book_info_and_volumes(self._session, book.url)
        book_info.author = book.author
        book_info.status = book.status
        book_info.last_update = book.last_update

        return book_info, volumes
        