import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from keep_alive import keep_alive

# BOT VE SAHİP AYARLARI
TOKEN = os.getenv("TOKEN")
BOT_OWNER_ID = 1547400739775844356  # Kendi Discord ID'nizi buraya yazın

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# DATA DOSYALARI
DATA_FILE = "bot_settings.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"authorized": [], "log_channel_id": None}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

db = load_data()

def is_authorized(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID or user_id in db.get("authorized", [])

async def send_log(guild: discord.Guild, embed: discord.Embed):
    log_id = db.get("log_channel_id")
    if log_id:
        channel = guild.get_channel(log_id)
        if channel:
            await channel.send(embed=embed)

@bot.event
async def on_ready():
    # Slash komutlarını Discord'a senkronize eder
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} adet Slash Komutu senkronize edildi.")
    except Exception as e:
        print(f"Slash komut senkronizasyon hatası: {e}")
    print(f"🤖 {bot.user} olarak giriş yapıldı! Koruma sistemleri aktif.")

# ================= SLASH KOMUTLARI =================

@bot.tree.command(name="yetkili-ekle", description="Korumalardan muaf tutulacak yetkili ekler (Sadece Bot Sahibi).")
@app_commands.describe(kullanici="Yetki verilecek kullanıcı")
async def yetkili_ekle(interaction: discord.Interaction, kullanici: discord.Member):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ Bu komutu sadece **Bot Sahibi** kullanabilir!", ephemeral=True)
        return

    if kullanici.id not in db["authorized"]:
        db["authorized"].append(kullanici.id)
        save_data(db)
        await interaction.response.send_message(f"✅ {kullanici.mention} başarıyla güvenli listeye eklendi. Korumalardan etkilenmeyecek.")
    else:
        await interaction.response.send_message("⚠️ Bu kullanıcı zaten yetkili listesinde.", ephemeral=True)

@bot.tree.command(name="yetkili-sil", description="Kullanıcının koruma muafiyetini kaldırır (Sadece Bot Sahibi).")
@app_commands.describe(kullanici="Yetkisi alınacak kullanıcı")
async def yetkili_sil(interaction: discord.Interaction, kullanici: discord.Member):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ Bu komutu sadece **Bot Sahibi** kullanabilir!", ephemeral=True)
        return

    if kullanici.id in db["authorized"]:
        db["authorized"].remove(kullanici.id)
        save_data(db)
        await interaction.response.send_message(f"🚫 {kullanici.mention} güvenli listeden çıkarıldı.")
    else:
        await interaction.response.send_message("⚠️ Bu kullanıcı yetkili listesinde bulunamadı.", ephemeral=True)

@bot.tree.command(name="yetkili-liste", description="Korumalardan muaf tutulan kişileri listeler.")
async def yetkili_liste(interaction: discord.Interaction):
    authorized_ids = db.get("authorized", [])
    
    embed = discord.Embed(title="🛡️ Güvenli / Yetkili Kullanıcılar", color=discord.Color.blue())
    embed.add_field(name="Crown Owner (Bot Sahibi)", value=f"<@{BOT_OWNER_ID}>", inline=False)
    
    if authorized_ids:
        users_str = "\n".join([f"• <@{uid}>" for uid in authorized_ids])
        embed.add_field(name="Eklenen Yetkililer", value=users_str, inline=False)
    else:
        embed.add_field(name="Eklenen Yetkililer", value="Hiç yetkili eklenmemiş.", inline=False)
        
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="log-ayarla", description="Koruma loglarının gönderileceği kanalı ayarlar (Sadece Bot Sahibi).")
@app_commands.describe(kanal="Log gönderilecek kanal")
async def log_ayarla(interaction: discord.Interaction, kanal: discord.TextChannel):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ Bu komutu sadece **Bot Sahibi** kullanabilir!", ephemeral=True)
        return

    db["log_channel_id"] = kanal.id
    save_data(db)
    await interaction.response.send_message(f"✅ Koruma Log kanalı {kanal.mention} olarak ayarlandı.")

# ================= KORUMALAR VE OTOMATİK ESKİYE DÖNDÜRME =================

# 1. KANAL SİLME & EKLEME KORUMASI
@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        if not is_authorized(entry.user.id):
            # Anında aynı kanalı geri oluştur
            new_chan = await channel.guild.create_text_channel(
                name=channel.name, category=channel.category, position=channel.position, topic=channel.topic
            )
            await channel.guild.ban(entry.user, reason="GÜVENLİK: Yetkisiz kanal silme!")
            
            embed = discord.Embed(title="🚨 Yetkisiz Kanal Silindi!", color=discord.Color.red())
            embed.add_field(name="Silen Kullanıcı", value=f"{entry.user.mention} ({entry.user.id})")
            embed.add_field(name="Silinen Kanal", value=channel.name)
            embed.add_field(name="İşlem", value="Kanal tekrar oluşturuldu ve kullanıcı yasaklandı.")
            await send_log(channel.guild, embed)

@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
        if not is_authorized(entry.user.id):
            await channel.delete()
            await channel.guild.ban(entry.user, reason="GÜVENLİK: Yetkisiz kanal oluşturma!")

# 2. ROL SİLME / EKLEME / DEĞİŞTİRME KORUMASI
@bot.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        if not is_authorized(entry.user.id):
            await role.guild.create_role(name=role.name, permissions=role.permissions, color=role.color)
            await role.guild.ban(entry.user, reason="GÜVENLİK: Yetkisiz rol silme!")

# 3. SUNUCU AYARLARI KORUMASI (Adı, URL, Afiş, Güvenlik Seviyesi vb.)
@bot.event
async def on_guild_update(before, after):
    async for entry in after.audit_logs(limit=1, action=discord.AuditLogAction.guild_update):
        if not is_authorized(entry.user.id):
            # Değiştirilen ne varsa 0.1ms mantığıyla anında eski haline döndür
            await after.edit(
                name=before.name,
                icon=before.icon,
                banner=before.banner,
                description=before.description,
                verification_level=before.verification_level,
                vanity_code=before.vanity_url_code if hasattr(before, 'vanity_url_code') else None
            )
            await after.ban(entry.user, reason="GÜVENLİK: Yetkisiz sunucu ayarı değiştirme!")
            
            embed = discord.Embed(title="🚨 Yetkisiz Sunucu Düzenlemesi!", color=discord.Color.red())
            embed.add_field(name="Yapan Kullanıcı", value=f"{entry.user.mention}")
            embed.add_field(name="İşlem", value="Sunucu ayarları eski haline getirildi ve kullanıcı banlandı.")
            await send_log(after, embed)

# 4. LİNK VE REKLAM ENGELİ
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    
    links = ["http://", "https://", "discord.gg/", ".com", ".net", ".org", "discord.com/invite"]
    if any(link in message.content.lower() for link in links):
        if not is_authorized(message.author.id):
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention}, burada link paylaşamazsın!", delete_after=3)
            return

    await bot.process_commands(message)

# Flask sunucusunu ve botu çalıştır
keep_alive()
bot.run(TOKEN)