from pathlib import Path

import pymupdf as fitz


OUT = Path(__file__).with_name("sample_deck.pdf")
FONT = Path("/usr/share/fonts/TTF/DejaVuSans.ttf")
PAGES = [
    ("Stayflow", "The operating system for independent hotels\nBarcelona · Seed round · Fictional startup"),
    ("The problem", "Independent hotels lose time switching between disconnected tools.\nStayflow brings guest operations into one workspace."),
    ("A large market", "Spain has more than 14,000 hotels, with independent properties underserved by enterprise software."),
    ("Traction", "€40k monthly recurring revenue\n25 pilot hotels\nInternal metrics shown for demo purposes."),
    ("Competitive landscape", "Amenitiz raised €39M in a Series B in November 2025 led by KFund.\nMews, our main competitor, has raised less than $100M in total."),
    ("Our backing", "Backed by Seedcamp and K Fund.\nFictional startup — demo deck"),
]


def main():
    doc = fitz.open()
    for title, body in PAGES:
        page = doc.new_page(width=720, height=405)
        page.insert_text((54, 95), title, fontsize=27, fontname="helv")
        page.insert_textbox(fitz.Rect(54, 135, 660, 310), body, fontsize=18, fontname="DejaVu", fontfile=str(FONT), lineheight=1.4)
        page.insert_text((54, 380), "Fictional startup — demo deck", fontsize=9, color=(0.4, 0.4, 0.4))
    doc.save(OUT)
    print(f"Generated {OUT}")


if __name__ == "__main__":
    main()
