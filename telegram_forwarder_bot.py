#!/usr/bin/env python3

-- coding: utf-8 --

0) Monkey-patch APScheduler timezone issue

import apscheduler.util import pytz

def _safe_astimezone(timezone): # Si no hay zona, usar UTC if timezone is None: return pytz.UTC # Si ya es tzinfo válido, devolverlo if hasattr(timezone, "utcoffset"): return timezone # Si viene como string o tiene atributo .zone, intenta convertir name = timezone if isinstance(timezone, str) else getattr(timezone, "zone", None) if name: try: return pytz.timezone(name) except Exception: pass # Fallback a UTC return pytz.UTC

Reemplaza la función astimezone de APScheduler

apscheduler.util.astimezone = _safe_astimezone

Imports estándar

import logging from datetime import datetime from telegram import Update, ReplyKeyboardMarkup from telegram.ext import ( Application, CommandHandler, MessageHandler, filters, ContextTypes, ) from config_manager import load_config, save_config, load_mensajes, save_mensajes

Configurar logging

logging.basicConfig( format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO ) logger = logging.getLogger(name)

Teclados principales

MAIN_KB = ReplyKeyboardMarkup([ ["🔗 Vincular Canal", "📂 Destinos"], ["✏️ Editar Mensaje", "🗑️ Eliminar Mensaje"], ["🔁 Cambiar Intervalo", "🌐 Cambiar Zona"], ["📄 Estado del Bot"] ], resize_keyboard=True) BACK_KB = ReplyKeyboardMarkup([["🔙 Volver"]], resize_keyboard=True)

class TelegramForwarderBot: def init(self, token): self.config = load_config() self.mensajes = load_mensajes() self.token = token

def _is_admin(self, uid):
    return uid == self.config.get("admin_id")

async def start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not self._is_admin(uid):
        await update.message.reply_text(
            "❌ *Acceso denegado.*",
            parse_mode="Markdown",
            reply_markup=MAIN_KB
        )
        return
    await self._show_main_menu(update)

async def _show_main_menu(self, update: Update):
    text = (
        "🚀 *Menú Principal*\n\n"
        f"📺 Origen: `{self.config.get('origen_chat_id','No asignado')}`\n"
        f"👥 Destinos: {len(self.config.get('destinos',[]))}\n"
        f"📁 Listas: {len(self.config.get('listas_destinos',{}))}\n"
        f"📨 Mensajes: {len(self.mensajes)}\n"
        f"⏱️ Intervalo: {self.config.get('intervalo_segundos',60)}s\n"
        f"🌐 Zona: `{self.config.get('timezone','UTC')}`\n\n"
        "Selecciona una opción:"
    )
    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text(text, reply_markup=MAIN_KB, parse_mode="Markdown")

async def message_handler(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not self._is_admin(uid):
        return
    text = update.message.text.strip() if update.message.text else ""
    waiting = ctx.user_data.get("waiting_for")

    # 1) Vincular Canal
    if text == "🔗 Vincular Canal":
        await update.message.reply_text(
            "📤 *Reenvía un mensaje* desde tu canal de origen.",
            parse_mode="Markdown", reply_markup=BACK_KB
        )
        ctx.user_data["waiting_for"] = "channel_forward"
        return
    if waiting == "channel_forward":
        fchat = getattr(update.message, 'forward_from_chat', None)
        if fchat:
            cid = fchat.id
            self.config["origen_chat_id"] = str(cid)
            save_config(self.config)
            await update.message.reply_text(
                f"✅ Canal vinculado: `{cid}`",
                parse_mode="Markdown", reply_markup=MAIN_KB
            )
            ctx.user_data.pop("waiting_for")
        return

    # 2) Gestión de Destinos
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
            await update.message.reply_text("📝 Envía ID del destino:", reply_markup=BACK_KB)
            ctx.user_data["waiting_for"] = "add_destino"
            return
        if text == "🗑️ Eliminar Destino":
            ds = self.config.get("destinos", [])
            if not ds:
                await update.message.reply_text("⚠️ No hay destinos.", reply_markup=MAIN_KB)
            else:
                lines = "\n".join(f"{i+1}. {d}" for i,d in enumerate(ds))
                await update.message.reply_text(f"🗑️ Selecciona número:\n{lines}", parse_mode="Markdown", reply_markup=BACK_KB)
                ctx.user_data["waiting_for"] = "del_destino"
            return
        if text == "📁 Crear Lista":
            await update.message.reply_text("📌 Nombre de la nueva lista:", reply_markup=BACK_KB)
            ctx.user_data["waiting_for"] = "new_list_name"
            return
        if text == "📂 Gestionar Listas":
            lists = self.config.get("listas_destinos", {})
            if not lists:
                await update.message.reply_text("⚠️ No hay listas.", reply_markup=MAIN_KB)
            else:
                menu = [[n] for n in lists.keys()] + [["🔙 Volver"]]
                await update.message.reply_text("📂 *Listas Disponibles:*", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True))
                ctx.user_data["waiting_for"] = "manage_lists"
            return
        if text == "🔙 Volver":
            await self._show_main_menu(update)
            ctx.user_data.pop("waiting_for")
            return
    if waiting == "add_destino":
        d = text
        lst = self.config.setdefault("destinos", [])
        if d not in lst:
            lst.append(d)
            save_config(self.config)
            await update.message.reply_text(f"✅ Destino `{d}` agregado.", reply_markup=MAIN_KB)
        else:
            await update.message.reply_text("⚠️ Ya existe.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return
    if waiting == "del_destino":
        try:
            idx = int(text)-1
            d = self.config["destinos"].pop(idx)
            save_config(self.config)
            await update.message.reply_text(f"✅ Destino `{d}` eliminado.", reply_markup=MAIN_KB)
        except:
            await update.message.reply_text("❌ Selección inválida.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return
    if waiting == "new_list_name":
        ctx.user_data["new_list_name"] = text
        await update.message.reply_text("📋 Ahora envía los IDs (coma o línea):", reply_markup=BACK_KB)
        ctx.user_data["waiting_for"] = "new_list_ids"
        return
    if waiting == "new_list_ids":
        name = ctx.user_data.pop("new_list_name")
        ids = [x.strip() for x in text.replace("\n",",").split(",") if x.strip()]
        self.config.setdefault("listas_destinos", {})[name] = ids
        save_config(self.config)
        await update.message.reply_text(f"✅ Lista `{name}` creada con {len(ids)} destinos.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return
    if waiting == "manage_lists":
        if text == "🔙 Volver":
            await self._show_main_menu(update)
            ctx.user_data.pop("waiting_for")
            return
        name = text
        if name in self.config.get("listas_destinos", {}):
            kb = ReplyKeyboardMarkup([["📋 Ver","❌ Eliminar"],["🔙 Volver"]], resize_keyboard=True)
            await update.message.reply_text(f"📂 *{name}* ({len(self.config['listas_destinos'][name])})", parse_mode="Markdown", reply_markup=kb)
            ctx.user_data["waiting_for"] = f"list_{name}"
        return
    if waiting and waiting.startswith("list_"):
        name = waiting.split("_",1)[1]
        if text == "📋 Ver":
            ids = self.config["listas_destinos"].get(name, [])
            await update.message.reply_text("\n".join(ids) or "Ninguno", reply_markup=MAIN_KB)
        elif text == "❌ Eliminar":
            self.config["listas_destinos"].pop(name, None)
            save_config(self.config)
            await update.message.reply_text(f"❌ Lista `{name}` eliminada.", reply_markup=MAIN_KB)
        else:
            await self._show_main_menu(update)
        ctx.user_data.pop("waiting_for")
        return
    # 3) Captura de mensaje reenviado
    fchat2 = getattr(update.message, 'forward_from_chat', None)
    if fchat2 and str(fchat2.id) == str(self.config.get("origen_chat_id")):
        mid = getattr(update.message, 'forward_from_message_id', None)
        nuevo = {
            "from_chat_id": fchat2.id,
            "message_id": mid,
            "intervalo_segundos": self.config.get("intervalo_segundos",60),
            "dest_all": True,
            "dest_list": None,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.mensajes.append(nuevo)
        save_mensajes(self.mensajes)
        kb = ReplyKeyboardMarkup([
            ["👥 A Todos","📋 Lista"],["✅ Guardar","❌ Cancelar"],["🏁 Finalizar"],["🔙 Volver"]
        ], resize_keyboard=True)
        await update.message.reply_text(
            f"🔥 *Nuevo Mensaje Detectado!*\nID: `{mid}`\nIntervalo: `{nuevo['intervalo_segundos']}s`\nElige destino:",parse_mode="Markdown",reply_markup=kb
        )
        ctx.user_data["waiting_for"] = f"msg_cfg_{len(self.mensajes)-1}"
        return
    if waiting and waiting.startswith("msg_cfg_"):
        idx = int(waiting.split("_")[-1])
        m = self.mensajes[idx]
        if text == "👥 A Todos":
            m["dest_all"], m["dest_list"] = True, None
            save_mensajes(self.mensajes)
            await update.message.reply_text("✅ Enviar a todos.", reply_markup=MAIN_KB)
            ctx.user_data.pop("waiting_for")
        elif text == "📋 Lista":
            lists = self.config.get("listas_destinos",{})
            if not lists:
                await update.message_reply_text("⚠️ No hay listas.",reply_markup=MAIN_KB)
                ctx.user_data.pop("waiting_for")
            else:
                kb = ReplyKeyboardMarkup([[n] for n in lists]+[["🔙 Volver"]],resize_keyboard=True)
                await update.message.reply_text("📋 Elige lista:",reply_markup=kb)
                ctx.user_data["waiting_for"] = f"msg_list_{idx}"
        elif waiting.startswith("msg_list_"):
            if text == "🔙 Volver":
                await self._show_main_menu(update)
            else:
                m["dest_all"], m["dest_list"] = False, text
                save_mensajes(self.mensajes)
                await update.message.reply_text(f"✅ Lista `{text}` seleccionada.",reply_markup=MAIN_KB)
            ctx.user_data.pop("waiting_for")
        elif text == "✅ Guardar":
            await update.message.reply_text("✅ Mensaje guardado.",reply_markup=MAIN_KB)
            ctx.user_data.pop("waiting_for")
        elif text == "❌ Cancelar":
            self.mensajes.pop(idx)
            save_mensajes(self.mensajes)
            await update.message_reply_text("❌ Mensaje descartado.",reply_markup=MAIN_KB)
            ctx.user_data.pop("waiting_for")
        elif text == "🏁 Finalizar":
            if not hasattr(ctx.application, "forwarder_job"):
                interval = self.config.get("intervalo_segundos",60)
                ctx.application.forwarder_job = ctx.job_queue.run_repeating(self._reenviar_mensajes,interval=interval,first=interval)
            await update.message.reply_text("🏁 ¡Reenvío iniciado!",reply_markup=MAIN_KB)
            ctx.user_data.pop("waiting_for")
        return
    # 5) Editar Mensaje
    if text == "✏️ Editar Mensaje":
        if not self.mensajes:
            await update.message_reply_text("⚠️ No hay mensajes.",reply_markup=MAIN_KB)
            return
        lines = [f"{i+1}. {m['message_id']} ({m['intervalo_segundos']}s)" for i,m in enumerate(self.mensajes)]
        await update.message.reply_text("✏️ Selecciona número para editar:\n"+"\n".join(lines),parse_mode="Markdown",reply_markup=BACK_KB)
        ctx.user_data["waiting_for"] = "edit_msg_select"
        return
    if waiting == "edit_msg_select":
        try:
            idx = int(text)-1
            ctx.user_data["edit_idx"] = idx
            # Submenú edición
            kb = ReplyKeyboardMarkup([
                ["🕒 Cambiar intervalo","👥 Cambiar destino"],
                ["📋 Cambiar lista","🗑️ Eliminar mensaje"],
                ["🔙 Volver"]
            ], resize_keyboard=True)
            await update.message.reply_text("✏️ ¿Qué quieres hacer?", reply_markup=kb)
            ctx.user_data["waiting_for"] = "edit_msg_menu"
        except:
            await update.message.reply_text("❌ Selección inválida.", reply_markup=MAIN_KB)
        return
    if waiting == "edit_msg_menu":
        idx = ctx.user_data.get("edit_idx")
        m = self.mensajes[idx]
        if text == "🕒 Cambiar intervalo":
            await update.message.reply_text("🕒 Nuevo intervalo (s):", reply_markup=BACK_KB)
            ctx.user_data["waiting_for"] = "edit_msg_interval"
        elif text == "👥 Cambiar destino":
            kb = ReplyKeyboardMarkup([["Sí","No"],["🔙 Volver"]], resize_keyboard=True)
            await update.message.reply_text("👥 Enviar a *todos*? (Sí/No)", parse_mode="Markdown", reply_markup=kb)
            ctx.user_data["waiting_for"] = "edit_msg_dest_all"
        elif text == "📋 Cambiar lista":
            lists = list(self.config.get("listas_destinos",{}).keys())
            if not lists:
                await update.message.reply_text("⚠️ No hay listas.", reply_markup=MAIN_KB)
                ctx.user_data.pop("waiting_for")
            else:
                kb = ReplyKeyboardMarkup([[n] for n in lists]+[["🔙 Volver"]],resize_keyboard=True)
                await update.message.reply_text("📋 Elige lista:", reply_markup=kb)
                ctx.user_data["waiting_for"] = "edit_msg_dest_list"
        elif text == "🗑️ Eliminar mensaje":
            self.mensajes.pop(idx)
            save_m mensajes")}

