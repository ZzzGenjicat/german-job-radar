import unittest

from radar.credentials import CredentialStore


class MemoryBackend:
    def __init__(self):self.values={}
    def set(self,name,secret):self.values[name]=secret
    def get(self,name):return self.values.get(name)
    def delete(self,name):self.values.pop(name,None)


class CredentialTests(unittest.TestCase):
    def test_set_get_delete_without_exposing_secret(self):
        backend=MemoryBackend();store=CredentialStore(backend)
        store.set('OpenAI','sk-secret-test')
        self.assertEqual(store.get('OpenAI'),'sk-secret-test')
        self.assertEqual(store.status('OpenAI'),{'configured':True})
        self.assertNotIn('sk-secret-test',repr(store.status('OpenAI')))
        store.delete('OpenAI')
        self.assertEqual(store.status('OpenAI'),{'configured':False})

    def test_rejects_empty_or_control_character_secret(self):
        store=CredentialStore(MemoryBackend())
        for value in ('','   ','sk-x\nheader'):
            with self.subTest(value=value),self.assertRaises(ValueError):store.set('OpenAI',value)


if __name__=='__main__':unittest.main()
