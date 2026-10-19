import unittest
from investment_analysis import classify

class ClassificationTests(unittest.TestCase):
    def test_explicit_independent_house(self):
        self.assertEqual(classify({"title":"Maison indépendante de plain-pied"} )[0], "Verified standalone wording")
    def test_floor_of_villa_excluded(self):
        self.assertEqual(classify({"title":"RDC de villa à louer"} )[0], "Excluded")
    def test_generic_house_unverified(self):
        self.assertEqual(classify({"title":"Maison à vendre","category":"house"})[0], "Unverified property type")
    def test_apartment_excluded(self):
        self.assertEqual(classify({"title":"Appartement S+2"})[0], "Excluded")

if __name__ == "__main__":
    unittest.main()
