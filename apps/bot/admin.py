# apps/bot/admin.py (YANGI VERSIYA)

from django.contrib import admin
from .models import User, Location, SubscribeChannel, Broadcast, BroadcastRecipient

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # 'bot' maydoniga oid barcha murojaatlar olib tashlandi
    list_display = ('id', 'telegram_id', 'full_name', 'is_admin', 'is_blocked', 'created_at')
    list_filter = ('is_admin', 'is_blocked', 'left', 'stock_language') # 'bot' olib tashlandi
    search_fields = ('telegram_id', 'first_name', 'last_name', 'username')
    readonly_fields = ('telegram_id', 'created_at', 'updated_at') # 'bot' olib tashlandi
    list_per_page = 20

@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    # 'bot' maydoniga oid barcha murojaatlar olib tashlandi
    list_display = ('id', 'status', 'scheduled_time', 'created_at')
    list_filter = ('status',) # 'bot' olib tashlandi
    # ... boshqa sozlamalar ...

# --- Boshqa admin klasslari (o'zgarishsiz qolishi mumkin) ---

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('user', 'latitude', 'longitude', 'created_at')
    search_fields = ('user__telegram_id',)

@admin.register(SubscribeChannel)
class SubscribeChannelAdmin(admin.ModelAdmin):
    list_display = ('channel_username', 'channel_id', 'active', 'private')
    list_filter = ('active', 'private')
    search_fields = ('channel_username', 'channel_id')

@admin.register(BroadcastRecipient)
class BroadcastRecipientAdmin(admin.ModelAdmin):
    list_display = ('broadcast', 'user', 'status', 'sent_at')
    list_filter = ('status',)
    search_fields = ('user__telegram_id',)