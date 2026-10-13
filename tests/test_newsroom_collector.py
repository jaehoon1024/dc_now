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



class LguArchiveTests(unittest.TestCase):
    BASE='https://news.lguplus.com/category/%ED%94%84%EB%A0%88%EC%8A%A4%EC%84%BC%ED%84%B0/%EB%B3%B4%EB%8F%84%EC%9E%90%EB%A3%8C/'
    def card(self,date='2026.06.08',url='https://news.lguplus.com/21965',category='보도자료'):
        return ('<li class="post-item-wrap"><a class="post-title" href="'+url+'">파주 <b>AIDC</b> 전략</a><a class="post-excerpt">수집하면 안 되는 본문 요약</a><span class="post-category"><a>프레스센터</a> &gt; <a>'+category+'</a></span><span class="post-date">'+date+'</span></li>')
    def test_archive_reads_nested_title_category_and_date_but_not_excerpt(self):
        from src05_newsroom_collector import parse_lgu_archive
        rows=parse_lgu_archive((self.card()+self.card()+self.card(url='https://news.lguplus.com/9',category='기업뉴스')).encode())
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title'],'파주 AIDC 전략')
        self.assertNotIn('본문',str(rows));self.assertEqual(rows[0]['published_at'].year,2026)
    def test_head_next_link_is_followed_and_external_search_and_skips_are_rejected(self):
        from src05_newsroom_collector import next_archive_url
        page2=self.BASE+'page/2/'
        html=('<a href="https://evil.example/page/2/">x</a><a href="'+self.BASE+'page/3/">skip</a><a href="'+page2+'?s=파주">search</a><link rel="next" href="'+page2+'">').encode()
        self.assertEqual(next_archive_url(html,self.BASE),page2)
        self.assertIsNone(next_archive_url(html,'https://evil.example/category/프레스센터/보도자료/'))
    def test_date_cutoff_stops_at_requested_range_and_preserves_request_interval(self):
        from datetime import date
        from src05_newsroom_collector import article_batches
        page={'page_url':self.BASE,'parser_code':'LGUPLUS_ARCHIVE_V1','request_interval_seconds':30}
        calls=[];delays=[]
        def fetch(p):
            calls.append(p['page_url'])
            if len(calls)==1:return (self.card()+'<link rel="next" href="'+self.BASE+'page/2/">').encode()
            return (self.card(date='2026.04.30',url='https://news.lguplus.com/1')+'<link rel="next" href="'+self.BASE+'page/3/">').encode()
        batches=list(article_batches(page,5,date(2026,5,1),fetch,delays.append))
        self.assertEqual(len(calls),2);self.assertEqual(delays,[30]);self.assertEqual(page['scan_end'],'date_limit');self.assertEqual(len(batches[-1]),0)
    def test_page_limit_does_not_claim_archive_is_complete(self):
        from src05_newsroom_collector import article_batches
        page={'page_url':self.BASE,'parser_code':'LGUPLUS_ARCHIVE_V1','request_interval_seconds':30}
        payload=(self.card()+'<link rel="next" href="'+self.BASE+'page/2/">').encode()
        list(article_batches(page,1,None,lambda _:payload,lambda _:None))
        self.assertEqual(page['scan_end'],'page_limit');self.assertEqual(page['pages_scanned'],1)

if __name__=='__main__':unittest.main()
