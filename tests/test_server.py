import unittest
import app


class ServerTests(unittest.TestCase):
    def test_second_server_cannot_bind_same_address(self):
        first=app.LocalHTTPServer(('127.0.0.1',0),app.Handler)
        try:
            with self.assertRaises(OSError):
                second=app.LocalHTTPServer(first.server_address,app.Handler)
                second.server_close()
        finally:first.server_close()


if __name__=='__main__':unittest.main()
