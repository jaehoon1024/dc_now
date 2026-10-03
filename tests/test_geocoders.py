import unittest

from src23_kakao_address_geocoder import exact_parcel_match, parcel_key
from src24_google_embed_geocoder import exact_result


class GeocoderTests(unittest.TestCase):
    def test_parcel_key_supports_legal_ri_addresses(self):
        self.assertEqual(
            parcel_key("충청남도 당진시 송악읍 동곡리 379"),
            ("동곡리", "379"),
        )

    def test_exact_parcel_match_rejects_a_different_sub_lot(self):
        self.assertTrue(
            exact_parcel_match("서울특별시 구로구 구로동 422", "서울 구로구 구로동 422")
        )
        self.assertFalse(
            exact_parcel_match("서울특별시 구로구 구로동 422", "서울 구로구 구로동 422-10")
        )

    def test_google_result_requires_matching_lot_and_region(self):
        site = {
            "address_standard": "충청남도 당진시 송악읍 동곡리 379",
            "sido": "충청남도",
        }
        matching = {
            "resolved_address": "379 Donggok-ri, Songak-eup, Dangjin-si, Chungcheongnam-do, South Korea",
            "latitude": "36.9756023",
            "longitude": "126.7114381",
        }
        wrong_region = {**matching, "resolved_address": "379 Donggok-ri, Gyeonggi-do, South Korea"}
        self.assertTrue(exact_result(site, matching))
        self.assertFalse(exact_result(site, wrong_region))


if __name__ == "__main__":
    unittest.main()
