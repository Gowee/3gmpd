import scrapy


class BookSpider(scrapy.Spider):
    name = 'book'
    allowed_domains = ['www.3gmuseum.cn']
    start_urls = ['http://www.3gmuseum.cn/']

    def parse(self, response):
        pass
