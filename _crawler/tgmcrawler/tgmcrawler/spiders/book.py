import scrapy


class BookSpider(scrapy.Spider):
    name = 'book'
    allowed_domains = ['www.3gmuseum.cn']
    start_urls = ['http://www.3gmuseum.cn/web/ancient/toAncient.do?itemno=50&itemsonno=8280819a60d452fe0160d46016c00016']

    def parse(self, response):
        roll = response.css(".ancient-books-list")
        for book in roll.css(".ancient-book"):
            name = book.css("ancient-book-name").
            cover_image_url = book.css("img").attrib['src']

