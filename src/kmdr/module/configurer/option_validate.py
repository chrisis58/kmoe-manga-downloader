from typing import Optional
from functools import wraps
import os

__OPTIONS_VALIDATOR = {}

def validate(key: str, value: str) -> Optional[object]:
    """
    供外部调用的验证函数，根据键名调用相应的验证器。

    :param key: 配置项的键名
    :param value: 配置项的值
    :return: 验证后的值或 None
    """
    if key in __OPTIONS_VALIDATOR:
        return __OPTIONS_VALIDATOR[key](value)
    else:
        print(f"Unsupported option: {key}. Supported options are: {', '.join(__OPTIONS_VALIDATOR.keys())}")
        return None

def check_key(key: str, exit_if_invalid: bool = True) -> None:
    """
    供外部调用的验证函数，用于检查配置项的键名是否有效。
    如果键名无效，函数会打印错误信息并退出程序。

    :param key: 配置项的键名
    :param exit_if_invalid: 如果键名无效，是否退出程序
    """
    if key not in __OPTIONS_VALIDATOR:
        print(f"Unknown option: {key}. Supported options are: {', '.join(__OPTIONS_VALIDATOR.keys())}")
        if exit_if_invalid:
            exit(1)

def register_validator(arg_name):
    """
    验证函数的注册装饰器，用于将验证函数注册到全局验证器字典中。

    :param arg_name: 配置项的键名
    """

    def wrapper(func):
        global __OPTIONS_VALIDATOR
        __OPTIONS_VALIDATOR[arg_name] = func

        @wraps(func)
        def inner(*args, **kwargs):
            return func(*args, **kwargs)
    
        return inner

    return wrapper


#############################################
## 以下为各个配置项的验证函数。
#############################################

@register_validator('num_workers')
def validate_num_workers(value: str) -> Optional[int]:
    try:
        num_workers = int(value)
        if num_workers <= 0:
            raise ValueError("Number of workers must be a positive integer.")
        return num_workers
    except ValueError as e:
        print(f"Invalid value for num_workers: {value}. {str(e)}")
        return None

@register_validator('dest')
def validate_dest(value: str) -> Optional[str]:
    if not value:
        print("Destination cannot be empty.")
        return None
    if not os.path.exists(value) or not os.path.isdir(value):
        print(f"Destination directory does not exist or is not a directory: {value}")
        return None

    if not os.access(value, os.W_OK):
        print(f"Destination directory is not writable: {value}")
        return None

    if not os.path.isabs(value):
        print(f"Destination better be an absolute path: {value}")

    return value

@register_validator('retry')
def validate_retry(value: str) -> Optional[int]:
    try:
        retry = int(value)
        if retry < 0:
            raise ValueError("Retry count must be a non-negative integer.")
        return retry
    except ValueError as e:
        print(f"Invalid value for retry: {value}. {str(e)}")
        return None

@register_validator('callback')
def validate_callback(value: str) -> Optional[str]:
    if not value:
        print("Callback cannot be empty.")
        return None
    return value

@register_validator('proxy')
def validate_proxy(value: str) -> Optional[str]:
    if not value:
        print("Proxy cannot be empty.")
        return None
    return value
