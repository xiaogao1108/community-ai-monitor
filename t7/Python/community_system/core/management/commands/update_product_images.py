from django.core.management.base import BaseCommand
from core.models import Product

class Command(BaseCommand):
    help = '更新商品图片URL，指向front/public/imgs/products/目录'

    def handle(self, *args, **options):
        # 商品名称到图片文件的映射
        product_image_mapping = {
            '洗衣液': 'laundry.jpg',
            '食用油': 'oil.jpg', 
            '大米': 'rice.jpg',
            '电影票': 'movie_ticket.jpg',
            '保温杯': 'thermos.jpg',
            '购物卡': 'gift_card.jpg'
        }
        
        updated_count = 0
        
        for product in Product.objects.all():
            if product.product_name in product_image_mapping:
                old_url = product.image_url
                product.image_url = f'/static/imgs/products/{product_image_mapping[product.product_name]}'
                product.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ 更新商品 "{product.product_name}": {old_url} -> {product.image_url}'
                    )
                )
                updated_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  跳过商品 "{product.product_name}": 未找到对应的图片文件'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 更新完成！共更新了 {updated_count} 个商品的图片URL')
        )
