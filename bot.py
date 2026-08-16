import asyncio
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import re
from datetime import datetime
import json
import os
from urllib.parse import urlparse

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "8039716101:AAH-wjh3I6BsZTHbbW0VKYbGEVXWF7YJ2_0")
CHAT_ID = os.getenv("CHAT_ID", "1605067196")

URLS = [
    "https://www.kufar.by/l/r~vitebskaya-obl/mobilnye-telefony/mt~apple?ar=v.or%3A18&sort=lst.d",
]

CHECK_INTERVAL = 120
# =================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "visited_links.json"

def normalize_link(link):
    if not link:
        return link
    if not link.startswith('http'):
        link = 'https://www.kufar.by' + link
    parsed = urlparse(link)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

def load_visited():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_visited(links):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(links), f, ensure_ascii=False, indent=2)

visited_links = load_visited()
print(f"📂 Загружено {len(visited_links)} отправленных объявлений")

# ========== КЛАВИАТУРЫ ==========
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔍 Проверить сейчас", callback_data="check_now"),
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        InlineKeyboardButton("📋 Мои ссылки", callback_data="my_links"),
        InlineKeyboardButton("❓ Помощь", callback_data="help"),
        InlineKeyboardButton("🗑 Сбросить историю", callback_data="reset_history")
    )
    return keyboard

def back_button():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="menu"))
    return keyboard

# ========== ПАРСИНГ ==========
def extract_ad_info(html):
    soup = BeautifulSoup(html, 'html.parser')
    ad_cards = soup.find_all('a', class_=re.compile(r'styles_wrapper__\w+'))
    
    results = []
    for card in ad_cards:
        href = card.get('href')
        if not href or '/item/' not in href:
            continue
        
        if not href.startswith('http'):
            link = 'https://www.kufar.by' + href
        else:
            link = href
        
        title_elem = card.find('h3', class_=re.compile(r'styles_title__\w+'))
        if not title_elem:
            title_elem = card.find('span', class_=re.compile(r'styles_title__\w+'))
        title = title_elem.text.strip() if title_elem else "Без названия"
        
        price_elem = card.find('p', class_=re.compile(r'styles_price__\w+'))
        if not price_elem:
            price_elem = card.find('span', class_=re.compile(r'styles_price__\w+'))
        price = price_elem.text.strip() if price_elem else "Цена не указана"
        price = re.sub(r'\s+', ' ', price)
        
        region_elem = card.find('p', class_=re.compile(r'styles_region__\w+'))
        city = region_elem.text.strip() if region_elem else ""
        
        photo_url = None
        img_elem = card.find('img')
        if img_elem:
            photo_url = img_elem.get('src') or img_elem.get('data-src')
            if photo_url and not photo_url.startswith('http'):
                photo_url = 'https:' + photo_url if photo_url.startswith('//') else 'https://www.kufar.by' + photo_url
        
        results.append({
            'link': link,
            'title': title,
            'price': price,
            'city': city,
            'photo': photo_url
        })
    
    return results

# ========== ОБРАБОТЧИКИ ==========
@dp.message_handler(commands=['start', 'menu'])
async def start_command(message: types.Message):
    welcome_text = (
        "👋 *Привет! Я бот для мониторинга Kufar!*\n\n"
        "Я отслеживаю *НОВЫЕ* объявления и присылаю их с ценой и фото.\n"
        "Каждое объявление отправляется *ТОЛЬКО 1 РАЗ*!\n\n"
        "📌 *Сейчас мониторю:*\n"
        f"• Витебская область, Apple-телефоны\n"
        f"• Интервал: *{CHECK_INTERVAL} сек*\n"
        f"• Уже отправлено: *{len(visited_links)}* объявлений\n\n"
        "Выбери действие в меню 👇"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_menu())

@dp.callback_query_handler(lambda c: c.data == "menu")
async def menu_callback(callback: types.CallbackQuery):
    await callback.message.edit_text("📋 *Главное меню:*", parse_mode="Markdown", reply_markup=main_menu())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "check_now")
async def check_now_callback(callback: types.CallbackQuery):
    await callback.message.edit_text("🔍 *Идёт проверка...*", parse_mode="Markdown")
    await callback.answer()
    
    new_count = 0
    for url in URLS:
        count = await check_updates_for_url(url)
        new_count += count
    
    await callback.message.edit_text(
        f"✅ *Проверка завершена!*\n\n📦 Найдено новых: *{new_count}*\n📂 Всего отправлено: *{len(visited_links)}*",
        parse_mode="Markdown",
        reply_markup=back_button()
    )

@dp.callback_query_handler(lambda c: c.data == "stats")
async def stats_callback(callback: types.CallbackQuery):
    stats_text = (
        "📊 *Статистика:*\n\n"
        f"📦 Отправлено объявлений: *{len(visited_links)}*\n"
        f"🔗 Отслеживаемых ссылок: *{len(URLS)}*\n"
        f"⏱ Интервал проверки: *{CHECK_INTERVAL} сек*\n"
        f"🟢 Статус: *Работает*"
    )
    await callback.message.edit_text(stats_text, parse_mode="Markdown", reply_markup=back_button())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "reset_history")
async def reset_history_callback(callback: types.CallbackQuery):
    global visited_links
    visited_links = set()
    save_visited(visited_links)
    await callback.message.edit_text("🗑 *История очищена!*\n\nТеперь бот отправит все текущие объявления как новые.", parse_mode="Markdown", reply_markup=back_button())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "help")
async def help_callback(callback: types.CallbackQuery):
    help_text = (
        "❓ *Как работает бот:*\n\n"
        "1️⃣ Проверяет сайт каждые 2 минуты\n"
        "2️⃣ Находит САМОЕ СВЕЖЕЕ объявление\n"
        "3️⃣ Проверяет, отправлял ли его ранее\n"
        "4️⃣ Если *НЕ ОТПРАВЛЯЛ* — присылает и запоминает\n"
        "5️⃣ Если *УЖЕ ОТПРАВЛЯЛ* — пропускает\n\n"
        "📌 Каждое объявление отправляется *ТОЛЬКО 1 РАЗ*!\n"
        "📌 Кнопка «Сбросить историю» — отправит все заново"
    )
    await callback.message.edit_text(help_text, parse_mode="Markdown", reply_markup=back_button())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "my_links")
async def my_links_callback(callback: types.CallbackQuery):
    if not URLS:
        links_text = "❌ Активных ссылок пока нет."
    else:
        links_text = "📋 *Твои ссылки:*\n\n"
        for i, url in enumerate(URLS, 1):
            short_url = url[:60] + "..." if len(url) > 60 else url
            links_text += f"{i}. {short_url}\n"
        links_text += f"\nВсего: *{len(URLS)}*"
    
    await callback.message.edit_text(links_text, parse_mode="Markdown", reply_markup=back_button())
    await callback.answer()

# ========== ОСНОВНАЯ ЛОГИКА ==========
async def check_updates_for_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status != 200:
                    print(f"[{datetime.now()}] ❌ HTTP {response.status}")
                    return 0
                
                html = await response.text()
                ads = extract_ad_info(html)
                
                print(f"[{datetime.now()}] 📦 Найдено {len(ads)} объявлений")
                
                if not ads:
                    print(f"[{datetime.now()}] ⚠️ Объявлений не найдено")
                    return 0
                
                ad = ads[0]
                original_link = ad['link']
                normalized_link = normalize_link(original_link)
                
                print(f"[{datetime.now()}] 🔗 Оригинальная ссылка: {original_link}")
                print(f"[{datetime.now()}] 🔗 Нормализованная ссылка: {normalized_link}")
                
                if normalized_link in visited_links:
                    print(f"[{datetime.now()}] ⏸ Объявление уже отправлено: {ad['title'][:40]}...")
                    return 0
                
                if original_link in visited_links:
                    print(f"[{datetime.now()}] ⏸ Объявление уже отправлено (по оригинальной ссылке): {ad['title'][:40]}...")
                    return 0
                
                print(f"[{datetime.now()}] 🆕 НОВОЕ объявление: {ad['title'][:40]}...")
                
                city_text = f"📍 *{ad['city']}*" if ad['city'] else ""
                
                caption = (
                    f"🔔 *НОВОЕ ОБЪЯВЛЕНИЕ!*\n\n"
                    f"📱 *{ad['title']}*\n"
                    f"💰 *{ad['price']}*\n"
                    f"{city_text}\n\n"
                    f"🔗 [Открыть объявление]({original_link})"
                )
                
                try:
                    if ad['photo']:
                        await bot.send_photo(
                            chat_id=CHAT_ID,
                            photo=ad['photo'],
                            caption=caption,
                            parse_mode="Markdown"
                        )
                    else:
                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=caption,
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        )
                    
                    visited_links.add(original_link)
                    visited_links.add(normalized_link)
                    save_visited(visited_links)
                    print(f"[{datetime.now()}] ✅ ОТПРАВЛЕНО и ЗАПОМНЕНО: {ad['title'][:40]}...")
                    print(f"[{datetime.now()}] 💾 Сохранено ссылок в истории: {len(visited_links)}")
                    return 1
                    
                except Exception as e:
                    print(f"[{datetime.now()}] ❌ Ошибка отправки: {e}")
                    visited_links.add(original_link)
                    visited_links.add(normalized_link)
                    save_visited(visited_links)
                    return 0
                    
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Ошибка: {e}")
            return 0

# ========== ЗАПУСК ==========
async def scheduled_check():
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        print(f"\n[{datetime.now()}] 🔄 Плановая проверка...")
        print(f"📂 В истории {len(visited_links)} ссылок")
        for url in URLS:
            await check_updates_for_url(url)

async def on_startup(dp):
    print("=" * 60)
    print("🚀 БОТ ЗАПУЩЕН!")
    print("=" * 60)
    print(f"📋 Мониторим {len(URLS)} ссылок")
    print(f"⏱ Интервал: {CHECK_INTERVAL} секунд")
    print(f"📂 Уже отправлено: {len(visited_links)} объявлений")
    print("=" * 60)
    print("📡 Первичная инициализация...")
    
    for url in URLS:
        await check_updates_for_url(url)
    
    print("✅ Бот готов к работе!")
    print("=" * 60)
    
    asyncio.create_task(scheduled_check())

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
