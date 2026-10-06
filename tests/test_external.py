import socket
import unittest

from radar.security import validate_external_url, open_external


def resolver(host, port, type=0):
    addresses={
        'jobs.example': '93.184.216.34',
        'private.example': '192.168.1.8',
        'loop.example': '127.0.0.1',
    }
    value=addresses.get(host,'8.8.8.8')
    return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(value,port))]


class ExternalUrlTests(unittest.TestCase):
    def test_accepts_public_http_and_https(self):
        self.assertEqual(validate_external_url('https://jobs.example/job/1?x=2',resolver),'https://jobs.example/job/1?x=2')
        self.assertEqual(validate_external_url('http://jobs.example/job/1',resolver),'http://jobs.example/job/1')

    def test_rejects_unsafe_schemes_credentials_and_private_destinations(self):
        bad=['file:///c:/windows','javascript:alert(1)','data:text/plain,x','//jobs.example/x',
             'https://u:p@jobs.example/x','https://localhost/x','https://private.example/x','https://loop.example/x']
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_external_url(value,resolver)

    def test_opener_receives_validated_url_as_argument(self):
        calls=[]
        self.assertTrue(open_external('https://jobs.example/job/1',opener=lambda url,new=0:calls.append((url,new)) or True,resolver=resolver))
        self.assertEqual(calls,[('https://jobs.example/job/1',2)])


if __name__ == '__main__':
    unittest.main()
