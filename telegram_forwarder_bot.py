#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config_manager import load_config, save_config, load_mensajes, save_mensajes

# Configurar logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramForwarderBot:
    def __init__(self, token):
        self.token = token
        self.config = load_config()
        self.mensajes = load_mensajes()
        self.application = None

    def _is_admin(self, user_id):
        return user_id == self.config.get("admin_id")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self._is_admin(user_id):
            return await update.message.reply_text(
                "❌ *Acceso Denegado*\nSolo el admin puede usar este bot.",
                parse_mode="Markdown",
            )
        await self._show_main_menu(update, context)

    async def _show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [
                InlineKeyboardButton("🔗 Vincular Canal", callback_data="vincular_canal"),
                InlineKeyboardButton("📂 Destinos", callback_data="gestionar_destinos"),
            ],
            [
                InlineKeyboardButton("✏️ Editar Mensaje", callback_data="editar_mensaje"),
                InlineKeyboardButton("🗑️ Eliminar Mensaje", callback_data="eliminar_mensaje"),
            ],
            [
                InlineKeyboardButton("🔁 Cambiar Intervalo", callback_data="cambiar_intervalo"),
                InlineKeyboardButton("🌐 Cambiar Zona", callback_data="cambiar_zona"),
            ],
            [InlineKeyboardButton("📄 Estado del Bot", callback_data="estado_bot")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        status = (
            f"🤖 *Bot de Reenvío*\n\n"
            f"📺 Origen: `{self.config.get('origen_chat_id','No configurado')}`\n"
            f"👥 Destinos: `{len(self.config.get('destinos',[]))}`\n"
            f"📁 Listas: `{len(self.config.get('listas_destinos',{}))}`\n"
            f"📨 Mensajes: `{len(self.mensajes)}`\n"
            f"⏱️ Intervalo: `{self.config.get('intervalo_segundos',60)}s`\n"
            f"🌐 Zona: `{self.config.get('zone','UTC')}`\n\n"
            "📋 Elige una opción:"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                status, reply_markup=reply_markup, parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                status, reply_markup=reply_markup, parse_mode="Markdown"
            )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        if not self._is_admin(user_id):
            return await query.edit_message_text(
                "❌ *Acceso Denegado*", parse_mode="Markdown"
            )

        data = query.data

        # Menú principal
        if data == "menu_principal":
            return await self._show_main_menu(update, context)

        # 2. Canal de Origen
        if data == "vincular_canal":
            return await self._show_vincular_canal_menu(update, context)
        if data == "agregar_canal":
            return await self._request_channel_forward(update, context)
        if data == "editar_canal":
            return await self._request_channel_forward(update, context)

        # 3. Gestión de Destinos
        if data == "gestionar_destinos":
            return await self._show_destinos_menu(update, context)
        if data == "destinos_simples":
            return await self._show_destinos_simples_menu(update, context)
        if data == "agregar_destino":
            return await self._request_add_destination(update, context)
        if data == "eliminar_destino":
            return await self._show_remove_destination_menu(update, context)
        if data.startswith("remove_dest_"):
            idx = int(data.split("_")[-1])
            return await self._remove_destination(update, context, idx)
        if data == "listas_destinos":
            return await self._show_listas_destinos_menu(update, context)
        if data == "crear_lista":
            return await self._request_create_list(update, context)
        if data == "gestionar_listas":
            return await self._show_manage_lists_menu(update, context)
        if data.startswith("select_list_"):
            name = data.replace("select_list_", "")
            return await self._show_list_details(update, context, name)
        if data.startswith("delete_list_"):
            name = data.replace("delete_list_", "")
            return await self._delete_list(update, context, name)

        # 4. Configuración de Mensajes
        if data == "editar_mensaje":
            return await self._show_edit_message_menu(update, context)
        if data.startswith("edit_msg_"):
            idx = int(data.split("_")[-1])
            return await self._edit_message_interval(update, context, idx)
        if data == "eliminar_mensaje":
            return await self._show_delete_message_menu(update, context)
        if data.startswith("delete_msg_"):
            idx = int(data.split("_")[-1])
            return await self._delete_message(update, context, idx)
        if data.startswith("msg_"):
            return await self._handle_message_config(update, context, data)

        # 6. Intervalos
        if data == "cambiar_intervalo":
            return await self._show_interval_menu(update, context)
        if data == "intervalo_global":
            return await self._request_global_interval(update, context)
        if data == "intervalo_por_mensaje":
            return await self._request_message_interval(update, context)
        if data == "intervalo_por_lista":
            return await self._request_list_interval(update, context)
        if data.startswith("interval_list_"):
            name = data.replace("interval_list_", "")
            return await self._process_list_interval(update, context, name)

        # 7. Zona Horaria
        if data == "cambiar_zona":
            return await self._request_timezone(update, context)

        # 8. Estado del Bot
        if data == "estado_bot":
            return await self._show_main_menu(update, context)

    # ----- 2. Canal de Origen -----
    async def _show_vincular_canal_menu(self, update, context):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Agregar Canal", callback_data="agregar_canal")],
            [InlineKeyboardButton("✏️ Editar Canal", callback_data="editar_canal")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu_principal")],
        ])
        current = self.config.get("origen_chat_id", "Ninguno")
        text = f"🔗 *Gestión Canal de Origen*\n\nCanal actual: `{current}`\n\nReenvía un mensaje del canal para vincularlo."
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    async def _request_channel_forward(self, update, context):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="menu_principal")]])
        text = "📤 *Reenvía un mensaje* desde el canal que quieres vincular."
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        context.user_data["waiting_for"] = "channel_forward"

    # ----- 3. Destinos -----
    async def _show_destinos_menu(self, update, context):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Destinos Simples", callback_data="destinos_simples")],
            [InlineKeyboardButton("📁 Listas de Destinos", callback_data="listas_destinos")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu_principal")],
        ])
        ds = len(self.config.get("destinos", []))
        ls = len(self.config.get("listas_destinos", {}))
        text = f"📂 *Gestión de Destinos*\n\nDestinos: `{ds}`\nListas: `{ls}`"
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    async def _show_destinos_simples_menu(self, update, context):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Agregar Destino", callback_data="agregar_destino")],
            [InlineKeyboardButton("🗑️ Eliminar Destino", callback_data="eliminar_destino")],
            [InlineKeyboardButton("🔙 Volver", callback_data="gestionar_destinos")],
        ])
        destinos = self.config.get("destinos", [])
        text = f"👥 *Destinos Simples* ({len(destinos)})\n\n"
        text += "\n".join(f"{i+1}. `{d}`" for i, d in enumerate(destinos[:5]))
        await update.callback_query.edit_message_text(text or "❌ No hay destinos.", reply_markup=kb, parse_mode="Markdown")

    async def _request_add_destination(self, update, context):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="gestionar_destinos")]])
        text = "📝 *Envía el ID* del chat/grupo destino.\nEj: `-1001234567890` o `@username`"
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        context.user_data["waiting_for"] = "destination_id"

    async def _process_destination_input(self, update, context):
        did = update.message.text.strip()
        try:
            did = int(did)
        except: pass
        lst = self.config.setdefault("destinos", [])
        if did not in lst:
            lst.append(did)
            save_config(self.config)
            text = f"✅ Destino `{did}` agregado."
        else:
            text = f"⚠️ `{did}` ya existe."
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="gestionar_destinos")]]))
        context.user_data.pop("waiting_for", None)

    async def _show_remove_destination_menu(self, update, context):
        destinos = self.config.get("destinos", [])
        keyboard = [
            [InlineKeyboardButton(f"🗑️ {i+1}. {d}", callback_data=f"remove_dest_{i}")] 
            for i, d in enumerate(destinos)
        ] + [[InlineKeyboardButton("🔙 Volver", callback_data="gestionar_destinos")]]
        text = "🗑️ *Eliminar Destino*\n\nSelecciona uno:"
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    async def _remove_destination(self, update, context, idx):
        d = self.config.get("destinos", []).pop(idx)
        save_config(self.config)
        text = f"✅ Destino `{d}` eliminado."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="gestionar_destinos")]])
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    # ----- Listas de Destinos -----
    async def _show_listas_destinos_menu(self, update, context):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Crear Lista", callback_data="crear_lista")],
            [InlineKeyboardButton("📂 Gestionar Listas", callback_data="gestionar_listas")],
            [InlineKeyboardButton("🔙 Volver", callback_data="gestionar_destinos")],
        ])
        total = len(self.config.get("listas_destinos", {}))
        text = f"📁 *Listas de Destinos* ({total})"
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    async def _request_create_list(self, update, context):
        await update.callback_query.edit_message_text("📌 *Nombre de la nueva lista*:", parse_mode="Markdown")
        context.user_data["waiting_for"] = "list_name"

    async def _process_list_name(self, update, context):
        name = update.message.text.strip()
        context.user_data["new_list_name"] = name
        await update.message.reply_text(
            f"📋 *{name}*\nEnvía IDs (coma o línea):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="listas_destinos")]])
        )
        context.user_data["waiting_for"] = "list_destinations"

    async def _process_list_destinations(self, update, context):
        name = context.user_data.pop("new_list_name")
        parts = [p.strip() for p in update.message.text.replace("\n",",").split(",") if p.strip()]
        cfg = self.config.setdefault("listas_destinos", {})
        cfg[name] = parts
        save_config(self.config)
        text = f"✅ Lista *{name}* creada con {len(parts)} destinos."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="listas_destinos")]])
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        context.user_data.pop("waiting_for", None)

    async def _show_manage_lists_menu(self, update, context):
        lists = self.config.get("listas_destinos", {})
        keyboard = [[InlineKeyboardButton(n, callback_data=f"select_list_{n}")] for n in lists] + [
            [InlineKeyboardButton("🔙 Volver", callback_data="listas_destinos")]
        ]
        text = "📂 *Gestionar Listas*\nSelecciona una:"
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    async def _show_list_details(self, update, context, name):
        ids = self.config.get("listas_destinos", {}).get(name, [])
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Eliminar", callback_data=f"delete_list_{name}")],
            [InlineKeyboardButton("🔙 Volver", callback_data="gestionar_listas")],
        ])
        text = f"📋 *{name}* ({len(ids)})\n" + ("\n".join(ids) or "Ninguno")
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    async def _delete_list(self, update, context, name):
        self.config.get("listas_destinos", {}).pop(name, None)
        save_config(self.config)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="gestionar_listas")]])
        await update.callback_query.edit_message_text(f"❌ Lista *{name}* eliminada.", reply_markup=kb, parse_mode="Markdown")

    # ----- 4. Mensajes a Reenviar -----
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not self._is_admin(uid):
            return

        waiting = context.user_data.get("waiting_for")
        # Canal de Origen
        if waiting == "channel_forward" and update.message.forward_from_chat:
            return await self._process_channel_forward(update, context)
        # Destino simple
        if waiting == "destination_id":
            return await self._process_destination_input(update, context)
        # Listas
        if waiting == "list_name":
            return await self._process_list_name(update, context)
        if waiting == "list_destinations":
            return await self._process_list_destinations(update, context)
        # Intervalos
        if waiting == "global_interval":
            return await self._process_global_interval(update, context)
        if waiting == "msg_interval_id":
            return await self._process_message_interval_id(update, context)
        if waiting == "edit_message_interval":
            return await self._process_edit_message_interval(update, context)
        if waiting == "list_interval_value":
            return await self._process_list_interval_value(update, context)
        # Timezone
        if waiting == "timezone":
            return await self._process_timezone(update, context)
        # Nuevo mensaje reenviado
        if (
            update.message.forward_from_chat
            and update.message.forward_from_chat.id == self.config.get("origen_chat_id")
        ):
            return await self._process_channel_message(update, context)

    async def _process_channel_forward(self, update, context):
        cid = update.message.forward_from_chat.id
        title = update.message.forward_from_chat.title or "Canal"
        self.config["origen_chat_id"] = cid
        save_config(self.config)
        text = (
            f"✅ *Canal Vinculado!*\n\n"
            f"📺 `{title}`\n"
            f"🆔 `{cid}`\n"
            "Ahora detecto mensajes de aquí."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menú", callback_data="menu_principal")]])
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        context.user_data.pop("waiting_for", None)

    async def _process_channel_message(self, update, context):
        origen = update.message.forward_from_chat.id
        mid = update.message.forward_from_message_id
        nuevo = {
            "from_chat_id": origen,
            "message_id": mid,
            "intervalo_segundos": self.config.get("intervalo_segundos", 60),
            "dest_all": True,
            "dest_list": None,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.mensajes.append(nuevo)
        save_mensajes(self.mensajes)
        await self._show_message_config_panel(update, context, len(self.mensajes) - 1)

    async def _show_message_config_panel(self, update, context, idx):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 A Todos", callback_data=f"msg_all_{idx}")],
            [InlineKeyboardButton("📋 Lista", callback_data=f"msg_list_{idx}")],
            [InlineKeyboardButton("✅ Guardar", callback_data=f"msg_save_{idx}")],
            [InlineKeyboardButton("❌ Cancelar", callback_data=f"msg_cancel_{idx}")],
            [InlineKeyboardButton("🏁 Finalizar", callback_data=f"msg_finish_{idx}")],
        ])
        m = self.mensajes[idx]
        text = (
            f"🔥 *Nuevo Mensaje*\n\n"
            f"ID: `{m['message_id']}`\n"
            f"⏱️ `{m['intervalo_segundos']}s`\n\n"
            "¿A dónde enviarlo?"
        )
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    async def _handle_message_config(self, update, context, data):
        parts = data.split("_")
        act, idx = parts[1], int(parts[2])
        m = self.mensajes[idx]

        if act == "all":
            m["dest_all"], m["dest_list"] = True, None
            save_mensajes(self.mensajes)
            text = "✅ *Enviar a todos*"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menú", callback_data="menu_principal")]])
        elif act == "list":
            return await self._show_listas_destinos_menu(update, context)
        elif act == "save":
            text = "✅ *Mensaje guardado*"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menú", callback_data="menu_principal")]])
        elif act == "cancel":
            self.mensajes.pop(idx)
            save_mensajes(self.mensajes)
            text = "❌ *Mensaje cancelado*"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menú", callback_data="menu_principal")]])
        elif act == "finish":
            if not hasattr(context.application, "forwarder_job"):
                await self._start_forwarder(context)
            text = "🏁 *¡Reenvío automático iniciado!*"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menú", callback_data="menu_principal")]])

        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    # ----- 6. Intervalos -----
    async def _show_interval_menu(self, update, context):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔁 Global", callback_data="intervalo_global")],
            [InlineKeyboardButton("✏️ Por Mensaje", callback_data="intervalo_por_mensaje")],
            [InlineKeyboardButton("📋 Por Lista", callback_data="intervalo_por_lista")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu_principal")],
        ])
        await update.callback_query.edit_message_text("🕒 *Cambiar Intervalo*", reply_markup=kb, parse_mode="Markdown")

    async def _request_global_interval(self, update, context):
        await update.callback_query.edit_message_text("🕒 *Nuevo intervalo global (s):*")
        context.user_data["waiting_for"] = "global_interval"

    async def _process_global_interval(self, update, context):
        try:
            v = int(update.message.text.strip())
            self.config["intervalo_segundos"] = v
            save_config(self.config)
            text = f"✅ Global: `{v}s`"
        except:
            text = "❌ Valor inválido"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cambiar_intervalo")]])
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        context.user_data.pop("waiting_for", None)

    async def _request_message_interval(self, update, context):
        await update.callback_query.edit_message_text("✏️ *ID de mensaje:*")
        context.user_data["waiting_for"] = "msg_interval_id"

    async def _process_message_interval_id(self, update, context):
        try:
            idx = int(update.message.text.strip()) - 1
            context.user_data["edit_msg_index"] = idx
            await update.message.reply_text("🕒 *Nuevo intervalo (s):*")
            context.user_data["waiting_for"] = "edit_message_interval"
        except:
            await update.message.reply_text("❌ ID inválido")
    
    async def _request_list_interval(self, update, context):
        lists = self.config.get("listas_destinos", {})
        keyboard = [[InlineKeyboardButton(n, callback_data=f"interval_list_{n}")] for n in lists] + [
            [InlineKeyboardButton("🔙 Volver", callback_data="cambiar_intervalo")]
        ]
        await update.callback_query.edit_message_text("📋 *Selecciona Lista*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    async def _process_list_interval(self, update, context, name):
        context.user_data["interval_list_name"] = name
        await update.callback_query.edit_message_text(f"🕒 *Intervalo para {name} (s):*")
        context.user_data["waiting_for"] = "list_interval_value"

    async def _process_list_interval_value(self, update, context):
        name = context.user_data.pop("interval_list_name")
        try:
            v = int(update.message.text.strip())
            for m in self.mensajes:
                if m.get("dest_list") == name:
                    m["intervalo_segundos"] = v
            save_mensajes(self.mensajes)
            text = f"✅ Intervalo de `{name}`: `{v}s`"
        except:
            text = "❌ Valor inválido"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cambiar_intervalo")]])
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        context.user_data.pop("waiting_for", None)

    # ----- 7. Zona Horaria -----
    async def _request_timezone(self, update, context):
        await update.callback_query.edit_message_text("🌐 *Nueva zona (p.ej. Europe/Madrid)*")
        context.user_data["waiting_for"] = "timezone"

    async def _process_timezone(self, update, context):
        tz = update.message.text.strip()
        try:
            pytz.timezone(tz)
            self.config["zone"] = tz
            save_config(self.config)
            text = f"✅ Zona: `{tz}`"
        except:
            text = "❌ Zona inválida"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu_principal")]])
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        context.user_data.pop("waiting_for", None)

    # ----- 8. Forwarder -----
    async def _start_forwarder(self, context: ContextTypes.DEFAULT_TYPE):
        interval = self.config.get("intervalo_segundos", 60)
        if hasattr(context.application, "forwarder_job"):
            context.application.forwarder_job.schedule_removal()
        context.application.forwarder_job = context.job_queue.run_repeating(
            self._reenviar_mensajes, interval=interval, first=10
        )
        logger.info(f"✅ Forwarder iniciado ({interval}s)")

    async def _reenviar_mensajes(self, context: ContextTypes.DEFAULT_TYPE):
        logger.info("🔄 Ciclo de reenvío...")
        for m in self.mensajes:
            dests = (
                self.config["destinos"]
                if m.get("dest_all", True)
                else self.config["listas_destinos"].get(m.get("dest_list"), [])
            )
            for d in dests:
                try:
                    await context.bot.forward_message(
                        chat_id=d,
                        from_chat_id=m["from_chat_id"],
                        message_id=m["message_id"],
                    )
                    logger.info(f"✔️ {m['message_id']} → {d}")
                except Exception as e:
                    logger.error(f"❌ {m['message_id']} → {d}: {e}")
        logger.info("🔄 Ciclo completado")

    def run(self):
        self.application = Application.builder().token(self.token).build()
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.application.add_handler(MessageHandler(filters.ALL, self.message_handler))
        logger.info("🚀 Bot iniciando…")
        self.application.run_polling()

if __name__ == "__main__":
    conf = load_config()
    token = conf.get("bot_token")
    if not token:
        print("❌ Debes poner tu bot_token en config.json")
        exit(1)
    TelegramForwarderBot(token).run()
