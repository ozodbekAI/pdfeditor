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
        self.size_order = [42, 44, 46, 48, 50, 52, 54, 56]
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
        # Faqat fayl nomi (kengaytmasiz)
        name = Path(filename).stem
        parts = name.split()
        
        size = ""
        
        # 1) Avval nom ichidagi raqamlarni izlaymiz (orqadan boshlab)
        for part in reversed(parts):
            if part.isdigit():
                num = int(part)
                if num in self.size_order:  # [42, 44, 46, 48, 50, 52, 54, 56]
                    size = str(num)
                    break
        
        # 2) Agar topilmasa: '56 разме', '56 размер', '56размер' kabi holatlar
        if not size:
            m = re.search(r'(\d{2})\s*разм', name, re.IGNORECASE)
            if m:
                num = int(m.group(1))
                if num in self.size_order:
                    size = str(num)
        
        # Article va rangni ajratamiz
        article = ""
        color = ""
        
        if len(parts) >= 2:
            article = " ".join(parts[:2])  # masalan: "Ю 3718"
        
        if size:
            # size qaysi indeksda – shunga qarab color'ni olamiz
            if size in parts:
                size_idx = parts.index(size)
                # rang – 3-elementdan (index 2) boshlab size'ga qadar
                if size_idx > 2:
                    color = " ".join(parts[2:size_idx])
                else:
                    color = " ".join(parts[2:])
            else:
                # size matndan (regex) topilgan bo'lsa, shunchaki qolganini rang deb olamiz
                color = " ".join(parts[2:])
        else:
            # O'lchamni topa olmadik – faqat article va rang
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
        """Barcha o'lchamlarni bitta faylga birlashtirish"""
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
    
    def process(self, create_combined: bool = True) -> Tuple[bool, List[Path]]:
        # Barcha PDF fayllar
        all_pdfs = list(self.input_dir.glob("*.pdf"))
        
        # 1) Nomi bo'yicha aniq etiketkani topishga harakat qilamiz
        label_files = [
            f for f in all_pdfs
            if re.search(r"(тикетка|этикетка|все\s*размеры|Этикетка)", f.name, re.IGNORECASE)
        ]
        
        
        if not label_files:
            self.log("❌ Etiketka fayli topilmadi!", "ERROR")
            return False, []
        
        label_file = label_files[0]
        
        # KIZ fayllar – barcha PDF lar ichidan etiketkani chiqarib tashlaymiz
        kiz_files = [f for f in all_pdfs if f != label_file]
        
        if not kiz_files:
            self.log("❌ KIZ fayllari topilmadi!", "ERROR")
            return False, []
        
        self.log(f"📂 KIZ fayllari: {len(kiz_files)} ta")
        self.log("")
        
        label_reader = PdfReader(label_file)
        size_pages = self.find_label_pages(label_file)
            
        if not size_pages:
            self.log("❌ Etiketka sahifalari topilmadi!", "ERROR")
            return False, []
        
        self.log("")
        self.log("⚙️ Qayta ishlash boshlandi...")
        self.log("-" * 50)
        
        created_files = []
        
        for kiz_file in sorted(kiz_files):
            info = self.extract_kiz_info(kiz_file.name)
            size = int(info['size']) if info['size'].isdigit() else None
            
            if size and size in size_pages:
                tovar_page, qadoq_page = size_pages[size]
                
                output_filename = f"Сборка_{info['article'].replace(' ', '')}_{info['color']}_{size}.pdf"
                output_path = self.output_dir / output_filename
                
                pages = self.assemble_pdf_for_size(
                    label_reader, tovar_page, qadoq_page, kiz_file, output_path
                )
                
                if pages > 0:
                    created_files.append(output_path)
            else:
                self.log(f"⚠️ {kiz_file.name} uchun etiketka topilmadi!", "WARNING")
        
        if create_combined and created_files:
            first_info = self.extract_kiz_info(kiz_files[0].name)
            combined_filename = f"Сборка_{first_info['article'].replace(' ', '')}_{first_info['color']}_все_размеры.pdf"
            combined_path = self.output_dir / combined_filename
            
            self.log("")
            self.create_combined_pdf(created_files, combined_path)
            created_files.append(combined_path)
        
        
        return True, created_files

