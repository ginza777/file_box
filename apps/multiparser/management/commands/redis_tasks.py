from django.core.management.base import BaseCommand
from django.conf import settings
from redis import Redis
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Redis bilan bog\'liq vazifalarni bajarish'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Redis keshini tozalash'
        )
        parser.add_argument(
            '--info',
            action='store_true',
            help='Redis serveri haqida ma\'lumot'
        )

    def handle(self, *args, **options):
        try:
            redis_client = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                socket_connect_timeout=5,
                decode_responses=True
            )

            # Redis ulanishini tekshirish
            redis_client.ping()

            if options['flush']:
                # Barcha keshlarni tozalash
                redis_client.flushall()
                self.stdout.write(
                    self.style.SUCCESS('Redis keshi muvaffaqiyatli tozalandi!')
                )

            if options['info']:
                # Redis serveri haqida ma'lumot
                info = redis_client.info()
                self.stdout.write(self.style.SUCCESS('\nRedis Server Ma\'lumotlari:'))
                self.stdout.write(f"Redis versiyasi: {info.get('redis_version')}")
                self.stdout.write(f"Xotira ishlatilishi: {info.get('used_memory_human')}")
                self.stdout.write(f"Ulangan mijozlar: {info.get('connected_clients')}")
                self.stdout.write(f"Keylar soni: {info.get('db0', {}).get('keys', 0)}")

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'Redis bilan bog\'lanishda xatolik: {e}')
            )
