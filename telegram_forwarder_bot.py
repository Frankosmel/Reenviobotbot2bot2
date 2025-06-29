#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
import pytz
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config_manager import load_config, save_config, load_mensajes, save_mensajes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# == Teclado Principal ==
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["🔗 Vincular Canal", "📂 Destinos"],
    ["✏️ Editar Mensaje", "🗑️ Eliminar Mensaje"],
    ["🔁 Cambiar Intervalo", "🌐 Cambiar Zona"],
    ["📄 Estado del Bot"]
], resize_keyboard=True)

BACK_KEYBOARD = ReplyKeyboardMarkup([["🔙 Volver"]], resize_keyboard=True)

class TelegramForwarderBot:
    def __init__(self, token):
        self.config = load_config()
        self.mensajes = load_mensajes()
        self.token = token

    def _is_admin(self, uid):
        return uid == self.config.get("admin_id")

    async def start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not self._is_admin(uid):
            return await update.message.reply_text(
                "❌ *Acceso denegado.*",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
        await self._show_main_menu(update)

    async def _show_main_menu(self, update: Update):
        text = (
            "🚀 *Menú Principal*\n\n"
            f"📺 Origen: `{self.config.get('origen_chat_id','No asignado')}`\n"
            f"👥 Destinos: {len(self.config.get('destinos',[]))}\n"
            f"📁 Listas: {len(self.config.get('listas_destinos',{}))}\n"
            f"📨 Mensajes: {len(self.mensajes)}\n"
            f"⏱️ Intervalo: {self.config.get('intervalo_segundos',60)}s\n"
            f"🌐 Zona: `{self.config.get('zone','UTC')}`\n\n"
            "Selecciona una opción:"
        )
        if update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=MAIN_KEYBOARD, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD, parse_mode="Markdown")

    async def message_handler(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not self._is_admin(uid):
            return

        text = update.message.text.strip()
        waiting = ctx.user_data.get("waiting_for")

        # == Canal de Origen ==
        if text == "🔗 Vincular Canal":
            await update.message.reply_text(
                "📤 *Reenvía un mensaje* desde tu canal para vincularlo.",
                parse_mode="Markdown",
                reply_markup=BACK_KEYBOARD
            )
            ctx.user_data["waiting_for"] = "channel_forward"
            return

        if waiting == "channel_forward" and update.message.forward_from_chat:
            cid = update.message.forward_from_chat.id
            self.config["origen_chat_id"] = str(cid)
            save_config(self.config)
            await update.message.reply_text(
                f"✅ Canal vinculado: `{cid}`",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
            ctx.user_data.pop("waiting_for")
            return

        # == Destinos ==
        if text == "📂 Destinos":
            kb = ReplyKeyboardMarkup([
                ["➕ Agregar Destino","🗑️ Eliminar Destino"],
                ["📁 Crear Lista","📂 Gestionar Listas"],
                ["🔙 Volver"]
            ], resize_keyboard=True)
            await update.message.reply_text("📂 *Gestión de Destinos*", parse_mode="Markdown", reply_markup=kb)
            ctx.user_data["waiting_for"] = "destinos_menu"
            return

        if waiting == "destinos_menu":
            if text == "➕ Agregar Destino":
                await update.message.reply_text("📝 Envía el ID del destino:", reply_markup=BACK_KEYBOARD)
                ctx.user_data["waiting_for"] = "add_destino"
            elif text == "🗑️ Eliminar Destino":
                ds = self.config.get("destinos",[])
                if not ds:
                    await update.message.reply_text("⚠️ No hay destinos.", reply_markup=MAIN_KEYBOARD)
                else:
                    lines = "\n".join(f"{i+1}. {d}" for i,d in enumerate(ds))
                    await update.message.reply_text(
                        f"🗑️ *Elige número a eliminar:*\n{lines}",
                        parse_mode="Markdown", reply_markup=BACK_KEYBOARD
                    )
                    ctx.user_data["waiting_for"] = "del_destino"
            elif text == "📁 Crear Lista":
                await update.message.reply_text("📌 Nombre de la nueva lista:", reply_markup=BACK_KEYBOARD)
                ctx.user_data["waiting_for"] = "new_list_name"
            elif text == "📂 Gestionar Listas":
                lists = self.config.get("listas_destinos",{})
                if not lists:
                    await update.message.reply_text("⚠️ No hay listas.", reply_markup=MAIN_KEYBOARD)
                else:
                    menu = [[name] for name in lists.keys()]+[["🔙 Volver"]]
                    await update.message.reply_text("📂 *Listas Disponibles:*", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(menu,resize_keyboard=True))
                    ctx.user_data["waiting_for"] = "manage_lists"
            else:
                await update.message.reply_text("🔙 Volver al menú", reply_markup=MAIN_KEYBOARD)
                ctx.user_data.pop("waiting_for")
            return

        # agregar destino
        if waiting == "add_destino":
            d = text
            if d not in self.config["destinos"]:
                self.config["destinos"].append(d)
                save_config(self.config)
                await update.message.reply_text(f"✅ Destino `{d}` agregado.", parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
            else:
                await update.message.reply_text("⚠️ Ya existe.", reply_markup=MAIN_KEYBOARD)
            ctx.user_data.pop("waiting_for")
            return

        # eliminar destino
        if waiting == "del_destino":
            try:
                idx = int(text)-1
                d = self.config["destinos"].pop(idx)
                save_config(self.config)
                await update.message.reply_text(f"✅ Destino `{d}` eliminado.", reply_markup=MAIN_KEYBOARD)
            except:
                await update.message.reply_text("❌ Selección inválida.", reply_markup=MAIN_KEYBOARD)
            ctx.user_data.pop("waiting_for")
            return

        # crear lista: nombre → pedir IDs
        if waiting == "new_list_name":
            ctx.user_data["new_list_name"] = text
            await update.message.reply_text("📋 IDs separados por coma o línea:", reply_markup=BACK_KEYBOARD)
            ctx.user_data["waiting_for"] = "new_list_ids"
            return
        if waiting == "new_list_ids":
            name = ctx.user_data.pop("new_list_name")
            ids = [x.strip() for x in text.replace("\n",",").split(",") if x.strip()]
            self.config["listas_destinos"][name] = ids
            save_config(self.config)
            await update.message.reply_text(f"✅ Lista `{name}` creada.", reply_markup=MAIN_KEYBOARD)
            ctx.user_data.pop("waiting_for")
            return

        # gestionar listas
        if waiting == "manage_lists":
            if text == "🔙 Volver":
                await update.message.reply_text("🔙 Volver al menú", reply_markup=MAIN_KEYBOARD)
                ctx.user_data.pop("waiting_for")
            else:
                name = text
                if name in self.config["listas_destinos"]:
                    kb = ReplyKeyboardMarkup([["📋 Ver","❌ Eliminar"],["🔙 Volver"]],resize_keyboard=True)
                    await update.message.reply_text(f"📂 *{name}* ({len(self.config['listas_destinos'][name])})", parse_mode="Markdown", reply_markup=kb)
                    ctx.user_data["waiting_for"] = f"list_{name}"
            return

        # dentro de una lista:
        if waiting and waiting.startswith("list_"):
            name = waiting.split("_",1)[1]
            if text == "📋 Ver":
                ids = self.config["listas_destinos"][name]
                await update.message.reply_text("\n".join(ids) or "Ninguno", reply_markup=MAIN_KEYBOARD)
            elif text == "❌ Eliminar":
                self.config["listas_destinos"].pop(name, None)
                save_config(self.config)
                await update.message.reply_text(f"❌ Lista `{name}` eliminada.", reply_markup=MAIN_KEYBOARD)
            else:
                await update.message.reply_text("🔙 Volver al menú", reply_markup=MAIN_KEYBOARD)
            ctx.user_data.pop("waiting_for")
            return

        # == Captura de mensaje reenviado ==
        if update.message.forward_from_chat and str(update.message.forward_from_chat.id) == str(self.config.get("origen_chat_id")):
            origen = update.message.forward_from_chat.id
            mid = update.message.forward_from_message_id
            nuevo = {
                "from_chat_id": origen,
                "message_id": mid,
                "intervalo_segundos": self.config.get("intervalo_segundos",60),
                "dest_all": True,
                "dest_list": None,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.mensajes.append(nuevo)
            save_mensajes(self.mensajes)
            kb = ReplyKeyboardMarkup([
                ["👥 A Todos","📋 Lista"],
                ["✅ Guardar","❌ Cancelar"],
                ["🏁 Finalizar"]
            ], resize_keyboard=True)
            await update.message.reply_text(
                f"🔥 *Nuevo Mensaje Detectado!*\nID: `{mid}`",
                parse_mode="Markdown", reply_markup=kb
            )
            ctx.user_data["waiting_for"] = f"msg_cfg_{len(self.mensajes)-1}"
            return

        # == Configuración puntual de mensaje reenviado ==
        if waiting and waiting.startswith("msg_cfg_"):
            idx = int(waiting.split("_")[-1])
            m = self.mensajes[idx]
            if text == "👥 A Todos":
                m["dest_all"], m["dest_list"] = True, None
                save_mensajes(self.mensajes)
                await update.message.reply_text("✅ Enviar a *todos*.", parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
                ctx.user_data.pop("waiting_for")
            elif text == "📋 Lista":
                lists = self.config.get("listas_destinos",{})
                if not lists:
                    await update.message.reply_text("⚠️ No hay listas.", reply_markup=MAIN_KEYBOARD)
                    ctx.user_data.pop("waiting_for")
                else:
                    kb = ReplyKeyboardMarkup([[n] for n in lists]+[["🔙 Volver"]], resize_keyboard=True)
                    await update.message.reply_text("📋 Elige lista:", reply_markup=kb)
                    ctx.user_data["waiting_for"] = f"msg_list_{idx}"
            elif waiting.startswith("msg_list_"):
                if text == "🔙 Volver":
                    await update.message.reply_text("🔙 Volver al menú", reply_markup=MAIN_KEYBOARD)
                else:
                    name = text
                    m["dest_all"], m["dest_list"] = False, name
                    save_mensajes(self.mensajes)
                    await update.message.reply_text(f"✅ Lista `{name}` seleccionada.", reply_markup=MAIN_KEYBOARD)
                ctx.user_data.pop("waiting_for")
            elif text == "✅ Guardar":
                await update.message.reply_text("✅ Mensaje guardado.", reply_markup=MAIN_KEYBOARD)
                ctx.user_data.pop("waiting_for")
            elif text == "❌ Cancelar":
                self.mensajes.pop(idx)
                save_mensajes(self.mensajes)
                await update.message.reply_text("❌ Mensaje descartado.", reply_markup=MAIN_KEYBOARD)
                ctx.user_data.pop("waiting_for")
            elif text == "🏁 Finalizar":
                # iniciar forwarder
                if not hasattr(ctx.application, "forwarder_job"):
                    interval = self.config.get("intervalo_segundos",60)
                    ctx.application.forwarder_job = ctx.job_queue.run_repeating(
                        self._reenviar_mensajes, interval=interval, first=interval
                    )
                await update.message.reply_text("🏁 ¡Reenvío iniciado!", reply_markup=MAIN_KEYBOARD)
                ctx.user_data.pop("waiting_for")
            return

        # == Editar Mensaje ==
        if text == "✏️ Editar Mensaje":
            if not self.mensajes:
                return await update.message.reply_text("⚠️ No hay mensajes.", reply_markup=MAIN_KEYBOARD)
            lines = [f"{i+1}. {m['message_id']} ({m['intervalo_segundos']}s)" for i,m in enumerate(self.mensajes)]
            await update.message.reply_text(
                "✏️ *Selecciona número* para cambiar intervalo:\n"+ "\n".join(lines),
                parse_mode="Markdown", reply_markup=BACK_KEYBOARD
            )
            ctx.user_data["waiting_for"] = "edit_msg_select"
            return

        if waiting == "edit_msg_select":
            try:
                idx = int(text)-1
                ctx.user_data["edit_idx"] = idx
                await update.message.reply_text("🕒 *Nuevo intervalo* (s):", parse_mode="Markdown", reply_markup=BACK_KEYBOARD)
                ctx.user_data["waiting_for"] = "edit_msg_value"
            except:
                await update.message.reply_text("❌ Selección inválida.", reply_markup=MAIN_KEYBOARD)
            return

        if waiting == "edit_msg_value":
            try:
                v = int(text)
                idx = ctx.user_data.pop("edit_idx")
                self.mensajes[idx]["intervalo_segundos"] = v
                save_mensajes(self.mensajes)
                await update.message.reply_text(f"✅ Intervalo actualizado a {v}s", reply_markup=MAIN_KEYBOARD)
            except:
                await update.message.reply_text("❌ Valor inválido.", reply_markup=MAIN_KEYBOARD)
            ctx.user_data.pop("waiting_for")
            return

        # == Eliminar Mensaje ==
        if text == "🗑️ Eliminar Mensaje":
            if not self.mensajes:
                return await update.message.reply_text("⚠️ No hay mensajes.", reply_markup=MAIN_KEYBOARD)
            lines = [f"{i+1}. {m['message_id']}" for i,m in enumerate(self.mensajes)]
            await update.message.reply_text(
                "🗑️ *Selecciona número* para eliminar:\n"+ "\n".join(lines),
                parse_mode="Markdown", reply_markup=BACK_KEYBOARD
            )
            ctx.user_data["waiting_for"] = "del_msg_select"
            return

        if waiting == "del_msg_select":
            try:
                idx = int(text)-1
                m = self.mensajes.pop(idx)
                save_mensajes(self.mensajes)
                await update.message.reply_text(f"✅ Mensaje `{m['message_id']}` eliminado.", reply_markup=MAIN_KEYBOARD)
            except:
                await update.message.reply_text("❌ Selección inválida.", reply_markup=MAIN_KEYBOARD)
            ctx.user_data.pop("waiting_for")
            return

        # == Cambiar Intervalo Global ==
        if text == "🔁 Cambiar Intervalo":
            kb = ReplyKeyboardMarkup([["🔁 Global","✏️ Por Mensaje"],["📋 Por Lista"],["🔙 Volver"]],resize_keyboard=True)
            await update.message.reply_text("🕒 *Modo Intervalo*", parse_mode="Markdown", reply_markup=kb)
            ctx.user_data["waiting_for"] = "interval_menu"
            return

        if waiting == "interval_menu":
            if text == "🔁 Global":
                await update.message.reply_text("🕒 *Nuevo intervalo global* (s):", parse_mode="Markdown", reply_markup=BACK_KEYBOARD)
                ctx.user_data["waiting_for"] = "interval_global"
            elif text == "✏️ Por Mensaje":
                await update.message.reply_text("✏️ *ID de mensaje*:", parse_mode="Markdown", reply_markup=BACK_KEYBOARD)
                ctx.user_data["waiting_for"] = "interval_msg_id"
            elif text == "📋 Por Lista":
                lists = self.config.get("listas_destinos",{})
                if not lists:
                    await update.message.reply_text("⚠️ No hay listas.", reply_markup=MAIN_KEYBOARD)
                    ctx.user_data.pop("waiting_for")
                else:
                    kb = ReplyKeyboardMarkup([[n] for n in lists]+[["🔙 Volver"]],resize_keyboard=True)
                    await update.message.reply_text("📋 *Elige lista*:", parse_mode="Markdown", reply_markup=kb)
                    ctx.user_data["waiting_for"] = "interval_list_sel"
            else:
                await update.message.reply_text("🔙 Volver al menú", reply_markup=MAIN_KEYBOARD)
                ctx.user_data.pop("waiting_for")
            return

        if waiting == "interval_global":
            try:
                v = int(text)
                self.config["intervalo_segundos"] = v
                save_config(self.config)
                await update.message.reply_text(f"✅ Intervalo global: {v}s", reply_markup=MAIN_KEYBOARD)
            except:
                await update.message.reply_text("❌ Número inválido.", reply_markup=MAIN_KEYBOARD)
            ctx.user_data.pop("waiting_for")
            return

        if waiting == "interval_msg_id":
            try:
                idx = int(text)-1
                ctx.user_data["interval_msg_idx"] = idx
                await update.message.reply_text("🕒 *Nuevo intervalo* (s):",parse_mode="Markdown",reply_markup=BACK_KEYBOARD)
                ctx.user_data["waiting_for"] = "interval_msg_val"
            except:
                await update.message.reply_text("❌ Selección inválida.", reply_markup=MAIN_KEYBOARD)
            return

        if waiting == "interval_msg_val":
            try:
                v = int(text)
                idx = ctx.user_data.pop("interval_msg_idx")
                self.mensajes[idx]["intervalo_segundos"] = v
                save_mensajes(self.mensajes)
                await update.message.reply_text(f"✅ Mensaje {idx+1}: {v}s", reply_markup=MAIN_KEYBOARD)
            except:
                await update.message.reply_text("❌ Error.", reply_markup=MAIN_KEYBOARD)
            ctx.user_data.pop("waiting_for")
            return

        if waiting == "interval_list_sel":
            if text == "🔙 Volver":
                await update.message.reply_text("🔙 Volver al menú", reply_markup=MAIN_KEYBOARD)
                ctx.user_data.pop("waiting_for")
            else:
                ctx.user_data["interval_list_name"] = text
                await update.message.reply_text("🕒 *Nuevo intervalo* (s):", parse_mode="Markdown", reply_markup=BACK_KEYBOARD)
                ctx.user_data["waiting_for"] = "interval_list_val"
            return

        if waiting == "interval_list_val":
            try:
                name = ctx.user_data.pop("interval_list_name")
                v = int(text)
                for m in self.mensajes:
                    if m.get("dest_list")==name:
                        m["intervalo_segundos"] = v
                save_mensajes(self.mensajes)
                await update.message.reply_text(f"✅ Lista `{name}`: {v}s", reply_markup=MAIN_KEYBOARD)
            except:
                await update.message.reply_text("❌ Error.", reply_markup=MAIN_KEYBOARD)
            ctx.user_data.pop("waiting_for")
            return

        # == Cambiar Zona ==
        if text == "🌐 Cambiar Zona":
            await update.message.reply_text("🌍 Nueva zona (p.ej. Europe/Madrid):", reply_markup=BACK_KEYBOARD)
            ctx.user_data["waiting_for"] = "timezone"
            return
        if waiting == "timezone":
            try:
                pytz.timezone(text)
                self.config["zone"] = text
                save_config(self.config)
                await update.message.reply_text(f"✅ Zona: `{text}`", parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
            except:
                await update.message.reply_text("❌ Zona inválida.", reply_markup=MAIN_KEYBOARD)
            ctx.user_data.pop("waiting_for")
            return

        # == Estado del Bot ==
        if text == "📄 Estado del Bot":
            await self._show_main_menu(update)
            return

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

    def run(self):
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(MessageHandler(filters.ALL, self.message_handler))
        # arrancar forwarder después de /start
        app.job_queue.run_once(lambda c: None, when=0)
        logger.info("🚀 Bot iniciado")
        app.run_polling()

if __name__ == "__main__":
    conf = load_config()
    token = conf.get("bot_token")
    if not token:
        logger.error("❌ Debes definir bot_token en config.json")
        exit(1)
    TelegramForwarderBot(token).run()
