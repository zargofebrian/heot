import asyncio
import sqlite3
import os
from pyrogram import Client, errors
from datetime import datetime, timedelta

api_id = '22343291'
api_hash = '8586812c2c0a51f9720d20f101a815b1'
app = Client("USERBOT2", api_id, api_hash, session_string="BQFU7nsAbj-3rSNRIeg7j33crwyClFWzdmDF_m2yDsR5HMV8VwfO9quMnlVxEUmXIrgDMy1-PMvkBLgy_yWRHlvOnQpQm-b884RTkXNv8I0yA4e0f6plRlfMhffZbQ5Dgl6VWhZ5F3Rthr3dUvCjeW5JDkmYM9exZ5so3xB-ofMxnL35semwynX1WE_lN4naUsnW1cQNpIY0FxRoyamNsqFwt5d8_FvgPn7WdZDX81lW_0bTH7KYnD9Z4b0gFzgxWl7c-RIlGtyJ0WbV0Xbv-AXfFWtBvBqvd_vHtF9tQ0c9kxPIouc6-bgKKThaw54ZHcbikDjoR5D7ySSwAZ-Pk_wLWhlPqAAAAAGjDFPOAA")

# Set untuk menyimpan target yang telah mengalami kesalahan serius
critical_errors_targets = set()
failed_attempts = {}

def get_db_connection():
    return sqlite3.connect('bot_database.db')

def delete_target(username):
    with sqlite3.connect('bot_database.db') as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM targets WHERE username = ?", (username,))
        print(f"Target {username} dihapus dari database.")

async def download_db():
    try:
        # Link to the database file in the Telegram channel
        source_channel = "SOURCEDATABASE"
        message_id = 5

        # Download the file from the Telegram channel
        message = await app.get_messages(source_channel, message_id)
        file_path = await app.download_media(message)

        # Replace the existing database file with the new one
        if os.path.exists('bot_database.db'):
            os.remove('bot_database.db')
        os.rename(file_path, 'bot_database.db')
        print("Database berhasil diperbarui.")
    except Exception as e:
        print(f"Failed to download and update the database: {e}")

async def send_message(target, message):
    if target in critical_errors_targets:
        print(f"Skipping sending to {target} due to prior critical error.")
        return
    await app.send_message(target, message)

def fetch_targets():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, message, delay FROM targets")
    tugas = cursor.fetchall()
    cursor.close()
    conn.close()
    return tugas

async def run_tugas(target, pesan, delay):
    while True:
        if target in critical_errors_targets:
            print(f"Stopping messages to {target} due to prior critical error.")
            break
        try:
            await send_message(target, pesan)
            current_time = datetime.now().strftime("%M:%S")
            print(f"{target} {current_time}. delay {delay} 2")
        except errors.ChatWriteForbidden:
            failed_attempts[target] = failed_attempts.get(target, 0) + 1
            print(f"Cannot send message to {target} due to 'Chat Write Forbidden'. Attempting to join chat. Attempt: {failed_attempts[target]}")
            try:
                await app.join_chat(target)
            except Exception as join_error:
                print(f"Failed to join chat {target}: {join_error}")
            if failed_attempts[target] >= 3:
                print(f"Deleting target {target} after 3 failed attempts to join.")
                delete_target(target)
                break
        except errors.ChatAdminRequired:
            print(f"Admin rights required for {target}. Deleting target.")
            delete_target(target)
            critical_errors_targets.add(target)
            break
        except errors.FloodWait as e:
            wait_time = getattr(e, 'x', 10)  # Default to 10 seconds if 'x' is not present
            print(f"Must wait {wait_time} seconds due to flood limit. Pausing.")
            await asyncio.sleep(wait_time)
        except errors.PeerIdInvalid:
            print(f"Invalid Peer ID: {target}. Removing from tasks.")
            delete_target(target)
            break
        except errors.UserIsBlocked:
            print(f"User has blocked the bot: {target}. Removing from tasks.")
            delete_target(target)
            break
        except Exception as e:
            error_message = f"Unhandled exception for {target}: {e}"
            print(error_message)
            await send_message('@jerga4', error_message)
        await asyncio.sleep(delay)

async def main():
    await app.start()
    await download_db()  # Update the database before starting tasks
    tugas_list = fetch_targets()
    if not tugas_list:
        print("Tidak ada tugas yang perlu dijalankan.")
    else:
        tasks = [asyncio.create_task(run_tugas(username, message, delay)) for _, username, message, delay in tugas_list]
        await asyncio.gather(*tasks)
    await app.stop()

if __name__ == '__main__':
    asyncio.run(main())
