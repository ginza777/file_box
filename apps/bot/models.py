# models.py (Refactored and Optimized Version)
import asyncio
import logging
import requests

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from telegram import Bot as TelegramBot
from telegram.error import TelegramError

# Katta loyihalarda print o'rniga logging dan foydalanish tavsiya etiladi
logger = logging.getLogger(__name__)

# --- Constants ---
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


# --- Telegram API Utility Functions ---
# Izoh: Katta loyihalarda bu funksiyalarni alohida services.py fayliga ko'chirish maqsadga muvofiq.

def get_bot_details_from_telegram(token: str) -> tuple[str, str]:
    """
    Fetches bot's first_name and username from the Telegram API using its token.

    Args:
        token: The Telegram bot token.

    Returns:
        A tuple containing the bot's first_name and username.

    Raises:
        ValidationError: If the API request fails or the token is invalid.
    """
    url = TELEGRAM_API_URL.format(token=token, method="getMe")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # HTTP xatolar uchun xatolikni ko'taradi (4xx, 5xx)
        data = response.json()
        if data.get("ok"):
            result = data["result"]
            return result["first_name"], result["username"]
        else:
            raise ValidationError(_("Failed to get bot information. API response not OK."))
    except requests.RequestException as e:
        logger.error(f"Telegram API request failed: {e}")
        raise ValidationError(_("Could not connect to Telegram API."))
    except (KeyError, TypeError) as e:
        logger.error(f"Unexpected API response structure: {e}")
        raise ValidationError(_("Invalid response received from Telegram API."))


def register_bot_webhook(bot_token: str, webhook_base_url: str) -> str:
    """
    Sets the bot's webhook on Telegram.

    Args:
        bot_token: The Telegram bot token.
        webhook_base_url: The base URL for the webhook (e.g., from settings).

    Returns:
        The full webhook URL that was set.

    Raises:
        ValidationError: If the webhook registration fails.
    """
    full_webhook_url = f"{webhook_base_url}/api/bot/{bot_token}"
    url = TELEGRAM_API_URL.format(token=bot_token, method=f"setWebhook?url={full_webhook_url}")
    try:
        response = requests.post(url, timeout=10)
        response.raise_for_status()
        if not response.json().get("ok"):
            raise ValidationError(
                _("Telegram API rejected the webhook setup: {description}").format(
                    description=response.json().get("description", "Unknown error")
                )
            )
        return full_webhook_url
    except requests.RequestException as e:
        logger.error(f"Failed to set webhook for bot {bot_token[:10]}...: {e}")
        raise ValidationError(_("Failed to register webhook with Telegram API."))


async def check_bot_is_admin_in_channel(channel_id: str, telegram_token: str) -> bool:
    """
    Asynchronously checks if the bot is an administrator in a given channel.

    Args:
        channel_id: The ID of the Telegram channel.
        telegram_token: The bot's token.

    Returns:
        True if the bot is an admin, False otherwise.
    """
    logger.info(f"Checking admin status for bot in channel {channel_id}")
    try:
        bot = TelegramBot(token=telegram_token)
        bot_info = await bot.get_me()
        print(bot_info)
        admins = await bot.get_chat_administrators(chat_id=channel_id)
        print("Admins in channel:", admins)
        return any(admin.user.id == bot_info.id for admin in admins)
    except TelegramError as e:
        logger.error(f"Telegram error while checking admin status in {channel_id}: {e}")
        return False


# --- Custom Managers ---

class GetOrNoneManager(models.Manager):
    """
    Custom manager with a `get_or_none` method that returns None
    if the object does not exist, instead of raising an exception.
    """

    async def get_or_none(self, **kwargs):
        """Asynchronously fetches an object or returns None if it doesn't exist."""
        try:
            return await sync_to_async(self.get)(**kwargs)
        except ObjectDoesNotExist:
            return None




class SubscribeChannel(models.Model):
    """
    Represents a Telegram channel that users must subscribe to.
    """
    channel_username = models.CharField(max_length=100, unique=True, null=True, blank=True)
    channel_link = models.URLField(max_length=255, blank=True, null=True)
    channel_id = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)
    private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Subscription Channel")
        verbose_name_plural = _("Subscription Channels")
        ordering = ["-created_at"]

    def __str__(self):
        return self.channel_username or self.channel_id

    def clean(self):
        """
        Custom validation for the model.
        """
        if self.private and not self.channel_link:
            raise ValidationError(_("A private channel must have an invitation link."))
        if not self.private and not self.channel_username:
            raise ValidationError(_("A public channel must have a username."))
        if settings.BOT_TOKEN and self.channel_id:
            try:
                # Run the async function from this sync method using asyncio.run()
                is_admin = asyncio.run(
                    check_bot_is_admin_in_channel(self.channel_id, settings.BOT_TOKEN)
                )

                # Corrected Logic: Raise error if the bot is NOT an admin.
                if not is_admin:
                    raise ValidationError(
                        _("The bot is not an administrator in the specified channel. Please add the bot as an admin and try again.")
                    )
            except Exception as e:
                # Catch potential network or API errors
                raise ValidationError(f"Failed to verify bot admin status: {e}")

    def save(self, *args, **kwargs):
        """
        Strips prefixes from the username before saving.
        """
        if self.channel_username:
            self.channel_username = self.channel_username.removeprefix("https://t.me/").removeprefix("@")
        super().save(*args, **kwargs)

    @property
    def get_channel_link(self) -> str | None:
        """Returns the full, clickable link for a public channel."""
        if self.private:
            return self.channel_link
        return f"https://t.me/{self.channel_username}"


class Language(models.TextChoices):
    UZ = 'uz', _('Uzbek')
    RU = 'ru', _('Russian')
    EN = 'en', _('English')
    TR = 'tr', _('Turkish')


class User(models.Model):
    """
    Represents a Telegram user interacting with one of the bots.
    """
    telegram_id = models.BigIntegerField()
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    username = models.CharField(max_length=100, blank=True, null=True)
    last_active = models.DateTimeField(auto_now=True)
    is_admin = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    stock_language = models.CharField(max_length=10, choices=Language.choices, default=Language.UZ)
    selected_language = models.CharField(max_length=10, choices=Language.choices, null=True, blank=True)
    deeplink = models.TextField(blank=True, null=True)
    left=models.BooleanField(default=False)

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return f"{self.full_name} ({self.telegram_id})"

    @property
    def full_name(self) -> str:
        """Returns the user's full name."""
        return f"{self.first_name or ''} {self.last_name or ''}".strip()


class Location(models.Model):
    """
    Stores location data sent by a user.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="locations")
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = GetOrNoneManager()

    class Meta:
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Location for {self.user} at {self.created_at.strftime('(%H:%M, %d %B %Y)')}"


from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class Broadcast(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        PENDING = 'pending', _('Pending')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
    from_chat_id = models.BigIntegerField()
    message_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_time = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    def __str__(self):
        return f"Forward {self.message_id} from {self.from_chat_id}"

class BroadcastRecipient(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        SENT = 'sent', _('Sent')
        FAILED = 'failed', _('Failed')

    broadcast = models.ForeignKey(Broadcast, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name="broadcast_messages")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('broadcast', 'user')