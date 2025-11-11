import asyncio
import tempfile
import zipfile
import shutil
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, TEMP_DIR, MAX_FILE_SIZE
from pdf_assembler import PDFAssembler


class PDFBot:
    
    def __init__(self, token: str):
        self.bot = Bot(token=token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.setup_handlers()
    
    def setup_handlers(self):
        self.dp.message.register(self.cmd_start, CommandStart())
        self.dp.message.register(self.handle_document, F.document)
    
    async def cmd_start(self, message: Message):
        welcome_text = (
            "👋 <b>Здравствуйте!</b>\n\n"
            "📦 Этот бот автоматически собирает PDF файлы этикеток и КИЗ.\n\n"
            "<b>📤 Как работает:</b>\n"
            "1️⃣ Подготовьте ZIP файл:\n"
            "   • Файл этикетки (например: Этикетка.pdf)\n"
            "   • Файлы КИЗ (например: Ю 1128 черный 42.pdf)\n\n"
            "2️⃣ Отправьте ZIP файл боту\n\n"
            "3️⃣ Бот обработает и отправит результаты в ZIP\n\n"
            "<b>✅ Результат:</b>\n"
            "   • Отдельный PDF для каждого размера\n"
            "   • Все размеры в одном PDF\n\n"
            "❓ Вопросы: @your_support"
        )
        await message.answer(welcome_text, parse_mode="HTML")
    
    async def handle_document(self, message: Message):
        document = message.document
        
        if not document.file_name.lower().endswith('.zip'):
            await message.answer(
                "❌ <b>Неверный тип файла!</b>\n\n"
                "Отправляйте только ZIP файлы.\n"
                "Внутри должны быть файлы этикеток и КИЗ.",
                parse_mode="HTML"
            )
            return
        
        if document.file_size > MAX_FILE_SIZE:
            size_mb = document.file_size / (1024 * 1024)
            max_mb = MAX_FILE_SIZE / (1024 * 1024)
            await message.answer(
                f"❌ <b>Файл слишком большой!</b>\n\n"
                f"Ваш файл: {size_mb:.1f} MB\n"
                f"Максимум: {max_mb:.0f} MB",
                parse_mode="HTML"
            )
            return
        
        status_msg = await message.answer("⏳ Загрузка файла...")
        
        temp_id = f"user_{message.from_user.id}_{message.message_id}"
        work_dir = TEMP_DIR / temp_id
        work_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            zip_path = work_dir / document.file_name
            await self.bot.download(document, zip_path)
            
            await status_msg.edit_text("📦 Распаковка ZIP...")
            
            input_dir = work_dir / "input"
            input_dir.mkdir(exist_ok=True)
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(input_dir)
            except zipfile.BadZipFile:
                await status_msg.edit_text("❌ <b>ZIP файл поврежден!</b>", parse_mode="HTML")
                return
            
            pdf_files = list(input_dir.rglob("*.pdf"))
            if len(pdf_files) < 2:
                await status_msg.edit_text(
                    "❌ <b>Недостаточно файлов!</b>\n\n"
                    "Нужно минимум 2 PDF:\n"
                    "• 1 файл этикетки\n"
                    "• 1+ файл КИЗ",
                    parse_mode="HTML"
                )
                return
            
            await status_msg.edit_text(
                f"⚙️ Обработка...\n"
                f"📄 Найдено: {len(pdf_files)} PDF"
            )
            
            output_dir = work_dir / "output"
            assembler = PDFAssembler(str(input_dir), str(output_dir))
            
            success, created_files = assembler.process(create_combined=True)
            
            if not success or not created_files:
                await status_msg.edit_text(
                    "❌ <b>Ошибка обработки!</b>\n\n"
                    "Проверьте файлы этикеток и КИЗ.",
                    parse_mode="HTML"
                )
                return
            
            await status_msg.edit_text("📦 Создание ZIP архива...")
            
            result_zip_path = work_dir / "Сборка_результаты.zip"
            
            with zipfile.ZipFile(result_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in created_files:
                    zip_file.write(file_path, file_path.name)
            
            await status_msg.edit_text("📤 Отправка...")
            
            result_file = FSInputFile(
                result_zip_path,
                filename="Сборка_результаты.zip"
            )
            
            await message.answer_document(
                result_file,
                caption="✅ <b>Готово!</b>",
                parse_mode="HTML"
            )
            
            file_size_kb = result_zip_path.stat().st_size / 1024
            report = (
                f"📊 <b>Результат:</b>\n\n"
                f"✅ Создано: {len(created_files)} файлов\n"
                f"📦 Размер: {file_size_kb:.1f} KB\n\n"
                f"<i>Для новой сборки отправьте ZIP.</i>"
            )
            
            await status_msg.edit_text(report, parse_mode="HTML")
            
        except Exception as e:
            error_text = (
                f"❌ <b>Непредвиденная ошибка!</b>\n\n"
                f"<code>{str(e)}</code>\n\n"
                f"Свяжитесь с администратором."
            )
            await message.answer(error_text, parse_mode="HTML")
            
        finally:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except:
                pass
    
    async def start(self):
        print("BOT ЗАПУЩЕН")
        await self.dp.start_polling(self.bot)
    
    async def stop(self):
        await self.bot.session.close()


async def main():
    
    bot = PDFBot(BOT_TOKEN)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n⏹️ Бот остановлен")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())