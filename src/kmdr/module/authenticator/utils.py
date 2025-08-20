from typing import Optional, Callable

from requests import Session

from kmdr.core.error import LoginError

def check_status(
        session: Session,
        show_quota: bool = False,
        is_vip_setter: Optional[Callable[[bool], None]] = None,
        level_setter: Optional[Callable[[int], None]] = None
) -> bool:
    response = session.get(url = 'https://kox.moe/my.php')

    try:
        response.raise_for_status()
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        return False
    
    if response.history and any(resp.status_code in (301, 302, 307) for resp in response.history) \
        and response.url == 'https://kox.moe/login.php':
        raise LoginError("Invalid credentials, please login again.", ['kmdr config -d cookie', 'kmdr login -u <username>'])

    if not show_quota:
        return True
    
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.text, 'html.parser')

    script = soup.find('script', language="javascript")

    # <script language='javascript'>
    # var user_level = "1";
    # var is_vip     = "0";
    # var i = 0;
    # 
    # ...
    # </script>

    # if script:
    #     script_content = script.string
    #     # 解析脚本内容，提取 VIP 状态和等级
    #     is_vip = "VIP" in script_content
    #     level = None
    #     level_match = re.search(r"level:\s*(\d+)", script_content)
    #     if level_match:
    #         level = int(level_match.group(1))

    #     if is_vip_setter:
    #         is_vip_setter(is_vip)
    #     if level_setter:
    #         level_setter(level)

    nickname = soup.find('div', id='div_nickname_display').text.strip().split(' ')[0]
    print(f"=========================\n\nLogged in as {nickname}\n\n=========================\n")
    
    quota = soup.find('div', id='div_user_vip').text.strip()
    print(f"=========================\n\n{quota}\n\n=========================\n")
    return True
    
