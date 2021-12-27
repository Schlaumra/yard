import datetime


def log(*args, target=None, level=0, **kwargs):
    """
    :param args:
    :param target:
    :param level:
    :param kwargs:
    :return:

    7 - emerg
    6 - lert
    5 - crit
    4 - err
    3 - warning
    2 - notice
    1 - info
    0 - debug
    """
    levels = ['debug', 'info', 'notice', 'warning', 'err', 'crit', 'lert', 'emerg']
    print(f"[{datetime.datetime.now()}] [{levels[level]}] [{target}]", *args, sep=" === ", **kwargs)
