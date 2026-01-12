#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import requests
from datetime import datetime, timezone, timedelta

# 配置 - 优先读取 GitHub Secrets
DASHBOARD_URL = 'https://dashboard.katabump.com'
SERVER_ID = os.environ.get('KATA_SERVER_ID', '201692')
KATA_EMAIL = os.environ.get('KATA_EMAIL', '')
KATA_PASSWORD = os.environ.get('KATA_PASSWORD', '')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
TG_USER_ID = os.environ.get('TG_USER_ID', '') # 统一变量名
EXECUTOR_NAME = os.environ.get('EXECUTOR_NAME', 'GitHub Actions')

def log(msg):
    tz = timezone(timedelta(hours=8))
    t = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{t}] {msg}')

def send_telegram(message):
    if not TG_BOT_TOKEN or not TG_USER_ID:
        log('⚠️ 未配置 TG 通知变量')
        return False
    try:
        url = f'https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage'
        payload = {'chat_id': TG_USER_ID, 'text': message, 'parse_mode': 'HTML'}
        requests.post(url, json=payload, timeout=30)
        log('✅ Telegram 通知已发送')
        return True
    except Exception as e:
        log(f'❌ Telegram 发送失败: {e}')
    return False

def get_expiry(html):
    # 增强版正则：尝试匹配多种可能的日期显示方式
    patterns = [
        r'Expiry[\s\S]*?(\d{4}-\d{2}-\d{2})',
        r'expires in (\d+) days',
        r'(\d{4}-\d{2}-\d{2})' 
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m: return m.group(1)
    return None

def run():
    log(f'🚀 开始执行 - 服务器 ID: {SERVER_ID}')
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    
    try:
        # 1. 登录
        session.get(f'{DASHBOARD_URL}/auth/login')
        login_resp = session.post(
            f'{DASHBOARD_URL}/auth/login',
            data={'email': KATA_EMAIL, 'password': KATA_PASSWORD, 'remember': 'true'}
        )
        if '/auth/login' in login_resp.url: raise Exception('登录失败')
        log('✅ 登录成功')
        
        # 2. 检查页面
        page = session.get(f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}')
        expiry = get_expiry(page.text)
        log(f'📅 抓取到期日期: {expiry or "失败"}')

        # 3. 强制尝试续订 (无论日期抓取是否成功，都尝试点一下按钮)
        log('🔄 正在发送续订请求...')
        csrf_m = re.search(r'name=["\']csrf["\'][^>]*value=["\']([^"\']+)["\']', page.text)
        csrf = csrf_m.group(1) if csrf_m else ""
        
        renew_resp = session.post(
            f'{DASHBOARD_URL}/api-client/renew?id={SERVER_ID}',
            data={'csrf': csrf},
            headers={'Referer': f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}'},
            allow_redirects=False
        )
        
        # 4. 判定结果
        location = renew_resp.headers.get('Location', '')
        if 'renew=success' in location:
            log('🎉 自动续订成功！')
            send_telegram(f'✅ <b>KataBump 自动续订成功</b>\n服务器: {SERVER_ID}')
        elif 'error=captcha' in location:
            log('❌ 需要验证码')
            send_telegram(f'⚠️ <b>KataBump 需要手动验证</b>\n服务器: {SERVER_ID}\n原因: 触发了人机验证，请手动登录操作一次。')
        else:
            log(f'📥 响应码: {renew_resp.status_code}，目前可能无需续订。')

    except Exception as e:
        log(f'❌ 执行出错: {e}')
        send_telegram(f'❌ <b>KataBump 脚本报错</b>\n错误信息: {e}')

if __name__ == '__main__':
    # 脚本开始运行就发个通知（你之前的需求）
    send_telegram("🚀 <b>KataBump 保活脚本开始工作</b>")
    run()
    log('🏁 任务完成')
