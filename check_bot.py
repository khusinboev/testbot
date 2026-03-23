#!/usr/bin/env python3
import requests
import config

try:
    response = requests.get(f'https://api.telegram.org/bot{config.BOT_TOKEN}/getMe')
    if response.status_code == 200:
        bot_info = response.json()
        print(f'🤖 Bot: @{bot_info["result"]["username"]}')
        print(f'📱 Status: ✅ Ishlayapti')
    else:
        print(f'❌ Bot javob bermayapti: {response.status_code}')
except Exception as e:
    print(f'❌ Xato: {str(e)}')