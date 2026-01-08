#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KataBump 自动续订/提醒脚本
作者：七转八起
cron: 0 9,21 * * *
new Env('KataBump续订');
"""

import os
import sys
import re
import requests
from datetime import datetime, timezone, timedelta

# 配置
DASHBOARD_URL = 'https://dashboard.katabump.com'
SERVER_ID = os.environ.get('KATA_SERVER_ID', '185829')
KATA_EMAIL = os.environ.get('KATA_EMAIL', '')
KATA_PASSWORD = os.environ.get('KATA_PASSWORD', '')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
TG_CHAT_ID = os.environ.get('TG_USER_ID', '')

# 执行器配置
EXECUTOR_NAME = os.environ.get('EXECUTOR_NAME', 'https://ql.api.sld.tw')

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
        log('✅ Telegram 通知已发送')
        return True
    except Exception as e:
        log(f'❌ Telegram 错误: {e}')
    return False


def get_expiry(html):
    match = re.search(r'Expiry[\s\S]*?(\d{4}-\d{2}-\d{2})', html, re.IGNORECASE)
    return match.group(1) if match else None


def get_csrf(html):
    patterns = [
        r'<input[^>]*name=["\']csrf["\'][^>]*value=["\']([^"\']+)["\']',
        r'<input[^>]*value=["\']([^"\']+)["\'][^>]*name=["\']csrf["\']',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m and len(m.group(1)) > 10:
            return m.group(1)
    return None


def days_until(date_str):
    try:
        exp = datetime.strptime(date_str, '%Y-%m-%d')
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return (exp - today).days
    except:
        return None


def parse_renew_error(url):
    if 'renew-error' not in url:
        return None, None
    
    error_match = re.search(r'renew-error=([^&]+)', url)
    if not error_match:
        return '未知错误', None
    
    error = requests.utils.unquote(error_match.group(1).replace('+', ' '))
    
    date_match = re.search(r'as of (\d+) (\w+)', error)
    if date_match:
        day = date_match.group(1)
        month = date_match.group(2)
        return error, f'{month} {day}'
    
    return error, None


def run():
    log('🚀 KataBump 自动续订/提醒')
    log(f'🖥 服务器 ID: {SERVER_ID}')
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    
    try:
        # ========== 登录 ==========
        log('🔐 登录中...')
        session.get(f'{DASHBOARD_URL}/auth/login', timeout=30)
        
        login_resp = session.post(
            f'{DASHBOARD_URL}/auth/login',
            data={
                'email': KATA_EMAIL,
                'password': KATA_PASSWORD,
                'remember': 'true'
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': DASHBOARD_URL,
                'Referer': f'{DASHBOARD_URL}/auth/login',
            },
            timeout=30,
            allow_redirects=True
        )
        
        log(f'📍 登录后URL: {login_resp.url}')
        log(f'🍪 Cookies: {list(session.cookies.keys())}')
        
        if '/auth/login' in login_resp.url:
            raise Exception('登录失败')
        
        log('✅ 登录成功')
        
        # ========== 获取服务器信息 ==========
        server_page = session.get(f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}', timeout=30)
        url = server_page.url
        
        expiry = get_expiry(server_page.text) or '未知'
        days = days_until(expiry)
        csrf = get_csrf(server_page.text)
        
        log(f'📅 到期: {expiry} (剩余 {days} 天)')
        
        # 检查是否有续订限制
        error, renew_date = parse_renew_error(url)
        if error:
            log(f'⏳ {error}')
            
            if days is not None and days <= 2:
                send_telegram(
                    f'ℹ️ KataBump 续订提醒\n\n'
                    f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                    f'📅 到期: {expiry}\n'
                    f'⏰ 剩余: {days} 天\n'
                    f'📝 {error}\n'
                    f'💻 执行器: {EXECUTOR_NAME}\n\n'
                    f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={SERVER_ID}">查看详情</a>'
                )
            return
        
        # ========== 尝试续订 ==========
        log('🔄 尝试续订...')
        
        api_url = f'{DASHBOARD_URL}/api-client/renew?id={SERVER_ID}'
        
        api_resp = session.post(
            api_url,
            data={'csrf': csrf} if csrf else {},
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': DASHBOARD_URL,
                'Referer': f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}'
            },
            timeout=30,
            allow_redirects=False
        )
        
        log(f'📥 状态码: {api_resp.status_code}')
        
        # 检查重定向
        if api_resp.status_code == 302:
            location = api_resp.headers.get('Location', '')
            log(f'📍 重定向到: {location}')
            
            if 'renew=success' in location:
                check = session.get(f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}', timeout=30)
                new_expiry = get_expiry(check.text) or '未知'
                
                log('🎉 续订成功！')
                send_telegram(
                    f'✅ KataBump 续订成功\n\n'
                    f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                    f'📅 原到期: {expiry}\n'
                    f'📅 新到期: {new_expiry}\n'
                    f'💻 执行器: {EXECUTOR_NAME}'
                )
                return
            
            elif 'renew-error' in location:
                error, _ = parse_renew_error(location)
                log(f'⏳ {error}')
                
                if days is not None and days <= 2:
                    send_telegram(
                        f'ℹ️ KataBump 续订提醒\n\n'
                        f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                        f'📅 到期: {expiry}\n'
                        f'⏰ 剩余: {days} 天\n'
                        f'📝 {error}\n'
                        f'💻 执行器: {EXECUTOR_NAME}'
                    )
                return
            
            elif 'error=captcha' in location:
                log('❌ 需要 Captcha 验证')
                
                if days is not None and days <= 2:
                    send_telegram(
                        f'⚠️ KataBump 需要手动续订\n\n'
                        f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                        f'📅 到期: {expiry}\n'
                        f'⏰ 剩余: {days} 天\n'
                        f'❗ 自动续订需要验证码\n'
                        f'💻 执行器: {EXECUTOR_NAME}\n\n'
                        f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={SERVER_ID}">点击续订</a>'
                    )
                return
        
        # 检查响应内容
        resp_text = api_resp.text
        
        if 'captcha' in resp_text.lower():
            log('❌ 需要 Captcha 验证')
            
            if days is not None and days <= 2:
                send_telegram(
                    f'⚠️ KataBump 需要手动续订\n\n'
                    f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                    f'📅 到期: {expiry}\n'
                    f'⏰ 剩余: {days} 天\n'
                    f'❗ 自动续订需要验证码\n'
                    f'💻 执行器: {EXECUTOR_NAME}\n\n'
                    f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={SERVER_ID}">点击续订</a>'
                )
            return
        
        # 最终检查
        check = session.get(f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}', timeout=30)
        new_expiry = get_expiry(check.text) or '未知'
        
        if new_expiry > expiry:
            log('🎉 续订成功！')
            send_telegram(
                f'✅ KataBump 续订成功\n\n'
                f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                f'📅 原到期: {expiry}\n'
                f'📅 新到期: {new_expiry}\n'
                f'💻 执行器: {EXECUTOR_NAME}'
            )
        else:
            log('⚠️ 续订状态未知')
            if days is not None and days <= 2:
                send_telegram(
                    f'⚠️ KataBump 请检查续订状态\n\n'
                    f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                    f'📅 到期: {new_expiry}\n'
                    f'💻 执行器: {EXECUTOR_NAME}\n\n'
                    f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={SERVER_ID}">查看详情</a>'
                )
    
    except Exception as e:
        log(f'❌ 错误: {e}')
        send_telegram(
            f'❌ KataBump 出错\n\n'
            f'🖥 服务器: <code>{SERVER_ID}</code>\n'
            f'❗ {e}\n'
            f'💻 执行器: {EXECUTOR_NAME}'
        )
        raise


def main():
    log('=' * 50)
    log('   KataBump 自动续订/提醒脚本')
    log('=' * 50)
    
    if not KATA_EMAIL or not KATA_PASSWORD:
        log('❌ 请设置 KATA_EMAIL 和 KATA_PASSWORD')
        sys.exit(1)
    
    run()
    log('🏁 完成')


if __name__ == '__main__':
    main()