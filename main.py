import tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
import logging
import sqlite3
import asyncio
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.handler import CancelHandler
from aiogram.types import ParseMode
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils.exceptions import TelegramAPIError, BotBlocked, UserDeactivated, ChatNotFound, NetworkError, RetryAfter
from aiogram import Bot, executor
from aiogram import Dispatcher
from aiogram.types import Message
import shutil
import os
import csv
import io
from aiogram import Bot, executor
from aiogram import Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.middlewares.environment import EnvironmentMiddleware
from aiogram.utils.executor import start_webhook


bot = Bot(token="6945981247:AAHuPO0UgNv2z0j3HyW5EpDzFQBurLBFw-w")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

CHANNEL_ID = -1002079102928

WEBHOOK_HOST = 'https://dangerous-seahorse-alonejustmyself-f0eebf16.koyeb.app'
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

@dp.message_handler(commands=['start'])
async def handler_start(message: types.Message):
    quote_text = "halooo, gimana nih kabarnya ❔ pasti kamu mau kirim menfess ya. <blockquote>Sebelum kirim menfess jangan lupa perhatikan menfes kalian ya apakah sudah sesuai dengan ht dan tidak melanggar rulesnya</blockquote> untuk mengetahui apakah ht kalian sesuai silahkan klik 📂 /hashtag"
    await message.reply(text=quote_text, parse_mode=ParseMode.HTML)

@dp.message_handler(commands=['hashtag'])
async def send_all_hashtags(message: types.Message):
    response = (
        "Berikut adalah penjelasan untuk semua hashtag di channel kami:\n\n"
        "#ELF = untuk bertanya kepada dreamies dan temukan apa yang kalian cari sebagai jawaban di dunia roleplayer ini.\n\n"
        "#FAIRY =  untuk menceritakan pengalaman kalian kepada dreamies tentang dunia roleplayer ini.\n\n"
        "#MERMAID = untuk mencari seseorang yang telah lama di cari seperti teman, pasangan, mutualan channel, akun, dan circle atau paguy..\n\n"
    )
    await message.reply(response)
    await message.answer_sticker('CAACAgUAAxkBAAEL_C9mKf2y-q1CD2_wOxneHKQd5ZUupQACdwwAAuajUFXgkBo0l99wcTQE')

boti = Bot(token="7026729109:AAGsiEhZvi-sETZjv2u9Q1R2rF08SXueot4")

forwarded_message_mapping = {}
in_progress = {}
last_message_time = {}

bot_status = {'status': 'on', 'message': None}

logging.basicConfig(level=logging.INFO)
# Koneksi ke database SQLite
conn = sqlite3.connect('chat_links.db')
c = conn.cursor()

# Buat tabel jika belum ada
c.execute('''CREATE TABLE IF NOT EXISTS chat_links
             (chat_id TEXT PRIMARY KEY, link TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS banned_users
             (user_id INTEGER PRIMARY KEY)''')
c.execute('''CREATE TABLE IF NOT EXISTS badwords
             (word TEXT PRIMARY KEY)''')
c.execute('''CREATE TABLE IF NOT EXISTS filterwords
             (word TEXT PRIMARY KEY)''')
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY,
              filterword_count INTEGER DEFAULT 0,
              message_count INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS hashtags (
             hashtag TEXT PRIMARY KEY)''')

conn.commit()

# Fungsi untuk mendapatkan daftar chat ID dan tautan dari database
def get_chat_links():
    c.execute("SELECT * FROM chat_links")
    return dict(c.fetchall())

def get_all_users():
    c.execute("SELECT user_id FROM users")
    return [row[0] for row in c.fetchall()]

async def is_user_banned(user_id):
    try:
        c.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,))
        result = c.fetchone()
        return result is not None
    except Exception as e:
        logging.error(f"Error checking banned status for user {user_id}: {str(e)}")
        return False

async def increment_user_message_count(user_id):
    conn = sqlite3.connect('chat_links.db')
    c = conn.cursor()
    c.execute("UPDATE users SET message_count = message_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

async def check_membership(user_id, chat_id):
    try:
        logging.info(f"Checking membership for user {user_id} in chat {chat_id}")
        member = await boti.get_chat_member(chat_id, user_id)
        logging.info(f"Membership status: {member.status}")
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Error checking membership for chat {chat_id}: {str(e)}")
        return False

async def add_user_to_banned(user_id):
    try:
        c.execute("INSERT INTO banned_users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error adding user {user_id} to banned users: {str(e)}")
        return False

async def add_badword(word):
    try:
        c.execute("INSERT INTO badwords (word) VALUES (?)", (word,))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error adding badword {word} to database: {str(e)}")
        return False

async def add_filterwords(words):
    try:
        # Split kata-kata berdasarkan koma
        word_list = words.split(',')
        added_words = []
        ignored_words = []

        # Untuk setiap kata dalam daftar kata
        for word in word_list:
            word = word.strip()
            # Periksa apakah kata sudah ada di database
            c.execute("SELECT COUNT(*) FROM filterwords WHERE word=?", (word,))
            result = c.fetchone()
            if result[0] == 0:
                # Jika kata belum ada, masukkan ke database
                c.execute("INSERT INTO filterwords (word) VALUES (?)", (word,))
                added_words.append(word)
            else:
                # Jika kata sudah ada, tambahkan ke daftar yang diabaikan
                ignored_words.append(word)

        conn.commit()

        return added_words, ignored_words
    except Exception as e:
        logging.error(f"Error adding filterwords to database: {str(e)}")
        return [], []


async def remove_filterword(word):
    try:
        c.execute("DELETE FROM filterwords WHERE word = ?", (word,))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error removing filterword {word} from database: {str(e)}")
        return False

async def get_filterwords():
    try:
        c.execute("SELECT word FROM filterwords")
        filterwords = [row[0] for row in c.fetchall()]
        return filterwords
    except Exception as e:
        logging.error(f"Error getting filterwords from database: {str(e)}")
        return []

async def contains_badword(text):
    if not text:
        return False

    try:
        c.execute("SELECT word FROM badwords")
        badwords = [row[0] for row in c.fetchall()]
        return any(badword in text for badword in badwords)
    except Exception as e:
        logging.error(f"Error checking badword in message: {str(e)}")
        return False

async def contains_filterword(text):
    if not text:
        return False

    try:
        c.execute("SELECT word FROM filterwords")
        filterwords = [row[0] for row in c.fetchall()]
        return any(filterword in text for filterword in filterwords)
    except Exception as e:
        logging.error(f"Error checking filterword in message: {str(e)}")
        return False

async def save_user(user_id):
    try:
        c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error saving user {user_id} to database: {str(e)}")
        return False

async def increment_filterword_count(user_id):
    try:
        c.execute("UPDATE users SET filterword_count = filterword_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        c.execute("SELECT filterword_count FROM users WHERE user_id = ?", (user_id,))
        count = c.fetchone()[0]
        return count
    except Exception as e:
        logging.error(f"Error incrementing filterword count for user {user_id}: {str(e)}")
        return 0

async def send_message_with_retry(user_id, message, retries=5):
    for attempt in range(retries):
        try:
            await bot.send_message(user_id, message)
            logging.info(f"Pesan berhasil dikirim ke pengguna {user_id}")
            return True
        except BotBlocked:
            logging.warning(f"Bot diblokir oleh pengguna {user_id}")
            return False
        except UserDeactivated:
            logging.warning(f"Pengguna {user_id} telah menonaktifkan akun mereka")
            return False
        except ChatNotFound:
            logging.warning(f"Chat dengan pengguna {user_id} tidak ditemukan")
            return False
        except RetryAfter as e:
            logging.warning(f"Rate limit hit: tidur selama {e.timeout} detik sebelum mengirim ulang ke pengguna {user_id}")
            await asyncio.sleep(e.timeout)
        except NetworkError:
            logging.warning(f"Network error, percobaan ulang ke pengguna {user_id} (attempt {attempt + 1} dari {retries})")
            await asyncio.sleep(5)  # Tunggu beberapa detik sebelum mencoba lagi
        except TelegramAPIError as e:
            logging.error(f"Error broadcasting message to user {user_id}: {str(e)}")
            await asyncio.sleep(5)  # Tunggu beberapa detik sebelum mencoba lagi

    logging.error(f"Gagal mengirim pesan ke pengguna {user_id} setelah {retries} kali percobaan")
    return False

async def rate_limit_check(user_id, message, rate_limit=60):
    current_time = message.date
    last_time = last_message_time.get(user_id, None)
    if last_time and (current_time - last_time).seconds < rate_limit:
        await message.reply(f"Harap tunggu {rate_limit} detik sebelum mengirim pesan lagi.")
        return False
    last_message_time[user_id] = current_time
    return True

def add_hashtag(hashtag):
    try:
        c.execute('INSERT INTO hashtags (hashtag) VALUES (?)', (hashtag,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        logging.error(f"Error adding hashtag {hashtag} to database: {str(e)}")
        return False

def delete_hashtag(hashtag):
    try:
        c.execute('DELETE FROM hashtags WHERE hashtag = ?', (hashtag,))
        success = c.rowcount > 0
        conn.commit()
        return success
    except Exception as e:
        logging.error(f"Error deleting hashtag {hashtag} from database: {str(e)}")
        return False

def get_hashtags():
    try:
        c.execute('SELECT hashtag FROM hashtags')
        hashtags = [tag[0] for tag in c.fetchall()]
        return hashtags
    except Exception as e:
        logging.error(f"Error fetching hashtags from database: {str(e)}")
        return []


async def reset_filterword_count(user_id):
    try:
        c.execute("UPDATE users SET filterword_count = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception as e:
        logging.error(f"Error resetting filterword count for user {user_id}: {str(e)}")

def check_message_conditions(message, hashtags):
    message_text = message.text or message.caption or ""
    conditions_met = any(hashtag in message_text for hashtag in hashtags)
    return conditions_met, message_text

def fetch_table_contents(table):
    conn = sqlite3.connect('chat_links.db')
    c = conn.cursor()
    c.execute(f"SELECT * FROM {table}")
    contents = c.fetchall()
    c.close()
    conn.close()
    return contents

# Function to create a CSV file
def create_csv_file_with_message_count(contents, table):
    temp_dir = tempfile.gettempdir()
    csv_file_path = os.path.join(temp_dir, f"{table}.csv")
    conn = sqlite3.connect('chat_links.db')
    c = conn.cursor()
    with open(csv_file_path, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([desc[0] for desc in c.execute(f"PRAGMA table_info({table})").fetchall()])  # Write column names
        for row in contents:
            writer.writerow(row)
    conn.close()
    return csv_file_path


class CombinedMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        if message.chat.type != 'private':
            return

        if bot_status['status'] == 'off':
            if bot_status['message']:
                await message.reply(bot_status['message'])
            raise CancelHandler()

        user_id = message.from_user.id

        await save_user(user_id)

        if await is_user_banned(user_id):
            await message.reply("KAMU TELAH DI BANNED, silahkan mengajukan permohonan unban ke admin jika diperlukan.")
            raise CancelHandler()

        chat_links = get_chat_links()
        non_member_chats = []

        for chat_id in chat_links:
            if not await check_membership(user_id, chat_id):
                non_member_chats.append(chat_id)

        if non_member_chats:
            links = [f"[Group/Channel]({chat_links[chat_id]})" for chat_id in non_member_chats]
            await message.reply(
                "Silahkan masuk terlebih dahulu ke sini sebelum menggunakan botnya : " + ", ".join(links),
                parse_mode=ParseMode.MARKDOWN
            )
            raise CancelHandler()

        if await contains_badword(message.text):
            await add_user_to_banned(user_id)
            await message.reply("BANNED‼️\nKamu telah diban karena mengirimkan BADWORD.")
            raise CancelHandler()

        if await contains_filterword(message.text):
            count = await increment_filterword_count(user_id)
            if count >= 3:
                await add_user_to_banned(user_id)
                await message.reply("BANNED‼️‼️\nKAMU TELAH DI BAN KARNA MENGIRIM KATA YANG DI LARANG 3 KALI.")
                await reset_filterword_count(user_id)
                raise CancelHandler()
            else:
                remaining_warnings = 3 - count
                await message.reply(f"PERINGATAN: Pesanmu mengandung kata-kata yang dilarang. Jika kamu masih mengirim kata terlarang sebanyak {remaining_warnings} kali lagi, kamu akan di-ban!")



@dp.message_handler(commands=['onbot'])
async def cmd_onbot(message: types.Message):
    bot_status['status'] = 'on'
    bot_status['message'] = None
    await message.reply("Bot telah dihidupkan kembali.")
    
dp.middleware.setup(LoggingMiddleware())
dp.middleware.setup(CombinedMiddleware())

@dp.message_handler(commands=['offbot'])
async def cmd_offbot(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply("Gunakan perintah ini dengan mereply pesan yang ingin dijadikan respon ketika bot mati.")
        return

    bot_status['status'] = 'off'
    bot_status['message'] = message.reply_to_message.text.strip()
    await message.reply("Bot telah dimatikan. Pesan yang akan dikirim ketika bot mati telah disimpan.")


@dp.message_handler(commands=['setlink'])
async def set_link(message: types.Message):
    try:
        command, chat_id, link = message.text.split()

        # Cek keberadaan grup/channel dan status admin bot
        try:
            chat = await boti.get_chat(chat_id)
            bot_member = await boti.get_chat_member(chat_id, bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                await message.reply("Bot tidak memiliki akses admin di grup atau channel ini.")
                return
        except Exception as e:
            await message.reply(f"Tidak dapat mengakses grup/channel: {str(e)}")
            return

        c.execute("INSERT OR REPLACE INTO chat_links (chat_id, link) VALUES (?, ?)", (chat_id, link))
        conn.commit()
        await message.reply("Tautan berhasil diperbarui!")
    except ValueError:
        await message.reply("Format perintah salah. Gunakan /setlink <chat_id> <link>")

# Perintah untuk menampilkan semua tautan yang tersimpan di database
@dp.message_handler(commands=['listlink'])
async def list_links(message: types.Message):
    chat_links = get_chat_links()
    if chat_links:
        links_message = "\n".join([f"{chat_id}: {link}" for chat_id, link in chat_links.items()])
        await message.reply(f"Tautan yang tersimpan:\n{links_message}", parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply("Belum ada tautan yang tersimpan.")

# Perintah untuk menghapus tautan dari database
@dp.message_handler(commands=['removelink'])
async def remove_link(message: types.Message):
    try:
        command, chat_id = message.text.split()
        c.execute("DELETE FROM chat_links WHERE chat_id=?", (chat_id,))
        conn.commit()
        await message.reply("Tautan berhasil dihapus!")
    except ValueError:
        await message.reply("Format perintah salah. Gunakan /removelink <chat_id>")

# Fungsi untuk menambah badword
@dp.message_handler(commands=['addbadword'])
async def add_badword_handler(message: Message):
    word = message.get_args()
    if not word:
        await message.reply("Gunakan /addbadword [kata] untuk menambah badword.")
        return

    if await add_badword(word):
        await message.reply(f"Kata '{word}' telah ditambahkan ke daftar badwords.")
    else:
        await message.reply(f"Gagal menambahkan kata '{word}' ke daftar badwords.")

# Fungsi untuk menghapus badword
@dp.message_handler(commands=['removebadword'])
async def remove_badword_handler(message: Message):
    word = message.get_args()
    if not word:
        await message.reply("Gunakan /removebadword [kata] untuk menghapus badword.")
        return

    try:
        c.execute("DELETE FROM badwords WHERE word=?", (word,))
        conn.commit()
        await message.reply(f"Kata '{word}' telah dihapus dari daftar badwords.")
    except Exception as e:
        logging.error(f"Error removing badword {word} from database: {str(e)}")
        await message.reply(f"Gagal menghapus kata '{word}' dari daftar badwords.")

# Fungsi untuk melihat daftar badwords
@dp.message_handler(commands=['listbadwords'])
async def list_badwords_handler(message: Message):
    try:
        c.execute("SELECT word FROM badwords")
        badwords = c.fetchall()
        if badwords:
            await message.reply("Daftar badwords:\n" + "\n".join([bw[0] for bw in badwords]))
        else:
            await message.reply("Tidak ada badword yang terdaftar.")
    except Exception as e:
        logging.error(f"Error fetching badwords from database: {str(e)}")
        await message.reply("Gagal mengambil daftar badwords.")

@dp.message_handler(commands=['addhashtag'])
async def cmd_add_hashtag(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply("Gunakan perintah ini dengan mereply pesan yang berisi hashtag yang ingin ditambahkan.")
        return

    hashtags = message.reply_to_message.text.split(',')
    responses = []
    for tag in hashtags:
        tag = tag.strip()
        if add_hashtag(tag):
            responses.append(f"Hashtag '{tag}' berhasil ditambahkan.")
        else:
            responses.append(f"Hashtag '{tag}' sudah ada atau terjadi kesalahan.")
    await message.reply('\n'.join(responses))

@dp.message_handler(commands=['removehashtag'])
async def cmd_remove_hashtag(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply("Gunakan perintah ini dengan mereply pesan yang berisi hashtag yang ingin dihapus.")
        return

    hashtags = message.reply_to_message.text.split(',')
    responses = []
    for tag in hashtags:
        tag = tag.strip()
        if delete_hashtag(tag):
            responses.append(f"Hashtag '{tag}' berhasil dihapus.")
        else:
            responses.append(f"Hashtag '{tag}' tidak ditemukan atau terjadi kesalahan.")
    await message.reply('\n'.join(responses))

@dp.message_handler(commands=['listhashtags'])
async def cmd_list_hashtags(message: types.Message):
    hashtags = get_hashtags()
    if hashtags:
        await message.reply("Daftar hashtag:\n" + '\n'.join(hashtags))
    else:
        await message.reply("Tidak ada hashtag yang ditemukan.")

# Fungsi untuk menambah banned user
@dp.message_handler(commands=['banuser'])
async def ban_user_handler(message: Message):
    try:
        user_id = int(message.get_args())
        if await add_user_to_banned(user_id):
            await message.reply(f"User dengan ID {user_id} telah ditambahkan ke daftar banned.")
        else:
            await message.reply(f"Gagal menambahkan user dengan ID {user_id} ke daftar banned.")
    except ValueError:
        await message.reply("Gunakan /banuser [user_id] untuk ban user.")
    except Exception as e:
        logging.error(f"Error banning user: {str(e)}")
        await message.reply("Gagal menambahkan user ke daftar banned.")

# Fungsi untuk menghapus banned user
@dp.message_handler(commands=['unbanuser'])
async def unban_user_handler(message: Message):
    try:
        user_id = int(message.get_args())
        try:
            c.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))
            conn.commit()
            await message.reply(f"User dengan ID {user_id} telah dihapus dari daftar banned.")
        except Exception as e:
            logging.error(f"Error removing banned user {user_id} from database: {str(e)}")
            await message.reply(f"Gagal menghapus user dengan ID {user_id} dari daftar banned.")
    except ValueError:
        await message.reply("Gunakan /unbanuser [user_id] untuk unban user.")

# Fungsi untuk melihat daftar banned users
@dp.message_handler(commands=['listbannedusers'])
async def list_banned_users_handler(message: Message):
    try:
        c.execute("SELECT user_id FROM banned_users")
        banned_users = c.fetchall()
        if banned_users:
            await message.reply("Daftar banned users:\n" + "\n".join([str(bu[0]) for bu in banned_users]))
        else:
            await message.reply("Tidak ada user yang ter-banned.")
    except Exception as e:
        logging.error(f"Error fetching banned users from database: {str(e)}")
        await message.reply("Gagal mengambil daftar banned users.")

@dp.message_handler(commands=['addfilterword'])
async def cmd_add_filterword(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply("Gunakan perintah ini dengan mereply pesan yang berisi kata yang ingin ditambahkan sebagai filterword.")
        return

    words = message.reply_to_message.text.strip()
    added, ignored = await add_filterwords(words)

    if added:
        added_str = ", ".join(added)
        await message.reply(f"Kata '{added_str}' berhasil ditambahkan ke filterwords.")
    if ignored:
        ignored_str = ", ".join(ignored)
        await message.reply(f"Kata '{ignored_str}' sudah ada di filterwords dan tidak ditambahkan.")

# Tambah command handler untuk menghapus filterword
@dp.message_handler(commands=['removefilterword'])
async def cmd_remove_filterword(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply("Gunakan perintah ini dengan mereply pesan yang berisi kata yang ingin dihapus dari filterword.")
        return

    word = message.reply_to_message.text.strip()
    if await remove_filterword(word):
        await message.reply(f"Kata '{word}' berhasil dihapus dari filterwords.")
    else:
        await message.reply(f"Gagal menghapus kata '{word}' dari filterwords.")

@dp.message_handler(commands=['listfilterwords'])
async def cmd_list_filterwords(message: types.Message):
    filterwords = await get_filterwords()
    if filterwords:
        await message.reply("Daftar filterwords:\n" + "\n".join(filterwords))
    else:
        await message.reply("Tidak ada filterwords yang terdaftar.")

@dp.message_handler(commands=['broadcast'])
async def cmd_broadcast(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply("Gunakan perintah ini dengan mereply pesan yang ingin dibroadcast.")
        return

    broadcast_message = message.reply_to_message.text
    users = get_all_users()

    if not users:
        await message.reply("Tidak ada pengguna yang ditemukan untuk menerima broadcast.")
        return

    failed_users = 0
    total_users = len(users)

    for user_id in users:
        success = await send_message_with_retry(user_id, broadcast_message)
        if not success:
            failed_users += 1

    success_users = total_users - failed_users
    await message.reply(f"Pesan broadcast telah dikirim ke {success_users} pengguna. Gagal mengirim ke {failed_users} pengguna.")


# Tambah command handler untuk backup database
@dp.message_handler(commands=['backupdb'])
async def cmd_backup_db(message: types.Message):
    try:
        shutil.copy('chat_links.db', 'chat_links_backup.db')
        await message.reply_document(open('chat_links_backup.db', 'rb'), caption="Database berhasil di-backup.")
    except Exception as e:
        logging.error(f"Error during database backup: {str(e)}")
        await message.reply("Gagal melakukan backup database.")

# Handler untuk restore database
@dp.message_handler(commands=['restoredb'])
async def cmd_restore_db(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply("Silakan reply pesan ini ke file database yang ingin di-restore.")
        return

    try:
        # Download file
        file_info = await bot.get_file(message.reply_to_message.document.file_id)
        file_path = file_info.file_path
        await bot.download_file(file_path, 'chat_links_new.db')

        # Hapus database lama dan rename yang baru
        if os.path.exists('chat_links.db'):
            os.remove('chat_links.db')
        shutil.move('chat_links_new.db', 'chat_links.db')

        await message.reply("Database berhasil di-restore.")
    except Exception as e:
        logging.error(f"Error during database restore: {str(e)}")
        await message.reply("Gagal melakukan restore database.")




async def send_to_channels(message: types.Message, content_type):
    sent_message_main = None
    if content_type == 'text':
        sent_message_main = await bot.send_message(CHANNEL_ID, message.html_text, parse_mode='HTML')
    elif content_type == 'photo':
        sent_message_main = await bot.send_photo(CHANNEL_ID, photo=message.photo[-1].file_id, caption=message.caption)
    elif content_type == 'audio':
        sent_message_main = await bot.send_audio(CHANNEL_ID, audio=message.audio.file_id, caption=message.caption)
    elif content_type == 'video':
        sent_message_main = await bot.send_video(CHANNEL_ID, video=message.video.file_id, caption=message.caption)
    else:
        return None, "Unsupported content type"

    if not sent_message_main:
        return None, "Failed to send message"

    user_mention = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"
    info_message = f"{user_mention}\n(ID: {message.from_user.id}).\n[Click here to view]({sent_message_main.url})"

    sent_message_info = await boti.send_message(-1002136671072, info_message, disable_web_page_preview=False, parse_mode='Markdown')
    return sent_message_main, sent_message_info

@dp.message_handler(commands=['cekalldb'])
async def cmd_check_all_db(message: types.Message):
    tables = ['chat_links', 'banned_users', 'badwords', 'filterwords', 'users', 'hashtags']

    for table in tables:
        contents = fetch_table_contents(table)
        if contents:
            if table == 'users':
                # Send users table as file
                csv_file_path = create_csv_file_with_message_count(contents, table)
                await message.reply_document(open(csv_file_path, 'rb'), caption=f"Isi tabel {table}")
                os.remove(csv_file_path)  # Clean up the temporary file after sending
            else:
                # Send other tables as separate messages
                response = [f"Isi tabel {table}:"]
                columns = [desc[1] for desc in sqlite3.connect('chat_links.db').cursor().execute(f"PRAGMA table_info({table})").fetchall()]  # Get column names
                response.append(", ".join(columns))  # Add header

                for row in contents:
                    formatted_row = ", ".join(str(item) for item in row)
                    response.append(formatted_row)

                await message.reply("\n".join(response))
        else:
            await message.reply(f"Tabel {table} kosong atau tidak ditemukan.")

@dp.message_handler(lambda message: any(hashtag.lower() in (message.text or message.caption or "").lower() for hashtag in get_hashtags()) and message.chat.type == 'private', content_types=types.ContentType.ANY)
async def handle_specific_hashtag_message_from_private(message: types.Message, state: FSMContext):

    await state.update_data(message_content=message, content_type=message.content_type)

    keyboard = InlineKeyboardMarkup(row_width=2)
    confirm_button = InlineKeyboardButton(text="Konfirmasi", callback_data="confirm_send")
    cancel_button = InlineKeyboardButton(text="Batal", callback_data="cancel_send")
    keyboard.add(confirm_button, cancel_button)

    # Kirim pesan konfirmasi dengan tombol
    await message.reply("Konfirmasi untuk mengirim pesan ini ke channel:", reply_markup=keyboard)

@dp.message_handler(lambda message: any(hashtag in (message.text or message.caption or "") for hashtag in get_hashtags()) and message.chat.type in ['group', 'supergroup'], content_types=types.ContentType.ANY)
async def delete_hashtag_message_in_group(message: types.Message):
    conditions_met, _ = check_message_conditions(message, get_hashtags())
    if conditions_met:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

@dp.callback_query_handler(lambda c: c.data == 'confirm_send', state='*')
async def confirm_send_to_channel(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id

    # Pengecekan rate limit
    if not await rate_limit_check(callback_query.from_user.id, callback_query.message):
        return

    if in_progress.get(user_id, False):
        await callback_query.answer("Sedang diproses, sabar ya...")
        return

    in_progress[user_id] = True
    try:
        data = await state.get_data()
        message_content = data['message_content']
        content_type = data['content_type']

        sent_message, _ = await send_to_channels(message_content, content_type)
        if sent_message:
            await callback_query.message.edit_text(f"Pesan terkirim: [lihat di sini]({sent_message.url})", parse_mode="Markdown")
            await increment_user_message_count(user_id)
        else:
            await callback_query.message.edit_text("Gagal mengirim pesan ke channel.")

        await callback_query.answer()
        await state.finish()
    finally:
        in_progress[user_id] = False

@dp.callback_query_handler(lambda c: c.data == 'cancel_send', state='*')
async def cancel_send_to_channel(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Pengiriman dibatalkan.")
    await callback_query.answer()

@dp.message_handler(lambda message: message.chat.type == 'private', content_types=types.ContentType.ANY)
async def forward_any_to_admin(message: types.Message):
    forwarded_msg = await message.forward(-1002087824662)
    forwarded_message_mapping[forwarded_msg.message_id] = message.from_user.id

@dp.message_handler(lambda message: message.chat.type in ['group', 'supergroup'] and message.reply_to_message, content_types=types.ContentType.ANY)
async def reply_to_user(message: types.Message):
    original_message_id = message.reply_to_message.message_id
    original_user_id = forwarded_message_mapping.get(original_message_id)
    if original_user_id:
        if message.content_type == 'text':
            await bot.send_message(original_user_id, message.text)
        elif message.content_type == 'photo':
            await bot.send_photo(original_user_id, photo=message.photo[-1].file_id, caption=message.caption)
        elif message.content_type == 'audio':
            await bot.send_audio(original_user_id, audio=message.audio.file_id, caption=message.caption)
        elif message.content_type == 'video':
            await bot.send_video(original_user_id, video=message.video.file_id, caption=message.caption)
        elif message.content_type == 'document':
            await bot.send_document(original_user_id, document=message.document.file_id, caption=message.caption)
        elif message.content_type == 'sticker':
            await bot.send_sticker(original_user_id, sticker=message.sticker.file_id)
        else:
            await bot.send_message(original_user_id, "Received a message type that I can't handle!")
        logging.info(f"Reply sent to user: {original_user_id} with content type: {message.content_type}")
        
async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == '__main__':
    from aiogram import executor
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
