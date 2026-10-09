import unittest
from pydantic import ValidationError
from app.main import OrderInput


class OrderValidationTests(unittest.TestCase):
    def test_valid_order_normalizes_name(self):
        order = OrderInput(customer_name=" Sathwik ", items=[{"product_id": 1, "quantity": 2}])
        self.assertEqual(order.customer_name, "Sathwik")

    def test_rejects_invalid_orders(self):
        cases = [
            {"customer_name": " ", "items": [{"product_id": 1, "quantity": 1}]},
            {"customer_name": "Student", "items": []},
            {"customer_name": "Student", "items": [{"product_id": 1, "quantity": 0}]},
            {"customer_name": "Student", "items": [{"product_id": 1, "quantity": 101}]},
            {"customer_name": "Student", "items": [{"product_id": 1, "quantity": 1}, {"product_id": 1, "quantity": 2}]},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValidationError):
                OrderInput(**case)
