from requests import Session

def check_status(session: Session, show_quota: bool = False) -> bool:
    response = session.get(url = 'https://kox.moe/my.php')

    try:
        response.raise_for_status()
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        return False

    if not show_quota:
        return True
    
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.text, 'html.parser')
    
    nickname = soup.find('div', id='div_nickname_display').text.strip().split(' ')[0]
    print(f"=========================\n\nLogged in as {nickname}\n\n=========================\n")
    
    quota = soup.find('div', id='div_user_vip').text.strip()
    print(f"=========================\n\n{quota}\n\n=========================\n")
    
