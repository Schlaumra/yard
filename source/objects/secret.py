import secrets
import string
from typing import Tuple


def create_secret(
        length: int,
        *,
        numbers: bool = True,
        alphabet: Tuple[bool, bool] = (False, True),
        symbols: str = "") -> str:
    """
    Create a secret with the given parameters.
    If length is smaller than min_length (len-types) it will not check if all types are present.

    :param length: int: the length of the secret
    :param numbers: bool: If numbers should be included
    :param alphabet: (bool, bool): Upper and lowercase -> (lower, upper)
    :param symbols: str: special symbols that should be included
    :return: str: The secret
    """

    # Create a string with allowed chars
    choices = ""
    min_length = 0
    if numbers:
        min_length += 1
        choices += string.digits
    if alphabet[0]:
        min_length += 1
        choices += string.ascii_lowercase
    if alphabet[1]:
        min_length += 1
        choices += string.ascii_uppercase
    if symbols:
        min_length += 1
        choices += symbols

    # Create the secret and check if min 1 per type is in it
    if length >= min_length:
        while True:
            secret = ''.join(secrets.choice(choices) for _ in range(length))

            if (not numbers or any(c.isdigit() for c in secret)
                    and (not alphabet[0] or any(c.islower() for c in secret))
                    and (not alphabet[1] or any(c.isupper() for c in secret))
                    and (not symbols or any(c in symbols for c in secret))):
                break
        return secret
    else:
        return ''.join(secrets.choice(choices) for _ in range(length))
