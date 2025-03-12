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

# Defina seu token do bot do Telegram
token = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(token)

# IDs dos administradores
ADMIN_IDS = ['6683824531', '7330315104']

# Chaves do Mercado Pago (use variáveis de ambiente para segurança)
ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# Dicionário para armazenar os pagamentos pendentes
# Formato: {chat_id: {'payment_id': id, 'plan_type': tipo, 'timestamp': hora}}
pending_payments = {}

# Mapear planos para descrições e duração em dias
plan_descriptions = {
    "10": {"name": "Semanal", "duration": 7},
    "30": {"name": "Mensal", "duration": 30},
    "60": {"name": "Trimestral", "duration": 90},
    "100": {"name": "Vitalício", "duration": 36500},  # 100 anos (praticamente vitalício)
    "18": {"name": "2 meses", "duration": 60},
    "25": {"name": "3 meses", "duration": 90}
}

# Arquivo para armazenar os usuários e planos
SUBSCRIBERS_FILE = 'subscribers.json'
USERS_FILE = 'users.json'

# Função para carregar inscritos do arquivo JSON
def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError:
            return {}
    return {}

# Função para salvar inscritos no arquivo JSON
def save_subscribers(subscribers):
    with open(SUBSCRIBERS_FILE, 'w') as file:
        json.dump(subscribers, file, indent=2)

# Função para carregar todos os usuários do arquivo JSON
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError:
            return {}
    return {}

# Função para salvar todos os usuários no arquivo JSON
def save_users(users):
    with open(USERS_FILE, 'w') as file:
        json.dump(users, file, indent=2)

# Carregar inscritos e usuários ao iniciar o bot
subscribers = load_subscribers()
users = load_users()

# Função para verificar se o usuário é um administrador
def is_admin(user_id):
    return str(user_id) in ADMIN_IDS

# Função para registrar um usuário quando ele interage com o bot
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
        # Atualizar a última atividade
        users[user_id]["last_activity"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if user.username and users[user_id]["username"] != user.username:
            users[user_id]["username"] = user.username
        save_users(users)

# Comando de administração
@bot.message_handler(commands=['admin'])
def admin_menu(message):
    # Registrar o usuário
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

# Handler para callbacks do menu admin
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback(call):
    chat_id = call.message.chat.id
    
    if not is_admin(chat_id):
        bot.answer_callback_query(call.id, "Acesso negado")
        return
    
    if call.data == "admin_users":
        # Lista de usuários assinantes
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        
        # Mostra até 10 usuários mais recentes para não sobrecarregar o menu
        recent_users = list(subscribers.keys())[-10:] if subscribers else []
        
        if recent_users:
            for user_id in recent_users:
                user_info = subscribers[user_id]
                plan_name = user_info.get("plan_name", "Desconhecido")
                
                # Buscar o nome de usuário do dicionário users
                username = "Sem username"
                if user_id in users:
                    username = users[user_id].get("username", "Sem username")
                
                # Mostrar username - plano em vez de ID - plano
                display_name = f"@{username}" if username != "Sem username" and username != "Não definido" else f"Usuario {user_id[:5]}..."
                markup.add(InlineKeyboardButton(f"👤 {display_name} - {plan_name}", callback_data=f"user_info_{user_id}"))
        else:
            bot.answer_callback_query(call.id, "Nenhum assinante encontrado")
            return
        
        markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="admin_back"))
        bot.edit_message_text("Selecione um assinante para ver detalhes:", chat_id, call.message.message_id, reply_markup=markup)
    
    elif call.data == "admin_all_users":
        # Lista todos os usuários (assinantes ou não)
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        
        # Mostra até 10 usuários mais recentes para não sobrecarregar o menu
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

# Handler para exibir informações de qualquer usuário (assinante ou não)
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
        
        # Verificar se é um assinante
        is_subscriber = user_id in subscribers
        subscription_status = "Não é assinante"
        
        if is_subscriber:
            sub_data = subscribers[user_id]
            if sub_data.get("is_active", False):
                expiry_date = datetime.datetime.strptime(sub_data.get("expiry_date", "2023-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
                subscription_status = f"✅ Plano {sub_data.get('plan_name', 'Desconhecido')} ativo até {expiry_date.strftime('%d/%m/%Y')}"
            else:
                subscription_status = "⛔ Assinatura expirada"
        
        # Formatar datas
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
        
        # Criar URL para perfil do usuário
        user_profile_url = f"tg://user?id={user_id}"
        markup.add(InlineKeyboardButton("🗣️ Abrir Chat", url=user_profile_url))
        markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="admin_all_users"))
        
        bot.edit_message_text(user_info, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "Usuário não encontrado")

# Handler para exibir informações de assinante
@bot.callback_query_handler(func=lambda call: call.data.startswith("user_info_"))
def user_info_callback(call):
    chat_id = call.message.chat.id
    
    if not is_admin(chat_id):
        bot.answer_callback_query(call.id, "Acesso negado")
        return
    
    user_id = call.data.replace("user_info_", "")
    
    if user_id in subscribers:
        user_data = subscribers[user_id]
        
        # Buscar nome de usuário do dicionário users
        username = "Não definido"
        if user_id in users:
            username = users[user_id].get("username", "Não definido")
        
        # Formatar datas
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
        
        # Criar URL para perfil do usuário
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

# Opções do menu principal
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Registrar o usuário
    register_user(message.from_user)
    
    # Obter informações do usuário
    user_id = message.from_user.id
    username = message.from_user.username or "Não definido"
    first_name = message.from_user.first_name or "Não definido"
    
    # Verificar se o usuário já tem uma assinatura ativa
    subscription_status = "❌ Sem plano ativo"
    if str(user_id) in subscribers and subscribers[str(user_id)].get("is_active", False):
        plan_name = subscribers[str(user_id)].get("plan_name", "Desconhecido")
        expiry_date = datetime.datetime.strptime(subscribers[str(user_id)]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        days_left = (expiry_date - datetime.datetime.now()).days
        subscription_status = f"✅ Plano {plan_name} ativo - {days_left} dias restantes"
    
    # Preparar mensagem de boas-vindas com detalhes do usuário no formato HTML
    welcome_text = (
        f"<b>Olá, {first_name}!</b>\n\n"
        "<pre>🕊 SUAS INFORMAÇÕES:</pre>\n"
        f"<pre>• Usuário: @{username}</pre>\n"
        f"<pre>• ID: {user_id}</pre>\n"
        f"<pre>• Status: {subscription_status}</pre>\n\n"
        "<b>Escolha uma opção abaixo:</b>"
    )
    
    # Criar menu de botões
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("PRÉVIAS 👀", callback_data="opt1"),
        InlineKeyboardButton("VIP 💕", callback_data="opt2"),
        InlineKeyboardButton("SUPORTE 👨‍💻", callback_data="opt3")
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="HTML")

# Handler para confirmar envio de mensagem global
@bot.callback_query_handler(func=lambda call: call.data == "confirm_broadcast")
def confirm_broadcast(call):
    chat_id = call.message.chat.id
    
    if not is_admin(chat_id):
        bot.answer_callback_query(call.id, "Acesso negado")
        return
    
    # Recuperar a mensagem armazenada
    global broadcast_text
    
    if not broadcast_text:
        bot.answer_callback_query(call.id, "Erro: mensagem não encontrada")
        return
    
    # Informar que o envio começou
    bot.edit_message_text("📤 *Enviando mensagem global...*", chat_id, call.message.message_id, parse_mode="Markdown")
    
    # Contador de sucesso/falha
    success_count = 0
    fail_count = 0
    
    # Enviar para todos os usuários que já interagiram com o bot (usando o arquivo users.json)
    for user_id in users:
        try:
            bot.send_message(int(user_id), f"📢 *Comunicado Oficial:*\n\n{broadcast_text}", parse_mode="Markdown")
            success_count += 1
            time.sleep(0.1)  # Pequeno delay para evitar limites de API
        except Exception as e:
            print(f"Erro ao enviar mensagem para {user_id}: {e}")
            fail_count += 1
    
    # Reportar resultado
    bot.send_message(
        chat_id, 
        f"📊 *Relatório de Envio:*\n\n"
        f"✅ *Enviados com sucesso:* {success_count}\n"
        f"❌ *Falhas:* {fail_count}\n\n"
        f"*Total de destinatários:* {len(users)}",
        parse_mode="Markdown"
    )
    
    # Limpar a variável global
    broadcast_text = None

# Adicionar a lógica de registro de usuários a outros handlers relevantes
@bot.callback_query_handler(func=lambda call: call.data in ["opt1", "opt2", "opt3"])
def menu_pagamento(call):
    # Registrar o usuário
    register_user(call.from_user)
    
    if call.data == "opt1":  # Opção 1
        # URL do canal
        channel_url = "https://t.me/+T0RlQN1tDb9hNTMx"
        
        # Cria botões de redirecionamento
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
        support_url = "http://T.me/X1X2X3X4X5I"
        
        # Criar botões de redirecionamento
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Abrir Chat de Suporte", url=support_url))
        markup.add(InlineKeyboardButton("Voltar ao Menu", callback_data="back_to_menu"))
        
    if message.text == '/mensagemglobal':
        bot.send_message(chat_id, "Use o comando seguido da mensagem que deseja enviar.\n\nExemplo: `/mensagemglobal Olá a todos!`", parse_mode="Markdown")
        return
    
    # Extrair a mensagem após o comando
    broadcast_message = message.text.replace('/mensagemglobal', '', 1).strip()
    
    # Enviar mensagem de confirmação
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("✅ Sim, enviar", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_broadcast")
    )
    
    # Armazenar a mensagem para uso posterior
    global broadcast_text
    broadcast_text = broadcast_message
    
    bot.send_message(
        chat_id, 
        f"*Prévia da Mensagem:*\n\n{broadcast_message}\n\n📢 *Confirma o envio desta mensagem para TODOS os usuários?*",
        parse_mode="Markdown",
        reply_markup=markup
    )

# Handler para cancelar envio de mensagem global
@bot.callback_query_handler(func=lambda call: call.data == "cancel_broadcast")
def cancel_broadcast(call):
    chat_id = call.message.chat.id
    
    if not is_admin(chat_id):
        bot.answer_callback_query(call.id, "Acesso negado")
        return
    
    # Limpar a variável global
    global broadcast_text
    broadcast_text = None
    
    bot.edit_message_text("❌ Envio de mensagem global cancelado.", chat_id, call.message.message_id)

# Opções do menu principal
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Obter informações do usuário
    user_id = message.from_user.id
    username = message.from_user.username or "Não definido"
    first_name = message.from_user.first_name or "Não definido"
    
    # Verificar se o usuário já tem uma assinatura ativa
    subscription_status = "❌ Sem plano ativo"
    if str(user_id) in subscribers and subscribers[str(user_id)].get("is_active", False):
        plan_name = subscribers[str(user_id)].get("plan_name", "Desconhecido")
        expiry_date = datetime.datetime.strptime(subscribers[str(user_id)]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        days_left = (expiry_date - datetime.datetime.now()).days
        subscription_status = f"✅ Plano {plan_name} ativo - {days_left} dias restantes"
    
    # Preparar mensagem de boas-vindas com detalhes do usuário no formato HTML
    welcome_text = (
        f"<b>Olá, {first_name}!</b>\n\n"
        "<pre>🕊 SUAS INFORMAÇÕES:</pre>\n"
        f"<pre>• Usuário: @{username}</pre>\n"
        f"<pre>• ID: {user_id}</pre>\n"
        f"<pre>• Status: {subscription_status}</pre>\n\n"
        "<b>Escolha uma opção abaixo:</b>"
    )
    
    # Criar menu de botões
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("PRÉVIAS 👀", callback_data="opt1"),
        InlineKeyboardButton("VIP 💕", callback_data="opt2"),
        InlineKeyboardButton("SUPORTE 👨‍💻", callback_data="opt3")
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="HTML")

# Opções de pagamento
@bot.callback_query_handler(func=lambda call: call.data in ["opt1", "opt2", "opt3"])
def menu_pagamento(call):
    if call.data == "opt1":  # Opção 1
        # URL do canal
        channel_url = "https://t.me/+T0RlQN1tDb9hNTMx"
        
        # Cria botões de redirecionamento
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
        support_url = "http://T.me/X1X2X3X4X5I"
        
        # Criar botões de redirecionamento
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Abrir Chat de Suporte", url=support_url))
        markup.add(InlineKeyboardButton("Voltar ao Menu", callback_data="back_to_menu"))
        
        bot.edit_message_text("Clique no botão abaixo para abrir o chat de suporte:", 
                             call.message.chat.id, 
                             call.message.message_id, 
                             reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "Opção inválida")

# Adicione um handler para o botão "Voltar ao Menu"
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

# Verificar status do pagamento
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
                
                # Salvar no arquivo JSON
                save_subscribers(subscribers)
                
                # URL específica para acessar o grupo VIP
                group_url = "https://t.me/+sQf5GlZZZPA3MDJh"
                
                # Criar markup com botão para o grupo
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("Entrar no Grupo VIP", url=group_url))
                
                # Enviar mensagem de confirmação com o botão
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
                
                # Remover o pagamento da lista de pendentes
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
                
                # Remover o pagamento da lista de pendentes
                if chat_id in pending_payments:
                    del pending_payments[chat_id]
                
                return True
            
            elif status == 'pending':
                # Ainda pendente, continua verificando
                return False
    
    except Exception as e:
        print(f"Erro ao verificar status do pagamento: {e}")
        return False

# Loop de verificação de pagamentos pendentes
def payment_checker():
    while True:
        # Criar uma cópia do dicionário para evitar erros durante a iteração
        pending_copy = pending_payments.copy()
        
        for chat_id, payment_data in pending_copy.items():
            payment_id = payment_data["payment_id"]
            plan_type = payment_data["plan_type"]
            timestamp = payment_data["timestamp"]
            
            # Verificar se o pagamento expirou (mais de 24 horas)
            if time.time() - timestamp > 86400:  # 24 horas em segundos
                bot.send_message(
                    chat_id,
                    "⏰ *Tempo Expirado*\n\n"
                    "O tempo para o pagamento expirou. Por favor, inicie uma nova solicitação de pagamento.",
                    parse_mode="Markdown"
                )
                del pending_payments[chat_id]
                continue
            
            # Verificar status atual
            result = check_payment_status(payment_id, chat_id, plan_type)
            
            # Se o resultado foi processado (aprovado ou rejeitado), não precisamos verificar novamente
            if result:
                continue
        
        # Verifica pagamentos a cada 30 segundos
        time.sleep(30)

# Loop de verificação de assinaturas vencidas
def subscription_checker():
    while True:
        # Obter data atual
        now = datetime.datetime.now()
        current_date = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # Criar uma cópia do dicionário para evitar erros durante a iteração
        subscribers_copy = subscribers.copy()
        
        for user_id, user_data in subscribers_copy.items():
            if user_data["is_active"]:
                expiry_date_str = user_data["expiry_date"]
                expiry_date = datetime.datetime.strptime(expiry_date_str, "%Y-%m-%d %H:%M:%S")
                
                # Verificar se o plano expirou
                if now > expiry_date:
                    # Plano expirou, atualizar status
                    subscribers[user_id]["is_active"] = False
                    save_subscribers(subscribers)
                    
                    # Enviar mensagem ao usuário sobre a expiração
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
                        
                        # Tentar remover o usuário do grupo VIP
                        try:
                            # ID do grupo VIP - substitua pelo ID do seu grupo
                            group_id = "-1001875691876"  # Exemplo: extraído de https://t.me/+sQf5GlZZZPA3MDJh
                            
                            # Banir o usuário do grupo
                            bot.ban_chat_member(group_id, int(user_id))
                            
                            # Depois de 1 segundo, desbanir para que o usuário possa entrar novamente após renovar
                            time.sleep(1)
                            bot.unban_chat_member(group_id, int(user_id), only_if_banned=True)
                            
                            print(f"Usuário {user_id} removido do grupo VIP por assinatura vencida")
                            
                            # Notificar o administrador
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
                
                # Verificar se o plano vai expirar nos próximos 3 dias (enviar lembrete)
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
                        
                        # Marcar que o lembrete foi enviado
                        subscribers[user_id]["reminder_sent"] = True
                        save_subscribers(subscribers)
                    except Exception as e:
                        print(f"Erro ao enviar lembrete de renovação: {e}")
        
        # Verificar inscrições a cada 6 horas
        time.sleep(21600)  # 6 horas em segundos

# Iniciar as threads de verificação
payment_thread = threading.Thread(target=payment_checker, daemon=True)
payment_thread.start()

subscription_thread = threading.Thread(target=subscription_checker, daemon=True)
subscription_thread.start()

# Processamento do pagamento
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def process_payment(call):
    parts = call.data.split("_")
    amount = parts[1]  # Valor do pagamento
    plan_type = "_".join(parts[2:])  # Tipo do plano (ex: vip_mensal, normal_2meses)
    plan_info = plan_descriptions.get(amount, {"name": "Plano", "duration": 30})
    plan_name = plan_info["name"]
    
    # Dados mais completos para a API do Mercado Pago
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
                "number": "12345678909"  # CPF fictício
            }
        }
    }
    
    try:
        # Adicione o cabeçalho X-Idempotency-Key
        idempotency_key = str(uuid.uuid4())
        headers = HEADERS.copy()
        headers["X-Idempotency-Key"] = idempotency_key
        
        response = requests.post(
            "https://api.mercadopago.com/v1/payments", 
            headers=headers,
            timeout=30,
            data=json.dumps(payment_data)
        )
        
        # Adicione logs para debug
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 201:
            payment_info = response.json()
            payment_id = payment_info.get('id')
            
            # Registra o pagamento como pendente para verificação posterior
            pending_payments[call.message.chat.id] = {
                "payment_id": payment_id,
                "plan_type": plan_type,
                "amount": amount,
                "timestamp": time.time(),
                "plan_description": plan_name
            }
            
            # Verifique se as chaves existem antes de acessá-las
            if ("point_of_interaction" in payment_info and 
                "transaction_data" in payment_info["point_of_interaction"]):
                
                transaction_data = payment_info["point_of_interaction"]["transaction_data"]
                pix_qr = transaction_data.get("qr_code", "QR Code não disponível")
                
                # Envie a mensagem inicial com informações do plano
                initial_message = (f"🔹 *Pagamento PIX gerado com sucesso*\n\n"
                                  f"🔹 *Plano:* {plan_name}\n"
                                  f"🔹 *Valor:* R$ {amount},00\n\n"
                                  f"⏰ *Válido por 24 horas*\n\n"
                                  f"✅ *Após o pagamento, seu acesso será liberado automaticamente*")
                
                bot.send_message(call.message.chat.id, initial_message, parse_mode="Markdown")
                
                # Se houver QR code base64, envie como imagem junto com o código copia e cola
                if "qr_code_base64" in transaction_data:
                    try:
                        import base64
                        from io import BytesIO
                        
                        # Decodifica a imagem Base64
                        image_data = base64.b64decode(transaction_data["qr_code_base64"])
                        image = BytesIO(image_data)
                        
                        # Preparar a caption com o código copia e cola
                        caption = f"*QR Code para pagamento - {plan_name}*\n\n*Código Copia e Cola:*\n`{pix_qr}`"
                        
                        # Envia a imagem com o código copia e cola na mesma mensagem
                        bot.send_photo(call.message.chat.id, image, caption=caption, parse_mode="Markdown")
                    except Exception as e:
                        print(f"Erro ao enviar QR code como imagem: {str(e)}")
                        # Fallback: envie o QR code como texto
                        bot.send_message(call.message.chat.id, f"*Código PIX para Copia e Cola:*\n`{pix_qr}`", parse_mode="Markdown")
                else:
                    # Se não tiver QR code base64, envie apenas o código copia e cola
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

# Comando para verificar status do pagamento manualmente
@bot.message_handler(commands=['status'])
def check_status(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    
    if user_id in subscribers and subscribers[user_id]["is_active"]:
        # Usuário tem assinatura ativa
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
        # Usuário tem pagamento pendente
        payment_data = pending_payments[chat_id]
        payment_id = payment_data["payment_id"]
        plan_type = payment_data["plan_type"]
        
        bot.send_message(chat_id, "Verificando o status do seu pagamento...", parse_mode="Markdown")
        check_payment_status(payment_id, chat_id, plan_type)
    else:
        # Usuário não tem assinatura ativa nem pagamento pendente
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

# Comando para administradores verificarem assinaturas ativas
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
                
                # Limitar tamanho da mensagem
                if len(response) > 3500:
                    bot.send_message(message.chat.id, response, parse_mode="Markdown")
                    response = "*Continuação da lista:*\n\n"
            
            if response:
                bot.send_message(message.chat.id, response, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "Não há assinantes ativos no momento.", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Você não tem permissão para usar este comando.", parse_mode="Markdown")

# Comando para enviar mensagem global diretamente
@bot.message_handler(commands=['mensagemglobal'])
def mensagem_global_command(message):
    chat_id = message.chat.id
    
    if not is_admin(chat_id):
        bot.send_message(chat_id, "Você não tem permissão para usar este comando.")
        return
    
    # Verificar se há texto após o comando
    if message.text == '/mensagemglobal':
        bot.send_message(chat_id, "Use o comando seguido da mensagem que deseja enviar.\n\nExemplo: `/mensagemglobal Olá a todos!`", parse_mode="Markdown")
        return
    
    # Extrair a mensagem após o comando
    broadcast_message = message.text.replace('/mensagemglobal', '', 1).strip()
    
    # Enviar mensagem de confirmação
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("✅ Sim, enviar", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_broadcast")
    )
    
    # Armazenar a mensagem para uso posterior
    global broadcast_text
    broadcast_text = broadcast_message
    
    bot.send_message(
        chat_id, 
        f"*Prévia da Mensagem:*\n\n{broadcast_message}\n\n📢 *Confirma o envio desta mensagem para TODOS os usuários?*",
        parse_mode="Markdown",
        reply_markup=markup
    )

# Processador de mensagem global
def process_broadcast_message(message):
    chat_id = message.chat.id
    
    if not is_admin(chat_id):
        return
    
    if message.text == '/cancel':
        bot.send_message(chat_id, "Envio de mensagem global cancelado.")
        return
    
    # Obter a mensagem a ser enviada
    broadcast_message = message.text
    
    # Enviar mensagem de confirmação
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("✅ Sim, enviar", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_broadcast")
    )
    
    # Armazenar a mensagem para uso posterior
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