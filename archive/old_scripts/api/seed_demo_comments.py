import asyncio
from db.connection import database
from db.models import comments, users, comment_reactions
from sqlalchemy import insert, select, delete

async def seed_demo_data():
    print("🚀 Seeding high-quality demo comments...")
    await database.connect()
    
    target_id = 101280
    target_ep = 1.0
    
    demo_users = [
        {"id": "demo_1", "username": "RimuruLover", "avatar": "https://api.dicebear.com/7.x/adventurer/svg?seed=Rimuru"},
        {"id": "demo_2", "username": "AnimeExpert", "avatar": "https://api.dicebear.com/7.x/adventurer/svg?seed=Expert"},
        {"id": "demo_3", "username": "Veldora_Fan", "avatar": "https://api.dicebear.com/7.x/adventurer/svg?seed=Dragon"},
        {"id": "demo_4", "username": "NewbieWatcher", "avatar": "https://api.dicebear.com/7.x/adventurer/svg?seed=Newbie"},
    ]

    # Add extra random users for reactions
    for i in range(10):
        demo_users.append({"id": f"rand_{i}", "username": f"User_{i}", "avatar": None})

    for u in demo_users:
        q = select(users).where(users.c.id == u["id"])
        exist = await database.fetch_one(q)
        if not exist:
            await database.execute(insert(users).values(id=u["id"], username=u["username"], avatar=u.get("avatar")))

    # Root Comments
    root_comments = [
        {
            "user_id": "demo_2", "anilistId": target_id, "episodeNumber": target_ep,
            "text": "Produksi dari 8bit emang gak pernah mengecewakan. Art style-nya clean banget! 🔥",
            "timestamp_sec": 120
        },
        {
            "user_id": "demo_3", "anilistId": target_id, "episodeNumber": target_ep,
            "text": "Veldora akhirnya muncul! Tsundere dragon favorit kita semua wkwk 🐉",
            "timestamp_sec": 945
        },
        {
            "user_id": "demo_4", "anilistId": target_id, "episodeNumber": target_ep,
            "text": "Pertama kali nonton genre Isekai, semoga seru ya!",
            "timestamp_sec": 15
        }
    ]

    for c in root_comments:
        check = select(comments).where((comments.c.user_id == c["user_id"]) & (comments.c.text == c["text"]))
        exist = await database.fetch_one(check)
        if not exist:
            parent_id = await database.execute(insert(comments).values(**c))
            
            # Add some reactions
            for i in range(5):
                await database.execute(insert(comment_reactions).values(comment_id=parent_id, user_id=f"rand_{i}", emoji="🔥"))

            # Add a reply
            if c["user_id"] == "demo_2":
                await database.execute(insert(comments).values(
                    user_id="demo_1", anilistId=target_id, episodeNumber=target_ep,
                    parent_id=parent_id, text="Setuju! Pacing-nya juga pas, gak buru-buru."
                ))

    print("✅ Seed complete. Visit /watch/101280/1 to see the demo!")
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(seed_demo_data())
