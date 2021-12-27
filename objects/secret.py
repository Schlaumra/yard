import string
import secrets


def create_secret(length, *args, numbers=True, alphabet=(False, True), symbols=""):
    choices = ""
    if numbers:
        choices += string.digits
    if alphabet[0]:
        choices += string.ascii_lowercase
    if alphabet[1]:
        choices += string.ascii_uppercase
    if symbols:
        choices += symbols

    while True:
        secret = ''.join(secrets.choice(choices) for _ in range(length))

        if (not numbers or any(c.isdigit() for c in secret)
                and (not alphabet[0] or any(c.islower() for c in secret))
                and (not alphabet[1] or any(c.isupper() for c in secret))
                and (not symbols or any(c in symbols for c in secret))):
            break

    return secret
