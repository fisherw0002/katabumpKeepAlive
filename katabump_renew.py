#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import requests
from datetime import datetime, timezone, timedelta

# ================= 配置区 =================
DASHBOARD_URL = 'https://dashboard.katabump.com'
SERVER_ID = os.environ.get('KATA_SERVER_ID', '201692')
KATA_EMAIL = os.environ.get('KATA_EMAIL', '')
KATA_PASSWORD = os.environ.get('KATA_PASSWORD', '')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
TG_CHAT_ID = os.environ.get('TG_USER_ID', '') 

def log(msg):
    tz = timezone(timedelta(hours=8))
    t = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{t}] {msg}')

def send_telegram(message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return False
    try:
        requests.post(
            f'https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage',
            json={'chat_id': TG_CHAT_ID, 'text': message, 'parse_mode': 'HTML'},
            timeout=30
        )
        return True
    except:
        return False

def get_expiry(html):
    # 增强版正则
    patterns = [
        r'Expiry[\s\S]{0,200}?>\s*(\d{4}-\d{2}-\d{2})',
        r'(\d{4}-\d{2}-\d{2})'
    ]
    for p in patterns:
        match = re.search(p, html, re.IGNORECASE)
        if match: return match.group(1)
    return None

def run():
    log(f'🚀 开始保活检查 - 目标 ID: {SERVER_ID}')
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    })
    
    try:
        # 1. 登录
        log('🔐 正在登录...')
        session.get(f'{DASHBOARD_URL}/auth/login', timeout=30)
        login_resp = session.post(
            f'{DASHBOARD_URL}/auth/login',
            data={'email': KATA_EMAIL, 'password': KATA_PASSWORD, 'remember': 'true'},
            headers={'Referer': f'{DASHBOARD_URL}/auth/login'},
            timeout=30,
            allow_redirects=True
        )
        
        if '/auth/login' in login_resp.url:
            raise Exception("登录失败：请检查 Secrets 账号密码")
        log('✅ 登录成功')
        
        # 2. 获取管理页
        target_page = f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}'
        server_page = session.get(target_page, timeout=30)
        html_content = server_page.text

        # 【核心调试代码】：打印 Expiry 附近的内容
        if "Expiry" in html_content:
            pos = html_content.find("Expiry")
            # 取关键字前后 250 个字符
            snippet = html_content[max(0, pos-50) : pos+250]
            log(f"🛠 [DEBUG INFO] 网页日期源码片段: \n{snippet}")
        else:
            log("🛠 [DEBUG INFO] 页面中未找到 Expiry 关键字")

        expiry = get_expiry(html_content)
        log(f'📅 抓取到期日期: {expiry or "未知"}')

        # 3. 尝试续订
        csrf_token = None
        csrf_m = re.search(r'name=["\']csrf["\'][^>]*value=["\']([^"\']+)["\']', html_content)
        if csrf_m: csrf_token = csrf_m.group(1)
        
        log('🔄 发送续订请求...')
        api_resp = session.post(
            f'{DASHBOARD_URL}/api-client/renew?id={SERVER_ID}',
            data={'csrf': csrf_token} if csrf_token else {},
            headers={'Referer': target_page},
            timeout=30, 
            allow_redirects=False
        )
        
        location = api_resp.headers.get('Location', '')
        
        if 'renew=success' in location:
            send_telegram(f'✅ <b>KataBump 续订成功</b>\nID: {SERVER_ID}\n到期日: {expiry or "已刷新"}')
            log('🎉 续订成功！')
        elif 'error=captcha' in location:
            send_telegram(f'⚠️ <b>需要验证码</b>\nID: {SERVER_ID}')
            log('❌ 需手动验证')
        elif api_resp.status_code == 400:
            log('⏳ 尚未到续订时间 (400)')
            # 日期抓不到时发个报告，抓到了就不发，减少骚扰
            if not expiry:
                send_telegram(f'ℹ️ <b>状态报告</b>\nID: {SERVER_ID}\n登录成功但日期抓取失败')
        else:
            log(f'📥 响应码: {api_resp.status_code}，Location: {location}')

    except Exception as e:
        log(f'❌ 报错: {e}')
        send_telegram(f'❌ <b>报错通知</b>\nID: {SERVER_ID}\n错误: {e}')

if __name__ == '__main__':
    # 保持心跳通知
    send_telegram(f'🕒 <b>保活检查启动</b>\nID: {SERVER_ID}')
    run()
