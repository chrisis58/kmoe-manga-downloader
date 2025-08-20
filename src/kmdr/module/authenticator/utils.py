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
        raise LoginError("Invalid credentials, please login again.", ['kmdr config -c cookie', 'kmdr login -u <username>'])

    if not is_vip_setter and not level_setter:
        return True
    
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.text, 'html.parser')

    script = soup.find('script', language="javascript")

    if script:
        var_define = extract_var_define(script.text[:100])

        is_vip = int(var_define.get('is_vip', '0'))
        user_level = int(var_define.get('user_level', '0'))

        if is_vip_setter:
            is_vip_setter(is_vip >= 1)
        if level_setter:
            level_setter(user_level)
    
    if not show_quota:
        return True

    nickname = soup.find('div', id='div_nickname_display').text.strip().split(' ')[0]
    print(f"=========================\n\nLogged in as {nickname}\n\n=========================\n")
    
    quota = soup.find('div', id='div_user_vip').text.strip()
    print(f"=========================\n\n{quota}\n\n=========================\n")
    return True

def extract_var_define(script_text) -> dict[str, str]:
    var_define = {}
    for line in script_text.splitlines():
        line = line.strip()
        if line.startswith("var ") and "=" in line:
            var_name, var_value = line[4:].split("=", 1)
            var_define[var_name.strip()] = var_value.strip().strip(";").strip('"')
    return var_define
