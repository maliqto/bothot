import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
import os
import uuid
import time
import threading
import datetime
from dotenv import load_dotenv

load_dotenv()


token = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(token)


ADMIN_IDS = ['ID_ADMIN', 'ID_ADMIN2']


ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}


# Formato: {chat_id: {'payment_id': id, 'plan_type': tipo, 'timestamp': hora}}
pending_payments = {}


plan_descriptions = {
    "10": {"name": "Semanal", "duration": 7},
    "30": {"name": "Mensal", "duration": 30},
    "60": {"name": "Trimestral", "duration": 90},
    "100": {"name": "Vitalício", "duration": 36500},  # 100 anos (praticamente vitalício)
    "18": {"name": "2 meses", "duration": 60},
    "25": {"name": "3 meses", "duration": 90}
}


SUBSCRIBERS_FILE = 'subscribers.json'
USERS_FILE = 'users.json'


def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError:
            return {}
    return {}


def save_subscribers(subscribers):
    with open(SUBSCRIBERS_FILE, 'w') as file:
        json.dump(subscribers, file, indent=2)


def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError:
            return {}
    return {}


def save_users(users):
    with open(USERS_FILE, 'w') as file:
        json.dump(users, file, indent=2)


subscribers = load_subscribers()
users = load_users()


def is_admin(user_id):
    return str(user_id) in ADMIN_IDS


def register_user(user):
    user_id = str(user.id)
    if user_id not in users:
        users[user_id] = {
            "user_id": user_id,
            "username": user.username or "Não definido",
            "first_name": user.first_name or "Não definido",
            "last_name": user.last_name or "Não definido",
            "registered_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_activity": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users(users)
    else:
       
        users[user_id]["last_activity"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if user.username and users[user_id]["username"] != user.username:
            users[user_id]["username"] = user.username
        save_users(users)


@bot.message_handler(commands=['admin'])
def admin_menu(message):
   
    register_user(message.from_user)
    
    chat_id = message.chat.id
    
    if not is_admin(chat_id):
        bot.send_message(chat_id, "Você não tem permissão para acessar esta área.")
        return
    
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("👥 Usuários", callback_data="admin_users"),
        InlineKeyboardButton("📢 Mensagem Global", callback_data="admin_broadcast"),
        InlineKeyboardButton("📊 Estatísticas", callback_data="admin_stats"),
        InlineKeyboardButton("📋 Lista de Todos Usuários", callback_data="admin_all_users")
    )
    bot.send_message(chat_id, "🔐 *Painel do Administrador*\n\nSelecione uma opção abaixo:", reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback(call):
    chat_id = call.message.chat.id
    
    if not is_admin(chat_id):
        bot.answer_callback_query(call.id, "Acesso negado")
        return
    
    if call.data == "admin_users":
        
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
       
        recent_users = list(subscribers.keys())[-10:] if subscribers else []
        
        if recent_users:
            for user_id in recent_users:
                user_info = subscribers[user_id]
                plan_name = user_info.get("plan_name", "Desconhecido")
                
               
                username = "Sem username"
                if user_id in users:
                    username = users[user_id].get("username", "Sem username")
                
               
                display_name = f"@{username}" if username != "Sem username" and username != "Não definido" else f"Usuario {user_id[:5]}..."
                markup.add(InlineKeyboardButton(f"👤 {display_name} - {plan_name}", callback_data=f"user_info_{user_id}"))
        else:
            bot.answer_callback_query(call.id, "Nenhum assinante encontrado")
            return
        
        markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="admin_back"))
        bot.edit_message_text("Selecione um assinante para ver detalhes:", chat_id, call.message.message_id, reply_markup=markup)
    
    elif call.data == "admin_all_users":
        
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        
        
        recent_users = list(users.keys())[-10:] if users else []
        
        if recent_users:
            for user_id in recent_users:
                user_info = users[user_id]
                username = user_info.get("username", "Sem username")
                display_name = f"@{username}" if username != "Sem username" and username != "Não definido" else f"Usuario {user_id[:5]}..."
                markup.add(InlineKeyboardButton(f"👤 {display_name}", callback_data=f"all_user_info_{user_id}"))
        else:
            bot.answer_callback_query(call.id, "Nenhum usuário encontrado")
            return
        
        markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="admin_back"))
        bot.edit_message_text("Selecione um usuário para ver detalhes:", chat_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("all_user_info_"))
def all_user_info_callback(call):
    chat_id = call.message.chat.id
    
    if not is_admin(chat_id):
        bot.answer_callback_query(call.id, "Acesso negado")
        return
    
    user_id = call.data.replace("all_user_info_", "")
    
    if user_id in users:
        user_data = users[user_id]
        username = user_data.get('username', 'Não definido')
        
    
        is_subscriber = user_id in subscribers
        subscription_status = "Não é assinante"
        
        if is_subscriber:
            sub_data = subscribers[user_id]
            if sub_data.get("is_active", False):
                expiry_date = datetime.datetime.strptime(sub_data.get("expiry_date", "2023-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
                subscription_status = f"✅ Plano {sub_data.get('plan_name', 'Desconhecido')} ativo até {expiry_date.strftime('%d/%m/%Y')}"
            else:
                subscription_status = "⛔ Assinatura expirada"
        
     
        registered_at = datetime.datetime.strptime(user_data.get("registered_at", "2023-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
        last_activity = datetime.datetime.strptime(user_data.get("last_activity", "2023-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
        
        user_info = (
            f"*👤 Informações do Usuário*\n\n"
            f"*ID:* `{user_id}`\n"
            f"*Username:* @{username}\n"
            f"*Nome:* {user_data.get('first_name', 'Não definido')} {user_data.get('last_name', 'Não definido')}\n"
            f"*Registrado em:* {registered_at.strftime('%d/%m/%Y %H:%M')}\n"
            f"*Última atividade:* {last_activity.strftime('%d/%m/%Y %H:%M')}\n"
            f"*Status:* {subscription_status}\n"
        )
        
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        
        user_profile_url = f"tg://user?id={user_id}"
        markup.add(InlineKeyboardButton("🗣️ Abrir Chat", url=user_profile_url))
        markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="admin_all_users"))
        
        bot.edit_message_text(user_info, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "Usuário não encontrado")


@bot.callback_query_handler(func=lambda call: call.data.startswith("user_info_"))
def user_info_callback(call):
    chat_id = call.message.chat.id
    
    if not is_admin(chat_id):
        bot.answer_callback_query(call.id, "Acesso negado")
        return
    
    user_id = call.data.replace("user_info_", "")
    
    if user_id in subscribers:
        user_data = subscribers[user_id]
        
       
        username = "Não definido"
        if user_id in users:
            username = users[user_id].get("username", "Não definido")
        
        
        start_date = datetime.datetime.strptime(user_data.get("start_date", "2023-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
        expiry_date = datetime.datetime.strptime(user_data.get("expiry_date", "2023-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
        
        user_info = (
            f"*👤 Informações do Usuário*\n\n"
            f"*ID:* `{user_id}`\n"
            f"*Username:* @{username}\n"
            f"*Plano:* {user_data.get('plan_name', 'Desconhecido')}\n"
            f"*Status:* {'✅ Ativo' if user_data.get('is_active', False) else '⛔ Inativo'}\n"
            f"*Início:* {start_date.strftime('%d/%m/%Y')}\n"
            f"*Expira em:* {expiry_date.strftime('%d/%m/%Y')}\n"
            f"*Valor:* R$ {user_data.get('amount', '0')},00\n"
        )
        
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        
       
        user_profile_url = f"tg://user?id={user_id}"
        markup.add(InlineKeyboardButton("🗣️ Abrir Chat", url=user_profile_url))
        
        markup.add(
            InlineKeyboardButton("🔄 Renovar Plano", callback_data=f"renew_user_{user_id}"),
            InlineKeyboardButton("❌ Cancelar Plano", callback_data=f"cancel_user_{user_id}"),
            InlineKeyboardButton("🔙 Voltar", callback_data="admin_users")
        )
        bot.edit_message_text(user_info, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "Usuário não encontrado")


@bot.message_handler(commands=['start'])
def send_welcome(message):
   
    register_user(message.from_user)
    
   
    user_id = message.from_user.id
    username = message.from_user.username or "Não definido"
    first_name = message.from_user.first_name or "Não definido"
    
   
    subscription_status = "❌ Sem plano ativo"
    if str(user_id) in subscribers and subscribers[str(user_id)].get("is_active", False):
        plan_name = subscribers[str(user_id)].get("plan_name", "Desconhecido")
        expiry_date = datetime.datetime.strptime(subscribers[str(user_id)]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        days_left = (expiry_date - datetime.datetime.now()).days
        subscription_status = f"✅ Plano {plan_name} ativo - {days_left} dias restantes"
    
    
    welcome_text = (
        f"<b>Olá, {first_name}!</b>\n\n"
        "<pre>🕊 SUAS INFORMAÇÕES:</pre>\n"
        f"<pre>• Usuário: @{username}</pre>\n"
        f"<pre>• ID: {user_id}</pre>\n"
        f"<pre>• Status: {subscription_status}</pre>\n\n"
        "<b>Escolha uma opção abaixo:</b>"
    )
    
  
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("PRÉVIAS 👀", callback_data="opt1"),
        InlineKeyboardButton("VIP 💕", callback_data="opt2"),
        InlineKeyboardButton("SUPORTE 👨‍💻", callback_data="opt3")
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "confirm_broadcast")
def confirm_broadcast(call):
    chat_id = call.message.chat.id
    
    if not is_admin(chat_id):
        bot.answer_callback_query(call.id, "Acesso negado")
        return
    
  
    global broadcast_text
    
    if not broadcast_text:
        bot.answer_callback_query(call.id, "Erro: mensagem não encontrada")
        return
    
 
    bot.edit_message_text("📤 *Enviando mensagem global...*", chat_id, call.message.message_id, parse_mode="Markdown")
    
  
    success_count = 0
    fail_count = 0
    
    
    for user_id in users:
        try:
            bot.send_message(int(user_id), f"📢 *Comunicado Oficial:*\n\n{broadcast_text}", parse_mode="Markdown")
            success_count += 1
            time.sleep(0.1)  # Pequeno delay para evitar limites de API
        except Exception as e:
            print(f"Erro ao enviar mensagem para {user_id}: {e}")
            fail_count += 1
    
   
    bot.send_message(
        chat_id, 
        f"📊 *Relatório de Envio:*\n\n"
        f"✅ *Enviados com sucesso:* {success_count}\n"
        f"❌ *Falhas:* {fail_count}\n\n"
        f"*Total de destinatários:* {len(users)}",
        parse_mode="Markdown"
    )
    
   
    broadcast_text = None

@bot.callback_query_handler(func=lambda call: call.data in ["opt1", "opt2", "opt3"])
def menu_pagamento(call):
    
    register_user(call.from_user)
    
    if call.data == "opt1":  
       
        channel_url = "channel_url_previas"
        
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Acessar Canal", url=channel_url))
        markup.add(InlineKeyboardButton("Voltar ao Menu", callback_data="back_to_menu"))
        
        bot.edit_message_text("Clique no botão abaixo para acessar o canal:", 
                             call.message.chat.id, 
                             call.message.message_id, 
                             reply_markup=markup)
    
    elif call.data == "opt2":  # VIP 💕
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        markup.add(
            InlineKeyboardButton("Semanal - R$ 10,00", callback_data="pay_10_vip_semanal"),
            InlineKeyboardButton("Mensal - R$ 30,00", callback_data="pay_30_vip_mensal"),
            InlineKeyboardButton("Trimestral - R$ 60,00", callback_data="pay_60_vip_trimestral"),
            InlineKeyboardButton("Vitalício - R$ 100,00", callback_data="pay_100_vip_vitalicio")
        )
        markup.add(InlineKeyboardButton("Voltar ao Menu", callback_data="back_to_menu"))
        bot.edit_message_text("Escolha um plano VIP 💕:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "opt3":
        # Link para o suporte
        support_url = "link_suporta_or_account_support"
        
       
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Abrir Chat de Suporte", url=support_url))
        markup.add(InlineKeyboardButton("Voltar ao Menu", callback_data="back_to_menu"))
        
    if message.text == '/mensagemglobal':
        bot.send_message(chat_id, "Use o comando seguido da mensagem que deseja enviar.\n\nExemplo: `/mensagemglobal Olá a todos!`", parse_mode="Markdown")
        return
    
    
    broadcast_message = message.text.replace('/mensagemglobal', '', 1).strip()
    
 
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("✅ Sim, enviar", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_broadcast")
    )
    
   
    global broadcast_text
    broadcast_text = broadcast_message
    
    bot.send_message(
        chat_id, 
        f"*Prévia da Mensagem:*\n\n{broadcast_message}\n\n📢 *Confirma o envio desta mensagem para TODOS os usuários?*",
        parse_mode="Markdown",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "cancel_broadcast")
def cancel_broadcast(call):
    chat_id = call.message.chat.id
    
    if not is_admin(chat_id):
        bot.answer_callback_query(call.id, "Acesso negado")
        return
    
    
    global broadcast_text
    broadcast_text = None
    
    bot.edit_message_text("❌ Envio de mensagem global cancelado.", chat_id, call.message.message_id)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    
    user_id = message.from_user.id
    username = message.from_user.username or "Não definido"
    first_name = message.from_user.first_name or "Não definido"
    
    
    subscription_status = "❌ Sem plano ativo"
    if str(user_id) in subscribers and subscribers[str(user_id)].get("is_active", False):
        plan_name = subscribers[str(user_id)].get("plan_name", "Desconhecido")
        expiry_date = datetime.datetime.strptime(subscribers[str(user_id)]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        days_left = (expiry_date - datetime.datetime.now()).days
        subscription_status = f"✅ Plano {plan_name} ativo - {days_left} dias restantes"
    
    
    welcome_text = (
        f"<b>Olá, {first_name}!</b>\n\n"
        "<pre>🕊 SUAS INFORMAÇÕES:</pre>\n"
        f"<pre>• Usuário: @{username}</pre>\n"
        f"<pre>• ID: {user_id}</pre>\n"
        f"<pre>• Status: {subscription_status}</pre>\n\n"
        "<b>Escolha uma opção abaixo:</b>"
    )
    
    
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("PRÉVIAS 👀", callback_data="opt1"),
        InlineKeyboardButton("VIP 💕", callback_data="opt2"),
        InlineKeyboardButton("SUPORTE 👨‍💻", callback_data="opt3")
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data in ["opt1", "opt2", "opt3"])
def menu_pagamento(call):
    if call.data == "opt1":  # Opção 1
        
        channel_url = "https://t.me/canal_previas"
        
      
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Acessar Canal", url=channel_url))
        markup.add(InlineKeyboardButton("Voltar ao Menu", callback_data="back_to_menu"))
        
        bot.edit_message_text("Clique no botão abaixo para acessar o canal:", 
                             call.message.chat.id, 
                             call.message.message_id, 
                             reply_markup=markup)
    
    elif call.data == "opt2":  # VIP 💕
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        markup.add(
            InlineKeyboardButton("Semanal - R$ 10,00", callback_data="pay_10_vip_semanal"),
            InlineKeyboardButton("Mensal - R$ 30,00", callback_data="pay_30_vip_mensal"),
            InlineKeyboardButton("Trimestral - R$ 60,00", callback_data="pay_60_vip_trimestral"),
            InlineKeyboardButton("Vitalício - R$ 100,00", callback_data="pay_100_vip_vitalicio")
        )
        markup.add(InlineKeyboardButton("Voltar ao Menu", callback_data="back_to_menu"))
        bot.edit_message_text("Escolha um plano VIP 💕:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "opt3":
        # Link para o suporte
        support_url = "https://t.me/suporte_bot"
        
       
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Abrir Chat de Suporte", url=support_url))
        markup.add(InlineKeyboardButton("Voltar ao Menu", callback_data="back_to_menu"))
        
        bot.edit_message_text("Clique no botão abaixo para abrir o chat de suporte:", 
                             call.message.chat.id, 
                             call.message.message_id, 
                             reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "Opção inválida")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("PRÉVIAS 👀", callback_data="opt1"),
        InlineKeyboardButton("VIP 💕", callback_data="opt2"),
        InlineKeyboardButton("SUPORTE 👨‍💻", callback_data="opt3")
    )
    bot.edit_message_text("Escolha uma opção:", call.message.chat.id, call.message.message_id, reply_markup=markup)


def check_payment_status(payment_id, chat_id, plan_type):
    try:
        response = requests.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            payment_info = response.json()
            status = payment_info.get('status', '')
            
            if status == 'approved':
                # Pagamento aprovado
                amount = pending_payments[chat_id]["amount"]
                plan_info = plan_descriptions.get(amount, {"name": "Plano", "duration": 30})
                plan_name = plan_info["name"]
                duration = plan_info["duration"]
                
                # Calcular data de expiração
                start_date = datetime.datetime.now()
                expiry_date = start_date + datetime.timedelta(days=duration)
                
                # Registrar o usuário como inscrito
                user_id = str(chat_id)
                subscribers[user_id] = {
                    "user_id": user_id,
                    "plan_type": plan_type,
                    "plan_name": plan_name,
                    "amount": amount,
                    "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "expiry_date": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "payment_id": payment_id,
                    "is_active": True
                }
                
                
                save_subscribers(subscribers)
                
                # URL específica para acessar o grupo VIP
                group_url = "https://t.me/grupo_vip"
                
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("Entrar no Grupo VIP", url=group_url))
                
           
                bot.send_message(
                    chat_id, 
                    f"✅ *Pagamento Aprovado!*\n\n"
                    f"Seu plano *{plan_name}* foi ativado com sucesso.\n\n"
                    f"📅 *Início:* {start_date.strftime('%d/%m/%Y')}\n"
                    f"📅 *Validade até:* {expiry_date.strftime('%d/%m/%Y')}\n\n"
                    f"Clique no botão abaixo para acessar o grupo VIP:",
                    parse_mode="Markdown",
                    reply_markup=markup
                )
                
                
                if chat_id in pending_payments:
                    del pending_payments[chat_id]
                
                return True
            
            elif status == 'rejected' or status == 'cancelled':
                # Pagamento rejeitado ou cancelado
                bot.send_message(
                    chat_id, 
                    "❌ *Pagamento Rejeitado ou Cancelado*\n\n"
                    "Infelizmente seu pagamento não foi aprovado. "
                    "Por favor, tente novamente ou use outro método de pagamento.",
                    parse_mode="Markdown"
                )
                
               
                if chat_id in pending_payments:
                    del pending_payments[chat_id]
                
                return True
            
            elif status == 'pending':
              
                return False
    
    except Exception as e:
        print(f"Erro ao verificar status do pagamento: {e}")
        return False


def payment_checker():
    while True:
       
        pending_copy = pending_payments.copy()
        
        for chat_id, payment_data in pending_copy.items():
            payment_id = payment_data["payment_id"]
            plan_type = payment_data["plan_type"]
            timestamp = payment_data["timestamp"]
            
           
            if time.time() - timestamp > 86400:  # 24 horas em segundos
                bot.send_message(
                    chat_id,
                    "⏰ *Tempo Expirado*\n\n"
                    "O tempo para o pagamento expirou. Por favor, inicie uma nova solicitação de pagamento.",
                    parse_mode="Markdown"
                )
                del pending_payments[chat_id]
                continue
            
          
            result = check_payment_status(payment_id, chat_id, plan_type)
            
           
            if result:
                continue
       
        time.sleep(30)


def subscription_checker():
    while True:
       
        now = datetime.datetime.now()
        current_date = now.strftime("%Y-%m-%d %H:%M:%S")
        
       
        subscribers_copy = subscribers.copy()
        
        for user_id, user_data in subscribers_copy.items():
            if user_data["is_active"]:
                expiry_date_str = user_data["expiry_date"]
                expiry_date = datetime.datetime.strptime(expiry_date_str, "%Y-%m-%d %H:%M:%S")
                
                
                if now > expiry_date:
                    
                    subscribers[user_id]["is_active"] = False
                    save_subscribers(subscribers)
                    
                    
                    try:
                        markup = InlineKeyboardMarkup()
                        markup.row_width = 1
                        markup.add(
                            InlineKeyboardButton("Renovar Plano 🔄", callback_data="opt2")
                        )
                        
                        bot.send_message(
                            int(user_id),
                            f"⚠️ *PLANO EXPIRADO* ⚠️\n\n"
                            f"Seu plano *{user_data['plan_name']}* expirou em {expiry_date.strftime('%d/%m/%Y')}.\n\n"
                            f"Para continuar acessando o conteúdo VIP, por favor renove seu plano.",
                            parse_mode="Markdown",
                            reply_markup=markup
                        )
                        
                        
                        try:
                            
                            group_id = "id_cnaal"  # Exemplo: extraído de um link de convite
                            
                          
                            bot.ban_chat_member(group_id, int(user_id))
                            
                            
                            time.sleep(1)
                            bot.unban_chat_member(group_id, int(user_id), only_if_banned=True)
                            
                            print(f"Usuário {user_id} removido do grupo VIP por assinatura vencida")
                            
                           
                            for admin_id in ADMIN_IDS:
                                bot.send_message(
                                    admin_id,
                                    f"🚨 *Usuário Removido do Grupo* 🚨\n\n"
                                    f"*ID:* `{user_id}`\n"
                                    f"*Plano:* {user_data['plan_name']}\n"
                                    f"*Expirou em:* {expiry_date.strftime('%d/%m/%Y')}\n\n"
                                    f"O usuário foi automaticamente removido do grupo VIP.",
                                    parse_mode="Markdown"
                                )
                        except Exception as e:
                            print(f"Erro ao remover usuário {user_id} do grupo: {e}")
                            
                            # Notificar o administrador sobre falha na remoção
                            for admin_id in ADMIN_IDS:
                                bot.send_message(
                                    admin_id,
                                    f"⚠️ *FALHA NA REMOÇÃO AUTOMÁTICA* ⚠️\n\n"
                                    f"*ID:* `{user_id}`\n"
                                    f"*Plano:* {user_data['plan_name']}\n"
                                    f"*Expirou em:* {expiry_date.strftime('%d/%m/%Y')}\n\n"
                                    f"*Erro:* {str(e)}\n\n"
                                    f"Este usuário deve ser removido manualmente do grupo VIP.",
                                    parse_mode="Markdown"
                                )
                    except Exception as e:
                        print(f"Erro ao enviar notificação de expiração: {e}")
                
               
                days_until_expiry = (expiry_date - now).days
                if 0 < days_until_expiry <= 3 and not user_data.get("reminder_sent", False):
                    try:
                        markup = InlineKeyboardMarkup()
                        markup.row_width = 1
                        markup.add(
                            InlineKeyboardButton("Renovar Agora 🔄", callback_data="opt2")
                        )
                        
                        bot.send_message(
                            int(user_id),
                            f"⚠️ *LEMBRETE DE RENOVAÇÃO* ⚠️\n\n"
                            f"Seu plano *{user_data['plan_name']}* expira em *{days_until_expiry} dias*.\n\n"
                            f"Para continuar acessando o conteúdo VIP sem interrupções, renove seu plano antes da data de expiração.",
                            parse_mode="Markdown",
                            reply_markup=markup
                        )
                        
                        
                        subscribers[user_id]["reminder_sent"] = True
                        save_subscribers(subscribers)
                    except Exception as e:
                        print(f"Erro ao enviar lembrete de renovação: {e}")
        
       
        time.sleep(21600)  # 6 horas em segundos


payment_thread = threading.Thread(target=payment_checker, daemon=True)
payment_thread.start()

subscription_thread = threading.Thread(target=subscription_checker, daemon=True)
subscription_thread.start()


@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def process_payment(call):
    parts = call.data.split("_")
    amount = parts[1]  # Valor do pagamento
    plan_type = "_".join(parts[2:])  # Tipo do plano (ex: vip_mensal, normal_2meses)
    plan_info = plan_descriptions.get(amount, {"name": "Plano", "duration": 30})
    plan_name = plan_info["name"]
    
   
    payment_data = {
        "transaction_amount": float(amount),
        "description": f"Pagamento {plan_name}",
        "payment_method_id": "pix",
        "payer": {
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "identification": {
                "type": "CPF",
                "number": "12345678909"
            }
        }
    }
    
    try:
        
        idempotency_key = str(uuid.uuid4())
        headers = HEADERS.copy()
        headers["X-Idempotency-Key"] = idempotency_key
        
        response = requests.post(
            "https://api.mercadopago.com/v1/payments", 
            headers=headers,
            timeout=30,
            data=json.dumps(payment_data)
        )
        
       
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 201:
            payment_info = response.json()
            payment_id = payment_info.get('id')
            
            
            pending_payments[call.message.chat.id] = {
                "payment_id": payment_id,
                "plan_type": plan_type,
                "amount": amount,
                "timestamp": time.time(),
                "plan_description": plan_name
            }
            
           
            if ("point_of_interaction" in payment_info and 
                "transaction_data" in payment_info["point_of_interaction"]):
                
                transaction_data = payment_info["point_of_interaction"]["transaction_data"]
                pix_qr = transaction_data.get("qr_code", "QR Code não disponível")
                
               
                initial_message = (f"🔹 *Pagamento PIX gerado com sucesso*\n\n"
                                  f"🔹 *Plano:* {plan_name}\n"
                                  f"🔹 *Valor:* R$ {amount},00\n\n"
                                  f"⏰ *Válido por 24 horas*\n\n"
                                  f"✅ *Após o pagamento, seu acesso será liberado automaticamente*")
                
                bot.send_message(call.message.chat.id, initial_message, parse_mode="Markdown")
                
                
                if "qr_code_base64" in transaction_data:
                    try:
                        import base64
                        from io import BytesIO
                        
                       
                        image_data = base64.b64decode(transaction_data["qr_code_base64"])
                        image = BytesIO(image_data)
                        
                       
                        caption = f"*QR Code para pagamento - {plan_name}*\n\n*Código Copia e Cola:*\n`{pix_qr}`"
                        
                       
                        bot.send_photo(call.message.chat.id, image, caption=caption, parse_mode="Markdown")
                    except Exception as e:
                        print(f"Erro ao enviar QR code como imagem: {str(e)}")
                        
                        bot.send_message(call.message.chat.id, f"*Código PIX para Copia e Cola:*\n`{pix_qr}`", parse_mode="Markdown")
                else:
                   
                    bot.send_message(call.message.chat.id, f"*Código PIX para Copia e Cola:*\n`{pix_qr}`", parse_mode="Markdown")
                
            else:
                bot.send_message(call.message.chat.id, "Erro ao obter os dados do PIX. Tente novamente.")
                print("Estrutura da resposta:", payment_info)
        else:
            error_details = response.json() if response.text else "Sem detalhes disponíveis"
            bot.send_message(call.message.chat.id, "Erro ao processar o pagamento. Tente novamente.")
            print(f"Erro detalhado: {error_details}")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, "Erro ao conectar com o serviço de pagamento.")
        print(f"Exceção: {str(e)}")


@bot.message_handler(commands=['status'])
def check_status(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    
    if user_id in subscribers and subscribers[user_id]["is_active"]:
        
        user_data = subscribers[user_id]
        expiry_date = datetime.datetime.strptime(user_data["expiry_date"], "%Y-%m-%d %H:%M:%S")
        days_left = (expiry_date - datetime.datetime.now()).days
        
        bot.send_message(
            chat_id,
            f"✅ *Plano Ativo*\n\n"
            f"🔹 *Plano:* {user_data['plan_name']}\n"
            f"📅 *Expira em:* {expiry_date.strftime('%d/%m/%Y')}\n"
            f"⏳ *Dias restantes:* {max(0, days_left)}\n",
            parse_mode="Markdown"
        )
    elif chat_id in pending_payments:
        
        payment_data = pending_payments[chat_id]
        payment_id = payment_data["payment_id"]
        plan_type = payment_data["plan_type"]
        
        bot.send_message(chat_id, "Verificando o status do seu pagamento...", parse_mode="Markdown")
        check_payment_status(payment_id, chat_id, plan_type)
    else:
        
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        markup.add(
            InlineKeyboardButton("Adquirir Plano VIP 💕", callback_data="opt2")
        )
        
        bot.send_message(
            chat_id, 
            "Você não possui um plano ativo no momento.\n\n"
            "Para adquirir um plano VIP, clique no botão abaixo:", 
            reply_markup=markup
        )


@bot.message_handler(commands=['subscribers'])
def list_subscribers(message):
    admin_id = os.getenv("ADMIN_ID")
    
    if admin_id and str(message.chat.id) == admin_id:
        active_subscribers = {k: v for k, v in subscribers.items() if v.get("is_active", False)}
        
        if active_subscribers:
            response = "*Assinantes Ativos:*\n\n"
            for user_id, user_data in active_subscribers.items():
                expiry_date = datetime.datetime.strptime(user_data["expiry_date"], "%Y-%m-%d %H:%M:%S")
                response += f"👤 *Usuário:* `{user_id}`\n"
                response += f"📝 *Plano:* {user_data['plan_name']}\n"
                response += f"📅 *Expira em:* {expiry_date.strftime('%d/%m/%Y')}\n\n"
                
                
                if len(response) > 3500:
                    bot.send_message(message.chat.id, response, parse_mode="Markdown")
                    response = "*Continuação da lista:*\n\n"
            
            if response:
                bot.send_message(message.chat.id, response, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "Não há assinantes ativos no momento.", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Você não tem permissão para usar este comando.", parse_mode="Markdown")


@bot.message_handler(commands=['mensagemglobal'])
def mensagem_global_command(message):
    chat_id = message.chat.id
    
    if not is_admin(chat_id):
        bot.send_message(chat_id, "Você não tem permissão para usar este comando.")
        return
    
    
    if message.text == '/mensagemglobal':
        bot.send_message(chat_id, "Use o comando seguido da mensagem que deseja enviar.\n\nExemplo: `/mensagemglobal Olá a todos!`", parse_mode="Markdown")
        return
    
    
    broadcast_message = message.text.replace('/mensagemglobal', '', 1).strip()
    
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("✅ Sim, enviar", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_broadcast")
    )
    
   
    global broadcast_text
    broadcast_text = broadcast_message
    
    bot.send_message(
        chat_id, 
        f"*Prévia da Mensagem:*\n\n{broadcast_message}\n\n📢 *Confirma o envio desta mensagem para TODOS os usuários?*",
        parse_mode="Markdown",
        reply_markup=markup
    )


def process_broadcast_message(message):
    chat_id = message.chat.id
    
    if not is_admin(chat_id):
        return
    
    if message.text == '/cancel':
        bot.send_message(chat_id, "Envio de mensagem global cancelado.")
        return
    
  
    broadcast_message = message.text
    
   
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("✅ Sim, enviar", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_broadcast")
    )
    
  
    global broadcast_text
    broadcast_text = broadcast_message
    
    bot.send_message(
        chat_id, 
        f"*Prévia da Mensagem:*\n\n{broadcast_message}\n\n📢 *Confirma o envio desta mensagem para TODOS os usuários?*",
        parse_mode="Markdown",
        reply_markup=markup
    )

while True:
    try:
        print("Iniciando o bot...")
        bot.polling(none_stop=True, interval=1, timeout=30)
    except Exception as e:
        print(f"Erro na execução do bot: {e}")
        time.sleep(15)
