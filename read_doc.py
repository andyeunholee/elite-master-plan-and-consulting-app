import docx
import sys

try:
    doc = docx.Document("Elite Prep- Master Plan Guide format.docx")
    print("--- START OF DOC ---")
    for i, para in enumerate(doc.paragraphs):
        if para.text.strip():
            print(f"[{i}] {para.text}")
    print("--- END OF DOC ---")
except Exception as e:
    print(f"Error: {e}")
