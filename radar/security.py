"""Security helpers shared by browser opening and source configuration."""
import ipaddress
import socket
import webbrowser
from urllib.parse import urlsplit, urlunsplit


def validate_external_url(value, resolver=socket.getaddrinfo):
    if not isinstance(value,str) or len(value)>4096:
        raise ValueError('链接无效')
    try:
        parsed=urlsplit(value)
    except ValueError as exc:
        raise ValueError('链接无效') from exc
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError('仅允许公开的 HTTP/HTTPS 链接')
    host=parsed.hostname.rstrip('.').casefold()
    if host in ('localhost','localhost.localdomain') or not host:
        raise ValueError('不允许打开本机或内部地址')
    port=parsed.port or (443 if parsed.scheme=='https' else 80)
    try:
        addresses=resolver(host,port,type=socket.SOCK_STREAM)
    except (OSError,ValueError) as exc:
        raise ValueError('无法确认链接地址') from exc
    if not addresses:
        raise ValueError('无法确认链接地址')
    for entry in addresses:
        address=entry[4][0].split('%',1)[0]
        try:ip=ipaddress.ip_address(address)
        except ValueError as exc:raise ValueError('链接地址无效') from exc
        if not ip.is_global:
            raise ValueError('不允许打开本机或内部地址')
    clean=urlunsplit((parsed.scheme,parsed.netloc,parsed.path or '/',parsed.query,parsed.fragment))
    return clean


def open_external(value, opener=webbrowser.open, resolver=socket.getaddrinfo):
    return bool(opener(validate_external_url(value,resolver),new=2))
