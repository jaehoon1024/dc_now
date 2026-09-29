import unittest

from src05_newsroom_collector import parse_lgu_press, parse_skb_press


class NewsroomParserTests(unittest.TestCase):
    def test_lgu_parser_keeps_press_releases_and_deduplicates(self):
        card = """
        <div class="latest-item"><a href="https://news.lguplus.com/123">
        <h3>AI 데이터센터 구축</h3><div class="meta">
        <span class="category">보도자료</span>
        <span class="date">2026.09.28</span></div></a></div>
        """
        payload = (card + card + """
        <div class="latest-item"><a href="https://news.lguplus.com/456">
        <h3>기업문화 이야기</h3><span class="category">기업뉴스</span>
        <span class="date">2026.09.27</span></a></div>
        """).encode()
        items = parse_lgu_press(payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "AI 데이터센터 구축")
        self.assertEqual(items[0]["published_at"].isoformat(),
                         "2026-09-28T00:00:00+09:00")

    def test_skb_parser_builds_canonical_detail_url(self):
        payload = """
        <a href="javascript:fn_read_view('1990');" class="news_graybox">
          <p class="news_graybox-tit">SKB AI 데이터센터 구축</p>
          <span class="news_graybox-date">2026.07.03</span>
        </a>
        <a href="javascript:fn_read_view('1989');" class="download_item">
          <p class="download_name link2">일반 보도자료</p>
          <p class="download_date">2026.07.01</p>
        </a>
        """.encode()
        items = parse_skb_press(payload)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "SKB AI 데이터센터 구축")
        self.assertIn("keynum=1990", items[0]["canonical_url"])
        self.assertEqual(items[1]["published_at"].isoformat(),
                         "2026-07-01T00:00:00+09:00")


if __name__ == "__main__":
    unittest.main()
