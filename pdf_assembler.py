import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from pypdf import PdfReader, PdfWriter


class PDFAssembler:
    
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.log_messages = []
        self.size_order = [42, 44, 46, 48, 50, 52, 54, 56]   # qat’iy tartib
        self.output_dir.mkdir(exist_ok=True)
        
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.log_messages.append(log_entry)
        print(log_entry)
    
    def get_log_text(self) -> str:
        return '\n'.join(self.log_messages)
    
    def extract_text_from_page(self, page) -> str:
        try:
            return page.extract_text()
        except Exception as e:
            self.log(f"Matn chiqarishda xatolik: {e}", "WARNING")
            return ""
    
    def find_size_in_text(self, text: str) -> Optional[int]:
        match = re.search(r'Размер:\s*(\d+)', text)
        if match:
            return int(match.group(1))
        return None
    
    def find_label_pages(self, label_file_path: Path) -> Dict[int, Tuple[int, int]]:
        self.log(f"📄 Etiketka fayli: {label_file_path.name}")
        
        try:
            reader = PdfReader(label_file_path)
            total_pages = len(reader.pages)
            self.log(f"   Jami {total_pages} sahifa")
            
            size_pages = {}
            current_size = None
            first_page = None
            
            for page_num, page in enumerate(reader.pages):
                text = self.extract_text_from_page(page)
                size = self.find_size_in_text(text)
                
                if size:
                    if current_size == size and first_page is not None:
                        size_pages[size] = (first_page, page_num)
                        self.log(f"   ✓ O'lcham {size}: sahifa {first_page}+{page_num}")
                        current_size = None
                        first_page = None
                    else:
                        current_size = size
                        first_page = page_num
            
            if not size_pages:
                self.log("⚠️ Hech qanday o'lcham topilmadi!", "WARNING")
            
            return size_pages
            
        except Exception as e:
            self.log(f"❌ Xatolik: {e}", "ERROR")
            return {}
    
    def extract_kiz_info(self, filename: str) -> Dict[str, str]:
        """
        KIZ nomidan:
        - article
        - color
        - size (bo‘lsa)
        chiqarib beradi.
        Agar size bo‘lmasa — avtomatik fallback ishlaydi (pastda).
        """
        name = Path(filename).stem
        parts = name.split()
        
        size = ""
        
        # 1) Orqadan raqam qidirish
        for part in reversed(parts):
            if part.isdigit():
                num = int(part)
                if num in self.size_order:
                    size = str(num)
                    break
        
        # 2) "56 размер" kabi format
        if not size:
            m = re.search(r'(\d{2})\s*разм', name, re.IGNORECASE)
            if m:
                num = int(m.group(1))
                if num in self.size_order:
                    size = str(num)
        
        # Article + color
        article = ""
        color = ""
        
        if len(parts) >= 2:
            article = " ".join(parts[:2])
        
        if size:
            if size in parts:
                idx = parts.index(size)
                if idx > 2:
                    color = " ".join(parts[2:idx])
                else:
                    color = " ".join(parts[2:])
            else:
                color = " ".join(parts[2:])
        else:
            color = " ".join(parts[2:])
        
        return {"article": article, "color": color, "size": size}
    
    def assemble_pdf_for_size(
        self,
        label_reader: PdfReader,
        tovar_page: int,
        qadoq_page: int,
        kiz_file_path: Path,
        output_path: Path
    ) -> int:
        try:
            kiz_reader = PdfReader(kiz_file_path)
            kiz_page_count = len(kiz_reader.pages)
            
            self.log(f"   📦 KIZ: {kiz_file_path.name} ({kiz_page_count} dona)")
            
            writer = PdfWriter()
            tovar_page_obj = label_reader.pages[tovar_page]
            qadoq_page_obj = label_reader.pages[qadoq_page]
            
            for kiz_page in kiz_reader.pages:
                writer.add_page(tovar_page_obj)
                writer.add_page(qadoq_page_obj)
                writer.add_page(kiz_page)
                writer.add_page(kiz_page)
            
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            total_pages = kiz_page_count * 4
            self.log(f"   ✅ Tayyor: {output_path.name} ({total_pages} sahifa)")
            
            return total_pages
            
        except Exception as e:
            self.log(f"   ❌ Xatolik: {e}", "ERROR")
            return 0
    
    def create_combined_pdf(self, individual_files: List[Path], output_path: Path):
        try:
            self.log("🔗 Umumiy fayl yaratilmoqda...")
            
            writer = PdfWriter()
            total_pages = 0
            
            for size in self.size_order:
                for file_path in individual_files:
                    if f"_{size}.pdf" in str(file_path):
                        reader = PdfReader(file_path)
                        for page in reader.pages:
                            writer.add_page(page)
                        total_pages += len(reader.pages)
                        self.log(f"   + {file_path.name}")
            
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            self.log(f"✅ Umumiy fayl: {output_path.name} ({total_pages} sahifa)")
            
        except Exception as e:
            self.log(f"❌ Xatolik: {e}", "ERROR")
    
    def process(self, create_combined: bool = True):
        
        # 1) Hamma PDFlarni topamiz
        all_pdfs = list(self.input_dir.rglob("*.pdf"))

        # MacOS keraksiz fayllarni tashlab yuboramiz
        all_pdfs = [
            f for f in all_pdfs
            if "__MACOSX" not in f.parts and not f.name.startswith("._")
        ]

        if not all_pdfs:
            self.log("❌ PDF fayllar topilmadi!", "ERROR")
            return False, []

        # 2) Eng katta pdf — etiketka
        label_file = max(all_pdfs, key=lambda f: f.stat().st_size)
        self.log(f"📄 Etiketka fayli tanlandi: {label_file.name}")

        kiz_files = [f for f in all_pdfs if f != label_file]
        self.log(f"📂 KIZ fayllari: {len(kiz_files)} ta\n")

        # 3) Etiketka sahifalari
        label_reader = PdfReader(label_file)
        size_pages = self.find_label_pages(label_file)

        if not size_pages:
            self.log("❌ Etiketka sahifalari topilmadi!", "ERROR")
            return False, []

        self.log("\n⚙️ Qayta ishlash boshlandi...")
        self.log("-" * 50)

        # 4) KIZ haqida ma’lumot to‘plash
        kiz_infos = []
        known_sizes = set()

        for f in sorted(kiz_files):
            info = self.extract_kiz_info(f.name)
            s = int(info["size"]) if info["size"].isdigit() else None
            kiz_infos.append({"file": f, "info": info, "size": s})
            if s:
                known_sizes.add(s)

        missing_sizes = [s for s in self.size_order if s not in known_sizes]
        unknown_items = [x for x in kiz_infos if x["size"] is None]

        # 5) Avtomatik o‘lcham taqsimlash (universal)
        if unknown_items:
            if len(kiz_files) == len(self.size_order) and len(unknown_items) == len(missing_sizes):
                unknown_items.sort(key=lambda x: x["file"].name)
                for item, s in zip(unknown_items, missing_sizes):
                    item["size"] = s
                    item["info"]["size"] = str(s)
                    self.log(f"ℹ️ Size topilmadi → avtomatik: {item['file'].name} → {s}")
            else:
                for item in unknown_items:
                    self.log(f"⚠️ {item['file'].name} uchun size topilmadi!", "WARNING")

        # 6) Yig‘ish
        created_files = []

        for item in kiz_infos:
            kiz_file = item["file"]
            info = item["info"]
            size = item["size"]

            if size and size in size_pages:
                tovar_page, qadoq_page = size_pages[size]

                article_safe = (info["article"] or "NOARTICLE").replace(" ", "")
                color_safe = (info["color"] or "NOCOLOR").strip()

                output_filename = f"Сборка_{article_safe}_{color_safe}_{size}.pdf"
                output_path = self.output_dir / output_filename

                pages = self.assemble_pdf_for_size(
                    label_reader, tovar_page, qadoq_page, kiz_file, output_path
                )

                if pages > 0:
                    created_files.append(output_path)
            else:
                self.log(f"⚠️ {kiz_file.name} uchun etiketka topilmadi!", "WARNING")

        # 7) Bitta umumiy pdf
        if create_combined and created_files:
            first = kiz_infos[0]["info"]
            combined_name = f"Сборка_{first['article'].replace(' ', '')}_{first['color']}_все_размеры.pdf"
            combined_path = self.output_dir / combined_name
            self.create_combined_pdf(created_files, combined_path)
            created_files.append(combined_path)

        return True, created_files
