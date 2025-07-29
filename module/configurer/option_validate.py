from typing import Optional
import os

__OPTIONS_VALIDATOR = {}

def validate(key: str, value: str) -> Optional[object]:
    if key in __OPTIONS_VALIDATOR:
        return __OPTIONS_VALIDATOR[key](value)
    else:
        print(f"Unsupported option: {key}. Supported options are: {', '.join(__OPTIONS_VALIDATOR.keys())}")
        return None

def _register_validator(func):
    global __OPTIONS_VALIDATOR

    func_name = func.__name__

    assert func_name.startswith('validate_'), \
        f"Validator function name must start with 'validate_', got '{func_name}'"

    __OPTIONS_VALIDATOR[func.__name__[9:]] = func
    return func

@_register_validator
def validate_num_workers(value: str) -> Optional[int]:
    try:
        num_workers = int(value)
        if num_workers <= 0:
            raise ValueError("Number of workers must be a positive integer.")
        return num_workers
    except ValueError as e:
        print(f"Invalid value for num_workers: {value}. {str(e)}")
        return None

@_register_validator
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

@_register_validator
def validate_retry(value: str) -> Optional[int]:
    try:
        retry = int(value)
        if retry < 0:
            raise ValueError("Retry count must be a non-negative integer.")
        return retry
    except ValueError as e:
        print(f"Invalid value for retry: {value}. {str(e)}")
        return None

@_register_validator
def validate_callback(value: str) -> Optional[str]:
    if not value:
        print("Callback cannot be empty.")
        return None
    return value

@_register_validator
def validate_proxy(value: str) -> Optional[str]:
    if not value:
        print("Proxy cannot be empty.")
        return None
    return value
