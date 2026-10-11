import unittest
from uuid import uuid4
from fastapi import HTTPException
from pydantic import ValidationError
from app.main import BrandInput, SlotCapacity, OrderInput
from app.services import parse_collection_code

class CampusServiceValidationTests(unittest.TestCase):
    def test_collection_code_parser(self):
        order_id=uuid4();token='x'*43
        self.assertEqual(parse_collection_code(f'CC3:{order_id}:{token}'),(order_id,token))
        for code in ('invalid',f'CC3:{order_id}:short',f'OTHER:{order_id}:{token}',f'CC3:invalid:{token}'):
            with self.subTest(code=code),self.assertRaises(HTTPException):parse_collection_code(code)
    def test_branding_normalizes_and_rejects_empty_text(self):
        brand=BrandInput(name=' My University ',initials='mu',tagline='Campus essentials')
        self.assertEqual(brand.name,'My University')
        self.assertEqual(brand.initials,'MU')
        with self.assertRaises(ValidationError):BrandInput(name='   ',initials='MU',tagline='Campus essentials')
    def test_capacity_bounds(self):
        for value in (0,-1,501):
            with self.subTest(capacity=value),self.assertRaises(ValidationError):SlotCapacity(capacity=value)
        self.assertEqual(SlotCapacity(capacity=12).capacity,12)
    def test_order_carries_reservation(self):
        order=OrderInput(customer_name='Student',items=[{'product_id':1,'quantity':1}],pickup_slot_id=10,pickup_location_id=1)
        self.assertEqual(order.pickup_slot_id,10)
