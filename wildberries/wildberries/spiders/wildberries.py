import json
import random
from datetime import datetime

import scrapy

from ..items import WildberriesItem


class WildberriesSpider(scrapy.Spider):
    name = 'wildberries'
    allowed_domains = ['wildberries.ru']
    start_urls = ['https://www.wildberries.ru/catalog/aksessuary/veera']  # указываем желаемую категорию
    item = WildberriesItem()
    # г. Москва, ул. Арбат 4, с. 1
    cookies = {
        '__wbl': 'cityId%3D0%26regionId%3D0%26city%3D%D0%B3%20%D0%9C%D0%BE%D1%81%D0%BA%D0%B2%D0%B0%2C%20%D0%A3%D0%BB%D0%B8%D1%86%D0%B0%20%D0%90%D1%80%D0%B1%D0%B0%D1%82%204%D1%811%26phone%3D88001007505%26latitude%3D55%2C752114%26longitude%3D37%2C598587%26src%3D1',
        '__region': '64_75_4_38_30_33_70_68_71_22_31_66_40_1_80_69_48',
        '__store': '119261_122252_122256_117673_122258_122259_121631_122466_122467_122495_122496_122498_122590_122591_122592_123816_123817_123818_123820_123821_123822_124093_124094_124095_124096_124097_124098_124099_124100_124101_124583_124584_125238_125239_125240_132318_132320_132321_125611_135243_135238_133917_132871_132870_132869_132829_133084_133618_132994_133348_133347_132709_132597_132807_132291_132012_126674_126676_127466_126679_126680_127014_126675_126670_126667_125186_116433_119400_507_3158_117501_120602_6158_121709_120762_124731_1699_130744_2737_117986_1733_686_132043',
    }
    proxy_list = [
        '188.130.186.88:3000',
        '109.248.13.233:3000',
        '188.130.211.27:3000',
        '109.248.49.171:3000',
        '95.182.127.19:3000',
        '95.182.124.180:3000',
        '46.8.11.161:3000',
        '188.130.136.84:3000',
        '45.90.196.41:3000',
        '46.8.56.153:3000',
        '188.130.219.141:3000',
        '109.248.128.82:3000',
        '188.130.129.184:3000',
        '109.248.48.235:3000',
        '188.130.129.196:3000',
        '185.181.244.178:3000',
        '46.8.14.58:3000',
        '188.130.221.80:3000',
        '46.8.110.172:3000',
        '109.248.143.156:3000',
    ]  # текущие прокси привязаны к моему IP, требуется заменить на свои

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url,
                                 callback=self.parse_catalog,
                                 cookies=self.cookies,
                                 meta={'proxy': random.choice(self.proxy_list)})

    def parse_catalog(self, response):
        # не уверен, что куки используются правильно, по полученным данным они используются только в start_requests
        products_on_page = response.css('.product-card__wrapper')

        product_urls = []
        for product in products_on_page:
            product_url = product.css('.product-card__main.j-open-full-product-card::attr(href)').get()
            product_url = response.urljoin(product_url)
            product_urls.append(product_url)
            yield scrapy.Request(url=product_url,
                                 callback=self.parse_product_details,
                                 cookies=self.cookies,
                                 meta={'proxy': random.choice(self.proxy_list)})

        next_page_button_url = response.css('.pagination__next::attr(href)').get()
        if next_page_button_url:
            next_page_url = response.urljoin(next_page_button_url)
            yield scrapy.Request(url=next_page_url,
                                 callback=self.parse_catalog,
                                 cookies=self.cookies,
                                 meta={'proxy': random.choice(self.proxy_list)})

    def parse_product_details(self, response):
        # в теле страницы лежит JSON с данными о товаре, некоторые данные нельзя получить без этого JSON'а
        # ищем внутри всех тегов <script> JSON с ключом "staticResourses". Берём всю строку до '}}'
        data: list = response.xpath("//script[contains(., 'staticResourses')]/text()").re("{\"staticResourses\":.*}}")
        product_data: dict = json.loads(data[0]) if len(data) > 0 else ''

        product_id = str(product_data.get('rqCod1S'))  # RPC в словаре
        nomenclatures_by_product_id: dict = product_data.get('productCard').get('nomenclatures').get(product_id)

        product_name = product_data.get('productCard').get('goodsName', '')
        product_color = nomenclatures_by_product_id.get('colorName', '')
        if product_color:
            product_title = f'{product_name}, {product_color}'
        else:
            product_title = product_name

        try:  # возможно, нужна сумма 'quantity' из всех 'sizes' (сумма товаров по всем размерам модели)
            product_quantity: int = nomenclatures_by_product_id.get('sizes')[0].get('quantity', 0)
        except IndexError:
            product_quantity = 0

        section_len = len(product_data.get('sitePath', []))  # количество разделов, в котором находится продукт
        section = []
        if section_len > 0:
            for i in range(section_len - 1):  # последний раздел - имя бренда, его не вносим в список разделов
                section.append(product_data['sitePath'][i].get('name'))

        original_price = product_data.get('priceForProduct').get('price')
        current_price = product_data.get('priceForProduct').get('priceWithSale') or original_price
        try:
            sale_percent: float = round(100 - current_price * 100 / original_price, 2)  # 42.93
        except ZeroDivisionError:
            sale_percent: int = product_data.get('priceForProduct').get('sale')  # парсим скидку в процентах с сайта
        sale_tag = f'Скидка {sale_percent}%' if sale_percent else ''

        product_images: list = product_data.get('selectedNomenclature').get('imageHelper')
        if len(product_images) > 0:
            main_image: str = product_images[0].get('zoom', '')
        else:
            main_image = ''
        number_of_product_images = len(product_images)
        all_images = []
        for i in range(number_of_product_images):
            image_url = product_images[i].get('zoom')
            all_images.append(image_url)

        has_3d_view = nomenclatures_by_product_id.get('has3DView')
        view_360_images = []
        if has_3d_view:
            for i in range(11):  # по моим наблюдениям изображений у 3d_view всегда 11 (от 0 до 10)
                view_360_images.append(f'//images.wbstatic.net/3d/{product_id}/{i}.jpg')

        has_video = nomenclatures_by_product_id.get('hasVideo')
        if has_video:
            # можно регуляркой вытащить из <head>-блока, но решил не возиться, этот метод кажется стабильным
            # может ли у одного товара быть несколько видео? не нашёл таких
            # у товара с ID 11568570 гарантируется такой же ID категории, но в конце четыре нуля - 11560000
            # название "категория" не совсем корректно, но сложно это как-то иначе назвать
            video_category_id = product_id[:-4] + '0000'
            video_url = f'//video.wbstatic.net/video/new/{video_category_id}/{product_id}.mp4'
        else:
            video_url = ''

        product_metadata = dict()  # свойства продукта - страна производитель, материал, особенности модели и тд
        product_metadata['__description'] = product_data.get('productCard').get('description', '')
        # нужно ли указывать артикул товара для wildberries, если он совпадает с RPC и отсутствует в property?
        product_options = product_data.get('productCard').get('addedOptions')
        for i in range(len(product_options)):
            product_property = product_options[i].get('property', '')
            product_subproperty = product_options[i].get('subProperty', '')
            product_metadata[product_property] = product_subproperty

        self.item['timestamp'] = datetime.utcnow()
        self.item['RPC'] = product_id
        self.item['url'] = response.url
        self.item['title'] = product_title
        self.item['marketing_tags'] = []  # не нашёл на Wildberries подобные товары, но нашёл в json поле promoText
        self.item['brand'] = product_data.get('productCard').get('brandName', '')
        self.item['section'] = section
        self.item['price_data'] = {
            'current': float(current_price),
            'original': float(original_price),
            'sale_tag': sale_tag
        }
        self.item['stock'] = {
            'in_stock': not nomenclatures_by_product_id.get('soldOut'),  # False if 'soldOut': true
            'count': product_quantity
        }
        self.item['assets'] = {
            'main_image': main_image,
            'set_images': all_images,  # все боковые картинки товара, включая основное изображение
            'view360': view_360_images,
            'video': video_url
        }
        self.item['metadata'] = product_metadata
        self.item['variants'] = len(product_data.get('properNomenclaturesOrder', 1))

        yield self.item
