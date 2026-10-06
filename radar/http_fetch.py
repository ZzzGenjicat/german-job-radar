"""HTML transport pinned to vetted public IPs; TLS still verifies the hostname."""
import http.client
import ipaddress
import re
import socket
import urllib.error
from urllib.parse import urljoin, urlsplit
from lxml import html
from .core import now_utc

MAX_BYTES = 3500000


def public_addresses(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError('不支持的网页地址')
    if parsed.port not in (None, 80, 443):raise ValueError('非公开网页端口')
    host = parsed.hostname.encode('idna').decode('ascii')
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses:raise ValueError('无法解析公开网页地址')
    for family, _, _, _, address in addresses:
        if family not in (socket.AF_INET, socket.AF_INET6) or not ipaddress.ip_address(address[0].split('%', 1)[0]).is_global:
            raise ValueError('禁止请求本机或内网地址')
    return parsed, host, port, addresses


def pinned_socket(addresses, timeout):
    last_error = None
    for family, socktype, proto, _, address in addresses[:10]:
        connection = socket.socket(family, socktype, proto)
        try:
            connection.settimeout(timeout); connection.connect(address)
            peer = ipaddress.ip_address(connection.getpeername()[0].split('%', 1)[0])
            if not peer.is_global or peer != ipaddress.ip_address(address[0].split('%', 1)[0]):
                raise ValueError('连接目标与已核验公网地址不一致')
            return connection
        except OSError as error:
            connection.close(); last_error = error
        except Exception:
            connection.close(); raise
    raise last_error or OSError('无法连接已核验网页地址')


def fetch_html(url, timeout=12, before_request=None):
    seen = set()
    for _ in range(8):
        if url in seen:raise ValueError('网页重定向循环')
        seen.add(url)
        parsed, host, port, addresses = public_addresses(url)
        if before_request:before_request(url)
        cls = http.client.HTTPSConnection if parsed.scheme == 'https' else http.client.HTTPConnection
        connection = cls(host, port=port, timeout=timeout)
        # HTTPSConnection retains hostname certificate checks and SNI; TCP uses
        # only the numeric addresses from the single validated DNS response.
        connection._create_connection = lambda *args, **kwargs: pinned_socket(addresses, timeout)
        try:
            target = (parsed.path or '/') + ('?' + parsed.query if parsed.query else '')
            connection.request('GET', target, headers={'User-Agent':'Mozilla/5.0 (compatible; LocalJobRadar/1.0; job search)',
                'Accept':'text/html,application/xhtml+xml','Accept-Encoding':'identity','Accept-Language':'de-DE,de;q=0.9,en;q=0.5'})
            response = connection.getresponse()
            if response.status in (301,302,303,307,308):
                location = response.headers.get('Location')
                if not location:raise ValueError('重定向缺少目标网址')
                url = urljoin(url,location); continue
            if response.status >= 400:
                raise urllib.error.HTTPError(url,response.status,response.reason,response.headers,None)
            raw = response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:raise ValueError('页面过大，停止读取')
            body = raw.decode(response.headers.get_content_charset() or 'utf-8',errors='replace')
            result = {'body':body,'url':url,'status':response.status,'at':now_utc().isoformat()}
        finally:connection.close()
        document = html.fromstring(body or '<html></html>')
        refresh = document.xpath('//meta[translate(@http-equiv,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="refresh"]/@content')
        if refresh:
            match = re.search(r'url\s*=\s*["\x27]?([^"\x27]+)',refresh[0],re.I)
            if match:
                target = urljoin(url,match[1].strip())
                if target != url:url = target; continue
        return result
    raise ValueError('网页重定向次数过多')
