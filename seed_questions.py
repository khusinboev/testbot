#!/usr/bin/env python3
"""
Question seeding script for DTM Test Bot
Adds sample questions to the database for testing
"""

from database.db import Session, init_db
from database.models import Question, Subject
import random

def seed_questions():
    """Seed sample questions for each subject"""

    # Sample questions data
    questions_data = {
        1: [  # Matematika
            {
                "text_uz": "2 + 2 nechaga teng?",
                "text_oz": "2 + 2 neçä teng?",
                "text_ru": "2 + 2 сколько равно?",
                "option_a": "3",
                "option_b": "4",
                "option_c": "5",
                "option_d": "6",
                "correct_answer": "B"
            },
            {
                "text_uz": "Kvadratning perimetri P=16 sm. Uning tomoni a=?",
                "text_oz": "Kvadratning perimetri P=16 sm. Uning tomoni a=?",
                "text_ru": "Периметр квадрата P=16 см. Его сторона a=?",
                "option_a": "2 sm",
                "option_b": "4 sm",
                "option_c": "8 sm",
                "option_d": "16 sm",
                "correct_answer": "B"
            },
            {
                "text_uz": "x² - 4x + 4 = 0 tenglamaning ildizlari?",
                "text_oz": "x² - 4x + 4 = 0 teñlemanın ildizleri?",
                "text_ru": "Корни уравнения x² - 4x + 4 = 0?",
                "option_a": "x=2",
                "option_b": "x=-2",
                "option_c": "x=2, x=2",
                "option_d": "x=-2, x=-2",
                "correct_answer": "C"
            }
        ],
        2: [  # Fizika
            {
                "text_uz": "Yerning tortishish kuchi qanday kuch?",
                "text_oz": "Yerning tortışış küşi qanday küş?",
                "text_ru": "Сила притяжения Земли - это какая сила?",
                "option_a": "Mexanik kuch",
                "option_b": "Elektromagnit kuch",
                "option_c": "Gravitasiya kuch",
                "option_d": "Yadro kuch",
                "correct_answer": "C"
            },
            {
                "text_uz": "Svobodan tushayotgan jismining tezlanishi?",
                "text_oz": "Svobodan tüşayotğan jismining tezlanışı?",
                "text_ru": "Ускорение свободно падающего тела?",
                "option_a": "0 m/s²",
                "option_b": "9.8 m/s²",
                "option_c": "10 m/s²",
                "option_d": "1 m/s²",
                "correct_answer": "B"
            }
        ],
        3: [  # Kimyo
            {
                "text_uz": "Suvning kimyoviy formulasi?",
                "text_oz": "Suvning kimyoviy formulası?",
                "text_ru": "Химическая формула воды?",
                "option_a": "H2",
                "option_b": "O2",
                "option_c": "H2O",
                "option_d": "CO2",
                "correct_answer": "C"
            },
            {
                "text_uz": "pH qiymati 7 bo'lgan eritma qanday?",
                "text_oz": "pH qiymati 7 bolğan eritma qanday?",
                "text_ru": "Раствор с pH=7 является?",
                "option_a": "Kislotali",
                "option_b": "Asosli",
                "option_c": "Neytral",
                "option_d": "Tuzli",
                "correct_answer": "C"
            }
        ],
        4: [  # Biologiya
            {
                "text_uz": "Odamda qancha juft ribalar bor?",
                "text_oz": "Odamda qança juft ribalar bar?",
                "text_ru": "Сколько пар рёбер у человека?",
                "option_a": "10",
                "option_b": "12",
                "option_c": "14",
                "option_d": "16",
                "correct_answer": "B"
            },
            {
                "text_uz": "Fotosintez qaysi organoidda sodir bo'ladi?",
                "text_oz": "Fotosintez qaysi organoidda sodir boladi?",
                "text_ru": "В каком органелле происходит фотосинтез?",
                "option_a": "Yadro",
                "option_b": "Mitoxondriya",
                "option_c": "Xloroplast",
                "option_d": "Lizosoma",
                "correct_answer": "C"
            }
        ],
        5: [  # Tarix
            {
                "text_uz": "O'zbekiston qachon mustaqil bo'ldi?",
                "text_oz": "Özbekiston qaçan mustaqil boldi?",
                "text_ru": "Когда Узбекистан стал независимым?",
                "option_a": "1990",
                "option_b": "1991",
                "option_c": "1992",
                "option_d": "1993",
                "correct_answer": "B"
            },
            {
                "text_uz": "Amir Temur qaysi yilda vafot etgan?",
                "text_oz": "Amir Temur qaysi yılda vafot etgan?",
                "text_ru": "В каком году умер Амир Темур?",
                "option_a": "1404",
                "option_b": "1405",
                "option_c": "1406",
                "option_d": "1407",
                "correct_answer": "B"
            }
        ],
        6: [  # Ona tili
            {
                "text_uz": "Qaysi so'z ot so'zi hisoblanadi?",
                "text_oz": "Qaysi söz ot sözi hisoblanadi?",
                "text_ru": "Какое слово является именем существительным?",
                "option_a": "Yozmoq",
                "option_b": "Kitob",
                "option_c": "Chiroyli",
                "option_d": "Tez",
                "correct_answer": "B"
            },
            {
                "text_uz": "'Daraxt' so'zi qaysi qismga kiradi?",
                "text_oz": "'Daraxt' sözi qaysi qismğa kiradi?",
                "text_ru": "К какой части речи относится слово 'дерево'?",
                "option_a": "Sifat",
                "option_b": "Ot",
                "option_c": "Fe'l",
                "option_d": "Ravish",
                "correct_answer": "B"
            }
        ],
        7: [  # Adabiyot
            {
                "text_uz": "Alisher Navoiy qaysi asr shoiri?",
                "text_oz": "Alisher Navoiy qaysi asr şoiri?",
                "text_ru": "Поэт какого века Алишеp Навои?",
                "option_a": "14-asr",
                "option_b": "15-asr",
                "option_c": "16-asr",
                "option_d": "17-asr",
                "correct_answer": "B"
            },
            {
                "text_uz": "'Layli va Majnun' dostonini kim yozgan?",
                "text_oz": "'Layli va Majnun' dostonini kim yazğan?",
                "text_ru": "Кто написал дастан 'Лейли и Меджнун'?",
                "option_a": "Alisher Navoiy",
                "option_b": "Abdulla Qodiriy",
                "option_c": "Cho'lpon",
                "option_d": "Hamza",
                "correct_answer": "A"
            }
        ],
        8: [  # Geografiya
            {
                "text_uz": "O'zbekistonning poytaxti qayer?",
                "text_oz": "Özbekistonning poytaxti qayer?",
                "text_ru": "Столица Узбекистана где?",
                "option_a": "Samarqand",
                "option_b": "Buxoro",
                "option_c": "Toshkent",
                "option_d": "Andijon",
                "correct_answer": "C"
            },
            {
                "text_uz": "Qaysi daryo O'zbekiston hududidan o'tadi?",
                "text_oz": "Qaysi daryo Özbekiston hududidan ötadi?",
                "text_ru": "Какая река протекает по территории Узбекистана?",
                "option_a": "Volga",
                "option_b": "Amudaryo",
                "option_c": "Don",
                "option_d": "Kama",
                "correct_answer": "B"
            }
        ],
        9: [  # Ingliz tili
            {
                "text_uz": "'Kitob' so'zining inglizchasi?",
                "text_oz": "'Kitob' sözining inglizçesi?",
                "text_ru": "Английский перевод слова 'книга'?",
                "option_a": "Book",
                "option_b": "Pen",
                "option_c": "Table",
                "option_d": "Chair",
                "correct_answer": "A"
            },
            {
                "text_uz": "What is your name? - ...",
                "text_oz": "What is your name? - ...",
                "text_ru": "What is your name? - ...",
                "option_a": "I am fine",
                "option_b": "My name is...",
                "option_c": "I am 20",
                "option_d": "I live here",
                "correct_answer": "B"
            }
        ],
        10: [  # Rus tili
            {
                "text_uz": "'Kitob' so'zining ruschasi?",
                "text_oz": "'Kitob' sözining rusçesi?",
                "text_ru": "Русский перевод слова 'книга'?",
                "option_a": "Книга",
                "option_b": "Ручка",
                "option_c": "Стол",
                "option_d": "Стул",
                "correct_answer": "A"
            },
            {
                "text_uz": "Как вас зовут? - ...",
                "text_oz": "Как вас зовут? - ...",
                "text_ru": "Как вас зовут? - ...",
                "option_a": "Мне хорошо",
                "option_b": "Меня зовут...",
                "option_c": "Мне 20 лет",
                "option_d": "Я живу здесь",
                "correct_answer": "B"
            }
        ]
    }

    db = Session()

    try:
        total_questions = 0

        for subject_id, questions in questions_data.items():
            subject = db.query(Subject).filter(Subject.id == subject_id).first()

            if not subject:
                print(f"❌ Fan {subject_id} topilmadi!")
                continue

            for q_data in questions:
                question = Question(
                    subject_id=subject_id,
                    text_uz=q_data["text_uz"],
                    text_oz=q_data["text_oz"],
                    text_ru=q_data["text_ru"],
                    option_a=q_data["option_a"],
                    option_b=q_data["option_b"],
                    option_c=q_data["option_c"],
                    option_d=q_data["option_d"],
                    correct_answer=q_data["correct_answer"],
                    difficulty=random.choice(['easy', 'medium', 'hard'])
                )
                db.add(question)
                total_questions += 1

        db.commit()
        print(f"✅ {total_questions} ta savol muvaffaqiyatli qo'shildi!")

        # Update subject question counts
        for subject in db.query(Subject).all():
            count = db.query(Question).filter(Question.subject_id == subject.id).count()
            subject.question_count = count

        db.commit()
        print("✅ Fanlarning savol sonlari yangilandi!")

    except Exception as e:
        db.rollback()
        print(f"❌ Xato: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    print("📚 DTM Test Bot - Savollarni qo'shish...")
    init_db()  # Initialize database
    seed_questions()
    print("🎉 Tayyor!")