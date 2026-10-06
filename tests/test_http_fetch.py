import io
import socket
import unittest
from unittest.mock import patch


class FakeSocket:
    def __init__(self, body=b'<html>Public fixture</html>', status='200 OK', extra=''):
        self.destination=None
        self.response=(f'HTTP/1.1 {status}\r\nContent-Length: {len(body)}\r\nContent-Type: text/html; charset=utf-8\r\n{extra}\r\n'.encode()+body)
    def settimeout(self,value):pass
    def setsockopt(self,*args):pass
    def connect(self,address):self.destination=address
    def getpeername(self):return self.destination
    def sendall(self,data):pass
    def makefile(self,*args):return io.BytesIO(self.response)
    def close(self):pass


class HttpFetchTests(unittest.TestCase):
    def test_rebinding_cannot_trigger_second_dns_resolution(self):
        from radar.http_fetch import fetch_html
        public=(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',80))
        private=(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',80))
        fake=FakeSocket()
        with patch('socket.getaddrinfo',side_effect=[[public],[private]]) as dns,patch('socket.socket',return_value=fake):
            result=fetch_html('http://example.test/job',3)
        self.assertEqual(dns.call_count,1)
        self.assertEqual(fake.destination,('93.184.216.34',80))
        self.assertIn('Public fixture',result['body'])

    def test_redirect_to_loopback_is_rejected_before_connecting(self):
        from radar.http_fetch import fetch_html
        public=(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',80))
        private=(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',80))
        fake=FakeSocket(status='302 Found',extra='Location: http://private.test/admin\r\n')
        with patch('socket.getaddrinfo',side_effect=[[public],[private]]),patch('socket.socket',return_value=fake) as sockets:
            with self.assertRaises(ValueError):fetch_html('http://example.test/job',3)
            self.assertEqual(sockets.call_count,1)

    def test_empty_dns_result_and_nonweb_ports_are_rejected(self):
        from radar.http_fetch import fetch_html
        with patch('socket.getaddrinfo',return_value=[]):
            with self.assertRaises(ValueError):fetch_html('https://example.test/job',3)
        with self.assertRaises(ValueError):fetch_html('https://example.test:22/job',3)


if __name__ == '__main__':unittest.main()
