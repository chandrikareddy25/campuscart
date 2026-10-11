import unittest
from pydantic import ValidationError
from app.security import hash_password, verify_password, token_hash
from app.main import Registration, ProductInput

class SecurityTests(unittest.TestCase):
    def test_salted_password_verification(self):
        first=hash_password('long-secure-password')
        self.assertNotEqual(first,hash_password('long-secure-password'))
        self.assertTrue(verify_password('long-secure-password',first))
        self.assertFalse(verify_password('incorrect-password',first))
        self.assertFalse(verify_password('long-secure-password','invalid'))
    def test_session_token_is_hashed(self):
        self.assertNotEqual(token_hash('session-token'),'session-token')
        self.assertEqual(len(token_hash('session-token')),64)
    def test_registration_validation(self):
        with self.assertRaises(ValidationError):
            Registration(email='invalid',name='Student',password='long-password-123')
        with self.assertRaises(ValidationError):
            Registration(email='a@example.com',name='Student',password='short')
    def test_product_image_and_money_validation(self):
        body=dict(name='Notebook',description='Study notebook',stock=10,category='Stationery',price='80.00')
        for change in ({'images':['javascript:alert(1)']},{'price':'80.123'},{'stock':-1},{'category':'Unknown'}):
            with self.subTest(change=change),self.assertRaises(ValidationError):
                ProductInput(**{**body,**change})
